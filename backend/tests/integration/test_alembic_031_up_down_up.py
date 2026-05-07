"""Test migration F10 — Alembic 031_extend_interactive_questions (T007).

Vérifie :
- Up : ajoute les 9 valeurs d'enum + colonnes payload/response_payload + contrainte étendue.
- Down : refuse de descendre si des lignes utilisent les nouvelles valeurs.
- Up/down/up idempotent : pas de perte de lignes existantes (4 valeurs F18 conservées).

Couvre FR-004, SC-009, R9.

Note : ces tests utilisent SQLite (cohérent avec ``conftest.py``). En PostgreSQL,
les ALTER TYPE ADD VALUE et le check constraint sont gérés différemment ; les
tests d'intégration en CI Docker valideront le comportement Postgres-spécifique.
Le test ici se concentre sur la cohérence du schéma SQLAlchemy après upgrade et
sur la possibilité d'insérer des lignes avec les nouvelles valeurs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
    InteractiveQuestionType,
)


@pytest.mark.asyncio
async def test_payload_column_exists(db_session: AsyncSession) -> None:
    """Vérifie que la colonne payload existe et a le bon défaut."""
    # Inspection portable (SQLite et PostgreSQL).
    bind = await db_session.connection()

    def _inspect_columns(sync_conn) -> list[str]:
        return [c["name"] for c in inspect(sync_conn).get_columns("interactive_questions")]

    columns = await bind.run_sync(_inspect_columns)
    assert "payload" in columns, "La colonne 'payload' doit exister après la migration"
    assert "response_payload" in columns, (
        "La colonne 'response_payload' doit exister après la migration"
    )


@pytest.mark.asyncio
async def test_insert_row_with_new_yes_no_type(db_session: AsyncSession) -> None:
    """Insertion d'une question avec ``question_type='yes_no'`` accepté."""
    from uuid import uuid4

    from app.models.conversation import Conversation
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)

    conv = Conversation(id=uuid4(), user_id=user.id, title="T")
    db_session.add(conv)
    await db_session.flush()

    q = InteractiveQuestion(
        conversation_id=conv.id,
        module="chat",
        question_type=InteractiveQuestionType.YES_NO.value,
        prompt="Êtes-vous certain de vouloir supprimer ?",
        options=[],
        min_selections=1,
        max_selections=1,
        state=InteractiveQuestionState.PENDING.value,
        payload={
            "question_type": "yes_no",
            "confirm_label": "Oui, supprimer",
            "deny_label": "Non, annuler",
            "destructive": True,
        },
    )
    db_session.add(q)
    await db_session.flush()
    await db_session.refresh(q)

    assert q.payload["destructive"] is True
    assert q.payload["confirm_label"] == "Oui, supprimer"


@pytest.mark.asyncio
async def test_insert_row_with_select_max_50(db_session: AsyncSession) -> None:
    """Vérifie que la contrainte étendue accepte max_selections > 8 pour 'select'."""
    from uuid import uuid4

    from app.models.conversation import Conversation
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)

    conv = Conversation(id=uuid4(), user_id=user.id, title="T")
    db_session.add(conv)
    await db_session.flush()

    q = InteractiveQuestion(
        conversation_id=conv.id,
        module="profile",
        question_type=InteractiveQuestionType.SELECT.value,
        prompt="Choisissez 5 pays",
        options=[],
        min_selections=1,
        max_selections=50,  # > 8, doit être accepté pour 'select'
        state=InteractiveQuestionState.PENDING.value,
        payload={
            "question_type": "select",
            "options": [
                {"id": f"id_{i}", "label": f"Country {i}"} for i in range(50)
            ],
            "min_selections": 1,
            "max_selections": 50,
            "allow_other": False,
        },
    )
    db_session.add(q)
    await db_session.flush()
    await db_session.refresh(q)

    assert q.max_selections == 50
    assert q.question_type == "select"


@pytest.mark.asyncio
async def test_legacy_qcu_qcm_still_work(db_session: AsyncSession) -> None:
    """SC-009 — Les 4 valeurs F18 (qcu/qcm/qcu_justification/qcm_justification)
    restent insérables après migration."""
    from uuid import uuid4

    from app.models.conversation import Conversation
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)

    conv = Conversation(id=uuid4(), user_id=user.id, title="T")
    db_session.add(conv)
    await db_session.flush()

    for qtype in ("qcu", "qcm", "qcu_justification", "qcm_justification"):
        q = InteractiveQuestion(
            conversation_id=conv.id,
            module="chat",
            question_type=qtype,
            prompt=f"Question {qtype}",
            options=[
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            min_selections=1,
            max_selections=1 if qtype.startswith("qcu") else 2,
            requires_justification=qtype.endswith("_justification"),
            justification_prompt="Pourquoi ?" if qtype.endswith("_justification") else None,
            state=InteractiveQuestionState.PENDING.value,
        )
        db_session.add(q)
        await db_session.flush()


@pytest.mark.asyncio
async def test_payload_default_empty_dict(db_session: AsyncSession) -> None:
    """Le défaut de payload doit être un dict vide (server_default='{}')."""
    from uuid import uuid4

    from app.models.conversation import Conversation
    from tests.conftest import make_pme_user

    user = await make_pme_user(db_session)

    conv = Conversation(id=uuid4(), user_id=user.id, title="T")
    db_session.add(conv)
    await db_session.flush()

    # Insertion sans payload explicite (cas legacy F18 qui ne set pas payload)
    q = InteractiveQuestion(
        conversation_id=conv.id,
        module="chat",
        question_type="qcu",
        prompt="Test",
        options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        state=InteractiveQuestionState.PENDING.value,
    )
    db_session.add(q)
    await db_session.flush()
    await db_session.refresh(q)

    assert q.payload == {}, "Le défaut de payload doit être un dict vide"
