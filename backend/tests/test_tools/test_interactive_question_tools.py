"""Tests TDD du tool ask_interactive_question (F18).

Bug ciblé : l'INSERT en BDD échouait avec NOT NULL violation sur
`interactive_questions.account_id` car le tool ne propageait pas l'identifiant
multi-tenant depuis le RunnableConfig (pattern F12 `recall_history`).

Trois invariants à garantir après le fix :

1. Avec un RunnableConfig valide → INSERT contient `account_id` correct +
   `assistant_message_id` non NULL si fourni dans le config.
2. Sans `account_id` propageable → erreur claire renvoyée au LLM (pas une
   exception générique non gérée qui produit un 500 côté API).
3. Isolation multi-tenant : la question créée pour le tenant A n'apparaît
   pas dans le scope du tenant B (filtrage `account_id`).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.graph.tools.interactive_tools import ask_interactive_question
from app.models.account import Account
from app.models.conversation import Conversation
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
)
from app.models.message import Message
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def _make_tenant(
    db_session,
    *,
    company_name: str = "TenantCo",
) -> tuple[Account, User, Conversation]:
    """Créer un trio (Account, User PME, Conversation) cohérent pour les tests."""
    account = Account(name=f"{company_name}-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()

    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        full_name="Test User",
        company_name=company_name,
        is_active=True,
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(
        user_id=user.id,
        account_id=account.id,
        title=f"conv-{uuid.uuid4().hex[:4]}",
    )
    db_session.add(conv)
    await db_session.flush()

    return account, user, conv


def _config_for(
    db_session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    assistant_message_id: uuid.UUID | None = None,
    active_module: str = "chat",
) -> dict:
    """Construire un RunnableConfig conforme au pattern F12/F02."""
    configurable: dict = {
        "db": db_session,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "active_module": active_module,
    }
    if account_id is not None:
        configurable["account_id"] = account_id
    if assistant_message_id is not None:
        configurable["assistant_message_id"] = assistant_message_id
    return {"configurable": configurable}


def _extract_sse_payload(result: str) -> dict | None:
    marker = "<!--SSE:"
    if marker not in result:
        return None
    start = result.index(marker) + len(marker)
    end = result.index("-->", start)
    return json.loads(result[start:end])


# ─── Test 1 : INSERT contient account_id correct + assistant_message_id ──


async def test_ask_interactive_question_persists_account_id(db_session):
    """Avec un config valide (account_id propagé), l'INSERT enregistre
    `account_id` à l'identique du tenant courant."""
    account, user, conv = await _make_tenant(db_session)

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Quel modèle de valorisation des déchets ?",
            "options": [
                {"id": "compost", "label": "Compostage"},
                {"id": "biogas", "label": "Biogaz"},
                {"id": "incinerate", "label": "Incinération"},
            ],
        },
        config=_config_for(
            db_session,
            user_id=user.id,
            conversation_id=conv.id,
            account_id=account.id,
        ),
    )

    # Le tool ne renvoie PAS un message d'erreur
    assert "Erreur" not in result, f"Tool retournait une erreur: {result!r}"
    payload = _extract_sse_payload(result)
    assert payload is not None, "Marker SSE absent dans le retour du tool"

    rows = (await db_session.execute(select(InteractiveQuestion))).scalars().all()
    assert len(rows) == 1
    iq = rows[0]
    assert iq.state == InteractiveQuestionState.PENDING.value
    # ⚡ Bug ciblé : `account_id` doit être propagé depuis le RunnableConfig
    assert iq.account_id == account.id, (
        f"account_id non propagé : attendu {account.id}, obtenu {iq.account_id!r}"
    )
    assert iq.conversation_id == conv.id


async def test_ask_interactive_question_persists_assistant_message_id(db_session):
    """Si `assistant_message_id` est fourni dans le config, l'INSERT le
    propage côté BDD (option : créer le message assistant avant le tool)."""
    account, user, conv = await _make_tenant(db_session)

    # Simuler un message assistant créé en amont du tool call (option 1 du fix)
    assistant_msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="assistant",
        content="",
    )
    db_session.add(assistant_msg)
    await db_session.flush()

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Quel pays UEMOA ?",
            "options": [
                {"id": "sn", "label": "Sénégal"},
                {"id": "ci", "label": "Côte d'Ivoire"},
            ],
        },
        config=_config_for(
            db_session,
            user_id=user.id,
            conversation_id=conv.id,
            account_id=account.id,
            assistant_message_id=assistant_msg.id,
        ),
    )

    assert "Erreur" not in result, f"Tool retournait une erreur: {result!r}"

    rows = (await db_session.execute(select(InteractiveQuestion))).scalars().all()
    assert len(rows) == 1
    iq = rows[0]
    assert iq.assistant_message_id == assistant_msg.id, (
        "assistant_message_id non propagé depuis le RunnableConfig"
    )


# ─── Test 2 : sans account_id → erreur claire ────────────────────────────


async def test_ask_interactive_question_missing_account_id_returns_clear_error(
    db_session,
):
    """Sans `account_id` propageable (ni via config, ni via SELECT sur
    conversation), le tool DOIT retourner une erreur explicite au LLM
    (au lieu de laisser l'INSERT crasher en NOT NULL violation et produire
    un 500 côté API).

    On force le cas en passant un `conversation_id` inexistant : ni le
    config ni la BDD ne peuvent fournir un account_id valide.
    """
    _account, user, _conv = await _make_tenant(db_session)
    orphan_conversation_id = uuid.uuid4()  # n'existe pas en BDD

    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Test sans account_id",
            "options": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
        },
        config=_config_for(
            db_session,
            user_id=user.id,
            conversation_id=orphan_conversation_id,
            account_id=None,  # ⚠ volontairement absent
        ),
    )

    # Erreur claire renvoyée au LLM, pas un crash silencieux
    assert isinstance(result, str)
    assert "Erreur" in result, (
        f"Attendu un message d'erreur claire, obtenu: {result!r}"
    )
    assert "account_id" in result.lower() or "tenant" in result.lower(), (
        "Le message d'erreur doit mentionner explicitement l'account_id manquant"
    )

    # Aucune ligne ne doit avoir été insérée
    rows = (await db_session.execute(select(InteractiveQuestion))).scalars().all()
    assert len(rows) == 0, (
        "Aucune InteractiveQuestion ne doit être créée si account_id manque"
    )


# ─── Test 3 : isolation multi-tenant ─────────────────────────────────────


async def test_ask_interactive_question_does_not_leak_across_tenants(db_session):
    """La question créée pour le tenant A ne doit pas être visible dans le
    scope SQL d'un autre tenant B (filtrage `account_id`).

    Sur SQLite (tests), RLS est désactivée — l'isolation est vérifiée au
    niveau applicatif via `WHERE account_id = ...`. Sur PostgreSQL prod,
    F02 ajoute en plus la policy RLS `pme_access_own_account`.
    """
    account_a, user_a, conv_a = await _make_tenant(db_session, company_name="AlphaCo")
    account_b, _user_b, _conv_b = await _make_tenant(
        db_session, company_name="BetaCo",
    )

    # Le tool est invoqué dans le scope du tenant A
    result = await ask_interactive_question.ainvoke(
        {
            "question_type": "qcu",
            "prompt": "Question privée du tenant A",
            "options": [
                {"id": "x", "label": "X"},
                {"id": "y", "label": "Y"},
            ],
        },
        config=_config_for(
            db_session,
            user_id=user_a.id,
            conversation_id=conv_a.id,
            account_id=account_a.id,
        ),
    )
    assert "Erreur" not in result

    # Vues filtrées par tenant
    rows_a = (
        await db_session.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.account_id == account_a.id,
            )
        )
    ).scalars().all()
    rows_b = (
        await db_session.execute(
            select(InteractiveQuestion).where(
                InteractiveQuestion.account_id == account_b.id,
            )
        )
    ).scalars().all()

    assert len(rows_a) == 1, "Le tenant A doit voir sa propre question"
    assert len(rows_b) == 0, (
        "Le tenant B ne doit voir aucune question créée par le tenant A"
    )
    assert rows_a[0].account_id == account_a.id
    assert rows_a[0].account_id != account_b.id
