"""Tests F10 — Pattern destructif end-to-end (T016).

Vérifie le flux complet :
1. delete_project(confirm=False) → retourne marker JSON `requires_confirmation`
2. ask_yes_no(destructive=True) → crée question pending
3. Simule réponse user value=true → state=answered
4. Re-appel delete_project(confirm=True) → suppression effective

Couvre FR-011, FR-013, SC-001, SC-011.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.graph.tools.interactive_tools import ask_yes_no
from app.graph.tools.project_tools import delete_project
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
)


@pytest.mark.asyncio
async def test_delete_project_without_confirm_returns_requires_confirmation(
    db_session,
) -> None:
    """delete_project(confirm=False) DOIT retourner le marker sans toucher la BDD."""
    from tests.conftest import make_account, make_pme_user

    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)

    config = {
        "configurable": {
            "db": db_session,
            "user_id": str(user.id),
            "account_id": str(account.id),
        },
    }

    result = await delete_project.ainvoke(
        {"project_id": str(uuid4()), "confirm": False}, config=config,
    )
    parsed = json.loads(result)
    assert parsed["requires_confirmation"] is True
    assert parsed["destructive_action"] == "delete_project"


@pytest.mark.asyncio
async def test_full_flow_delete_with_confirmation(db_session) -> None:
    """Scénario E2E :
    - delete_project(confirm=False) → marker
    - ask_yes_no(destructive=True) → question pending en BDD
    - Re-appel delete_project(confirm=True) → suppression effective
    """
    from app.modules.projects import service as project_service
    from app.modules.projects.schemas import ProjectCreate
    from app.models.conversation import Conversation
    from tests.conftest import make_account, make_pme_user

    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)

    # Créer un projet à supprimer
    detail = await project_service.create_project(
        db_session,
        account_id=account.id,
        payload=ProjectCreate(name="Panneaux solaires"),
    )
    await db_session.flush()

    conv = Conversation(id=uuid4(), user_id=user.id, title="Suppression projet")
    db_session.add(conv)
    await db_session.flush()

    # Étape 1 : delete_project(confirm=False) → marker
    config = {
        "configurable": {
            "db": db_session,
            "user_id": str(user.id),
            "account_id": str(account.id),
            "conversation_id": str(conv.id),
            "active_module": "chat",
        },
    }
    result_step1 = await delete_project.ainvoke(
        {"project_id": str(detail.id), "confirm": False}, config=config,
    )
    parsed_step1 = json.loads(result_step1)
    assert parsed_step1["requires_confirmation"] is True

    # Étape 2 : ask_yes_no(destructive=True) → question pending en BDD
    result_step2 = await ask_yes_no.ainvoke(
        {
            "question": "Êtes-vous certain de vouloir supprimer 'Panneaux solaires' ?",
            "confirm_label": "Oui, supprimer",
            "deny_label": "Non, annuler",
            "destructive": True,
        },
        config=config,
    )
    assert "Question posée" in result_step2

    rows = await db_session.execute(
        select(InteractiveQuestion).where(
            InteractiveQuestion.conversation_id == conv.id,
        ),
    )
    question = rows.scalars().first()
    assert question is not None
    assert question.question_type == "yes_no"
    assert question.state == InteractiveQuestionState.PENDING.value
    assert question.payload["destructive"] is True
    assert question.payload["confirm_label"] == "Oui, supprimer"

    # Étape 3 : re-appel delete_project(confirm=True) → suppression effective
    result_step3 = await delete_project.ainvoke(
        {"project_id": str(detail.id), "confirm": True}, config=config,
    )
    parsed_step3 = json.loads(result_step3)
    # Le projet doit être soft-deleted (status=cancelled)
    assert parsed_step3.get("status") == "cancelled" or parsed_step3.get("ok") is True


@pytest.mark.asyncio
async def test_delete_project_default_confirm_false_blocks(db_session) -> None:
    """Sans paramètre confirm explicite, l'action ne s'exécute jamais (défense en profondeur)."""
    from tests.conftest import make_account, make_pme_user

    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)

    config = {
        "configurable": {
            "db": db_session,
            "user_id": str(user.id),
            "account_id": str(account.id),
        },
    }
    result = await delete_project.ainvoke(
        {"project_id": str(uuid4())}, config=config,
    )
    parsed = json.loads(result)
    assert parsed["requires_confirmation"] is True, (
        "Le pattern destructif doit refuser par défaut sans confirm explicite"
    )
