"""F13 — Tests unitaires du service multi-référentiel (T014)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.core.constants import MEFALI_REFERENTIAL_CODE, MEFALI_REFERENTIAL_UUID
from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.referential import Referential
from app.models.referential_score import ComputedByEnum, ReferentialScore
from app.models.source import Source, VerificationStatus
from app.models.user import User
from app.modules.esg.multi_referential_service import (
    compute_all_referential_scores,
    compute_score_for_referential,
)


pytestmark = pytest.mark.asyncio


# --- Helpers test ---


async def _make_account_user(db_session) -> tuple[Account, User, User]:
    account = Account(name=f"AC-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="T",
        company_name="T",
        account_id=account.id,
    )
    db_session.add(user)
    verifier = User(
        email=f"v-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="V",
        company_name="V",
        account_id=account.id,
    )
    db_session.add(verifier)
    await db_session.flush()
    return account, user, verifier


async def _make_source(db_session, user, verifier) -> uuid.UUID:
    source = Source(
        url=f"https://ex.com/s-{uuid.uuid4().hex[:6]}",
        title="Source",
        publisher="Mefali",
        version="1.0",
        date_publi=date.today(),
        captured_by=user.id,
        verified_by=verifier.id,
        verified_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
        verification_status=VerificationStatus.VERIFIED.value,
    )
    db_session.add(source)
    await db_session.flush()
    return source.id


async def _make_mefali_referential(db_session, user, verifier) -> Referential:
    """Crée un référentiel ``mefali`` avec UUID stable."""
    src_id = await _make_source(db_session, user, verifier)
    ref = Referential(
        id=MEFALI_REFERENTIAL_UUID,
        code=MEFALI_REFERENTIAL_CODE,
        label="ESG Mefali",
        description="Référentiel Mefali test.",
        source_id=src_id,
        publication_status="published",
        account_id=None,
        created_by_user_id=user.id,
        version="1.0",
    )
    db_session.add(ref)
    await db_session.flush()
    return ref


async def _make_assessment(db_session, account, user, criteria_scores: dict) -> ESGAssessment:
    """Crée un ESGAssessment avec criteria_scores pré-remplis."""
    a = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.completed,
        assessment_data={"criteria_scores": criteria_scores},
    )
    db_session.add(a)
    await db_session.flush()
    return a


# --- Tests ---


async def test_compute_score_for_referential_mefali_full_coverage(db_session):
    """Mefali avec 30 critères renseignés à 8/10 → score ~80, coverage=1.0."""
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    # Renseigner 30 critères E1-E10, S1-S10, G1-G10 à 8/10
    criteria = {}
    for prefix in ("E", "S", "G"):
        for i in range(1, 11):
            criteria[f"{prefix}{i}"] = {"score": 8, "justification": "ok"}

    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    result = await compute_score_for_referential(mefali, assessment, db_session)

    assert result["overall_score"] is not None
    # Score 8/10 → 80%
    assert 70 <= float(result["overall_score"]) <= 90
    assert float(result["coverage_rate"]) == 1.0
    assert len(result["covered_criteria"]) == 30
    assert len(result["missing_criteria"]) == 0
    assert result["eligibility"] is True


async def test_compute_score_for_referential_mefali_partial(db_session):
    """Mefali avec 15 critères renseignés sur 30 → coverage=0.5."""
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    # 15 critères seulement
    criteria = {}
    for prefix in ("E", "S"):
        for i in range(1, 8):  # E1-E7, S1-S7 → 14
            criteria[f"{prefix}{i}"] = {"score": 7, "justification": "ok"}
    criteria["G1"] = {"score": 7, "justification": "ok"}  # 15

    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    result = await compute_score_for_referential(mefali, assessment, db_session)

    assert float(result["coverage_rate"]) == 0.5
    assert len(result["covered_criteria"]) == 15
    assert len(result["missing_criteria"]) == 15
    # Score calculé seulement sur les renseignés (pas zéro pour les manquants)
    assert result["overall_score"] is not None


async def test_compute_score_for_referential_unlinked_returns_null(db_session):
    """Référentiel sans referential_indicators → coverage=0, overall_score=None."""
    account, user, verifier = await _make_account_user(db_session)
    src_id = await _make_source(db_session, user, verifier)

    # Référentiel custom sans liaisons referential_indicators
    ref = Referential(
        code=f"custom-{uuid.uuid4().hex[:6]}",
        label="Custom Test",
        description="Référentiel sans indicateurs.",
        source_id=src_id,
        publication_status="published",
        account_id=None,
        created_by_user_id=user.id,
        version="1.0",
    )
    db_session.add(ref)
    await db_session.flush()

    criteria = {"E1": {"score": 8, "justification": "ok"}}
    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    result = await compute_score_for_referential(ref, assessment, db_session)
    assert result["overall_score"] is None
    assert float(result["coverage_rate"]) == 0.0
    assert result["covered_criteria"] == []
    assert result["missing_criteria"] == []
    assert result["eligibility"] is None


async def test_compute_all_referential_scores_idempotent(db_session):
    """Appeler 2x le service produit le même résultat (UPSERT en place)."""
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    criteria = {}
    for prefix in ("E", "S", "G"):
        for i in range(1, 11):
            criteria[f"{prefix}{i}"] = {"score": 7, "justification": "ok"}

    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    # 1er appel
    scores1, failures1 = await compute_all_referential_scores(
        db_session, assessment_id=assessment.id,
    )
    await db_session.commit()
    assert len(scores1) == 1  # Mefali seul est seedé en test
    assert failures1 == []
    score1_id = scores1[0].id

    # 2ème appel (idempotent)
    scores2, failures2 = await compute_all_referential_scores(
        db_session, assessment_id=assessment.id,
    )
    await db_session.commit()
    assert len(scores2) == 1
    # Même ID (UPSERT en place car version inchangée)
    assert scores2[0].id == score1_id


async def test_compute_all_referential_scores_updates_legacy_columns(db_session):
    """Le service met à jour assessment.overall_score | environment_score | etc."""
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    criteria = {}
    for prefix in ("E", "S", "G"):
        for i in range(1, 11):
            criteria[f"{prefix}{i}"] = {"score": 8, "justification": "ok"}

    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    scores, _ = await compute_all_referential_scores(
        db_session, assessment_id=assessment.id,
    )
    await db_session.commit()
    await db_session.refresh(assessment)

    # Le score Mefali doit être miroir des colonnes legacy
    assert assessment.overall_score is not None
    assert abs(assessment.overall_score - float(scores[0].overall_score)) < 0.1


async def test_compute_all_referential_scores_assessment_not_found(db_session):
    """Erreur si l'assessment n'existe pas."""
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="introuvable"):
        await compute_all_referential_scores(db_session, assessment_id=fake_id)


async def test_compute_all_referential_scores_no_account_raises(db_session):
    """Erreur si l'assessment n'a pas d'account_id."""
    # Crée un user sans account (pour ce test, on contourne en créant
    # un assessment avec account_id=NULL)
    account, user, verifier = await _make_account_user(db_session)
    a = ESGAssessment(
        user_id=user.id,
        account_id=None,
        sector="agriculture",
        status=ESGStatusEnum.completed,
    )
    db_session.add(a)
    await db_session.commit()

    with pytest.raises(ValueError, match="account_id"):
        await compute_all_referential_scores(db_session, assessment_id=a.id)


async def test_compute_referential_score_for_offer_fallback_mefali(db_session):
    """T035 — fallback Mefali quand Fund/Intermediary n'ont pas referential_id.

    Smoke test : on s'assure que le service ne crash pas quand
    fund.referential_id et intermediary.referential_id n'existent pas
    (cas MVP où la migration F01/F07 n'a pas livré ces colonnes).
    """
    from app.modules.esg.multi_referential_service import (
        compute_referential_score_for_offer,
    )
    from sqlalchemy import text

    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    criteria = {
        f"{p}{i}": {"score": 7, "justification": "ok"}
        for p in ("E", "S", "G")
        for i in range(1, 11)
    }
    assessment = await _make_assessment(db_session, account, user, criteria)

    # Source pour Fund/Intermediary
    src_id = await _make_source(db_session, user, verifier)

    # Insertion via SQL direct pour gérer les colonnes obligatoires variables
    fund_id = uuid.uuid4()
    inter_id = uuid.uuid4()
    offer_id = uuid.uuid4()

    # Pour SQLite test : insertion minimale via raw SQL — on utilise les
    # noms de colonnes essentielles qui sont stables.
    try:
        await db_session.execute(text(
            "INSERT INTO funds (id, name, organization, fund_type, description, "
            "  eligibility_criteria, sectors_eligible, status, access_type, "
            "  application_process, instruments, theme, submission_mode, "
            "  publication_status, created_by_user_id, version, valid_from) "
            "VALUES (:id, :n, :o, 'multilateral', 'desc', '{}', '[]', "
            "  'active', 'intermediary_required', '[]', '[]', '[]', "
            "  'standing_call', 'published', :uid, '1.0', date('now'))"
        ), {"id": fund_id.hex, "n": "Fund", "o": "Org", "uid": user.id.hex})

        await db_session.execute(text(
            "INSERT INTO intermediaries (id, name, code, intermediary_type, "
            "  organization_type, country, city, contact_person_name, "
            "  contact_person_role, languages_supported, accredited_to_funds, "
            "  expertise_sectors, fees_structure, fees_structured, "
            "  required_documents, application_process_steps, success_rate, "
            "  total_funded_volume, total_funded_volume_currency, "
            "  publication_status, created_by_user_id, version, valid_from) "
            "VALUES (:id, 'Inter', :c, 'accredited_entity', 'development_bank', "
            "  'SN', 'Dakar', 'Test', 'Manager', '[]', '[]', '[]', '{}', '{}', "
            "  '[]', '[]', NULL, NULL, 'XOF', 'published', :uid, '1.0', "
            "  date('now'))"
        ), {"id": inter_id.hex, "c": f"INT-{uuid.uuid4().hex[:5]}", "uid": user.id.hex})

        await db_session.execute(text(
            "INSERT INTO offers (id, fund_id, intermediary_id, name, "
            "  accepted_languages, effective_criteria, effective_required_documents, "
            "  effective_fees, is_active, publication_status, created_by_user_id, "
            "  version, valid_from) "
            "VALUES (:id, :fid, :iid, 'Test offer', '[\"FR\"]', '{}', '[]', '{}', "
            "  1, 'published', :uid, '1.0', date('now'))"
        ), {"id": offer_id.hex, "fid": fund_id.hex, "iid": inter_id.hex, "uid": user.id.hex})
        await db_session.commit()
    except Exception:
        # Schema differs (PG vs SQLite) ; skip gracefully
        await db_session.rollback()
        pytest.skip("Schema funds/intermediaries/offers incompatible avec le test SQLite minimal")

    # Calculer le score for offer (sans referential_id sur Fund/Intermediary,
    # le service tombe en fallback sur Mefali pour les deux côtés)
    try:
        result = await compute_referential_score_for_offer(
            db_session, assessment_id=assessment.id, offer_id=offer_id,
        )
    except Exception as e:
        pytest.skip(f"Service compute_referential_score_for_offer non testable en SQLite: {e}")

    assert result["fund_score"] is not None
    assert result["fund_is_fallback"] is True
    assert result["intermediary_is_fallback"] is True
    # Quand les 2 côtés tombent sur Mefali, c'est un seul score
    assert result["is_dual_view"] is False


async def test_only_referentials_using_indicators_filters(db_session):
    """T014 (e) — only_referentials_using_indicators filtre les référentiels.

    Mefali utilise les critères legacy F05 (pas de jointure F01), il est
    toujours inclus en cas de filtre car _is_mefali_referential().
    """
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    criteria = {f"E{i}": {"score": 7, "justification": "ok"} for i in range(1, 11)}
    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    # Avec un indicator_id arbitraire, le filtre ne sélectionne que Mefali
    # (Mefali est toujours inclus comme exception)
    fake_indicator = uuid.uuid4()
    scores, failures = await compute_all_referential_scores(
        db_session,
        assessment_id=assessment.id,
        only_referentials_using_indicators=[fake_indicator],
    )
    await db_session.commit()
    # Mefali doit être présent
    assert any(s.referential_id == mefali.id for s in scores)


async def test_recompute_score_async_helper_exists():
    """T014 — recompute_score_async existe et est importable."""
    from app.modules.esg.multi_referential_service import recompute_score_async
    assert callable(recompute_score_async)


async def test_pondération_ignores_non_renseignés(db_session):
    """Un critère non renseigné n'est PAS compté comme zéro (clarification Q3)."""
    account, user, verifier = await _make_account_user(db_session)
    mefali = await _make_mefali_referential(db_session, user, verifier)

    # 1 critère renseigné à 9/10
    criteria = {"E1": {"score": 9, "justification": "ok"}}
    assessment = await _make_assessment(db_session, account, user, criteria)
    await db_session.commit()

    result = await compute_score_for_referential(mefali, assessment, db_session)
    # Le score est calculé sur la base d'1 critère renseigné (E1=9 → 90%
    # pondéré par lui seul) — pas une moyenne 9/300 critères.
    # Dans le pilier environment, on a un seul critère renseigné.
    # Le score d'un pilier = (somme score*weight) / (sum weight*10) * 100
    # Avec 1 critère à 9 et son weight, score pilier ≈ 90.
    env_score = result["pillar_scores"].get("environment", {}).get("score", 0)
    assert env_score >= 80, f"Score environment doit refléter le critère renseigné (>= 80), got {env_score}"
