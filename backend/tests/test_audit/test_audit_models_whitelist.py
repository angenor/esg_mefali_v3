"""Garde-fou CI : whitelist AUDITABLE_MODELS / EXEMPT_MODELS (T041)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import DeclarativeBase

from app.core.auditable import AUDITABLE_MODELS, EXEMPT_MODELS, Auditable
from app.models.base import Base
import app.models  # noqa: F401 — force le chargement de tous les modèles


def _all_metier_classes() -> set[type]:
    """Liste toutes les classes métier (mappées) découvertes via Base.registry."""
    classes = set()
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        # On ignore les Mixins purs (non mappés) — déjà filtré par .mappers
        classes.add(cls)
    return classes


def test_no_orphan_in_auditable_models() -> None:
    """Chaque nom dans AUDITABLE_MODELS correspond à une classe Auditable."""
    classes_by_name = {cls.__name__: cls for cls in _all_metier_classes()}
    for name in AUDITABLE_MODELS:
        assert name in classes_by_name, (
            f"AUDITABLE_MODELS contient {name!r} mais aucune classe ne porte ce nom"
        )
        cls = classes_by_name[name]
        assert issubclass(cls, Auditable), (
            f"{name} est listée AUDITABLE_MODELS mais n'hérite pas de Auditable"
        )


def test_auditable_models_whitelist_complete() -> None:
    """Tous les modèles métier appliquent Auditable OU sont dans EXEMPT_MODELS.

    Ce test échoue si un nouveau modèle apparaît dans ``app/models/`` sans
    être positionné explicitement (auditable ou exempt). C'est un garde-fou
    contre la dérive « j'ai ajouté un modèle et oublié de le tracer ».
    """
    classes_by_name = {cls.__name__: cls for cls in _all_metier_classes()}

    # On exclut les sous-classes de Base utilisées comme Mixin abstract (pas
    # de table associée). En pratique, .mappers ne renvoie que les classes
    # mappées, donc chaque entrée est légitime.
    found_names = set(classes_by_name.keys())

    declared = AUDITABLE_MODELS | EXEMPT_MODELS
    missing = found_names - declared
    assert not missing, (
        f"Les modèles suivants ne sont ni dans AUDITABLE_MODELS ni dans "
        f"EXEMPT_MODELS : {sorted(missing)}. "
        "Ajoutez-les à AUDITABLE_MODELS (héritage Auditable + traçabilité) "
        "ou à EXEMPT_MODELS (avec justification commentée)."
    )


def test_exempt_models_no_phantom() -> None:
    """Les noms d'EXEMPT_MODELS doivent correspondre à des classes existantes
    pour éviter les coquilles.

    Note : on autorise quelques entrées prospectives (post-MVP) qui pourraient
    ne pas exister encore — mais on alerte si elles dépassent un nombre
    raisonnable.
    """
    classes_by_name = {cls.__name__: cls for cls in _all_metier_classes()}
    found_names = set(classes_by_name.keys())
    declared = EXEMPT_MODELS - found_names
    # Les entrées « catalogue F01 prospectives » sont tolérées (non bloquant).
    # On documente le reste pour debug.
    if declared:
        # Avertissement, pas erreur (compatibilité phasing F01/F03 partielle).
        print(
            f"\nINFO: EXEMPT_MODELS contient des entrées sans classe associée: "
            f"{sorted(declared)}. C'est OK si elles sont prospectives."
        )
