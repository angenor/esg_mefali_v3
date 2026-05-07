"""Tests de la migration Alembic F17 (T007).

Couvre :
- Le module migration peut etre importe et expose ``upgrade``/``downgrade``.
- ``revision`` et ``down_revision`` sont coherents.
- Les helpers ``_seed_factors_via_orm`` et ``_backfill_carbon_entries``
  existent et sont referencees dans ``upgrade()``.

Note : l'execution Alembic up/down/up reelle est testee via le quickstart
manuel (``alembic upgrade head && alembic downgrade -1 && alembic upgrade head``)
contre PostgreSQL. SQLite ne supporte pas tous les DDL (drop_constraint,
ALTER COLUMN ... NULLABLE, etc.) donc les tests ici se limitent aux invariants
de structure du module.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest


_MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "024_carbone_mix_uemoa.py"
)


def _load_migration_module():
    """Charge le module de migration F17 sans l'enregistrer dans Alembic."""
    spec = importlib.util.spec_from_file_location(
        "_migration_f17", _MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_file_exists() -> None:
    """Le fichier de migration F17 existe."""
    assert _MIGRATION_PATH.exists()


def test_migration_revision_id_is_024() -> None:
    """L'identifiant de revision est ``024_carbone_mix_uemoa``."""
    module = _load_migration_module()
    assert module.revision == "024_carbone_mix_uemoa"


def test_migration_down_revision_is_023() -> None:
    """``down_revision`` pointe vers F12 (``023_create_message_chunks``)."""
    module = _load_migration_module()
    assert module.down_revision == "023_create_message_chunks"


def test_migration_exposes_upgrade_and_downgrade() -> None:
    """Les fonctions ``upgrade`` et ``downgrade`` sont exposees."""
    module = _load_migration_module()
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_uses_seed_factors_helper() -> None:
    """La migration utilise le helper ``_seed_factors_via_orm``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "_seed_factors_via_orm" in content


def test_migration_uses_backfill_helper() -> None:
    """La migration utilise le helper ``_backfill_carbon_entries``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "_backfill_carbon_entries" in content


def test_migration_adds_year_column() -> None:
    """La migration ajoute la colonne ``year`` sur ``emission_factors``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "add_column" in content
    assert '"year"' in content
    assert "Integer" in content


def test_migration_creates_unique_constraint() -> None:
    """La migration cree la contrainte UNIQUE composite."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_unique_constraint" in content
    assert "emission_factors_cat_country_year_uniq" in content


def test_migration_creates_lookup_index() -> None:
    """La migration cree l'index composite ``idx_emission_factors_lookup``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_index" in content
    assert "idx_emission_factors_lookup" in content


def test_migration_adds_source_id_to_carbon_entries() -> None:
    """La migration ajoute ``source_id`` sur ``carbon_emission_entries``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"source_id"' in content
    assert "carbon_emission_entries" in content


def test_migration_adds_factor_id_to_carbon_entries() -> None:
    """La migration ajoute ``factor_id`` sur ``carbon_emission_entries``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"factor_id"' in content


def test_migration_keeps_source_description_legacy() -> None:
    """La migration NE drop PAS ``source_description`` (legacy 2 sprints)."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    # Pas de "drop_column" pour source_description.
    assert 'drop_column("carbon_emission_entries", "source_description")' not in content


def test_backfill_strategy_includes_strict_match() -> None:
    """Le backfill applique d'abord un matching strict ``subcategory`` -> ``code``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    # Verifie le commentaire ET la requete UPDATE par equality.
    assert "subcategory = ef.code" in content


def test_backfill_strategy_includes_prefix_match() -> None:
    """Le backfill applique un fallback par prefix ``subcategory`` LIKE ``code``."""
    content = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "LIKE" in content
    assert "ef.code LIKE" in content


def test_downgrade_does_not_drop_source_description() -> None:
    """Le downgrade NE drop PAS ``source_description`` (legacy 2 sprints)."""
    module = _load_migration_module()
    # Inspect downgrade source code.
    import inspect

    source = inspect.getsource(module.downgrade)
    assert "source_description" not in source or (
        # Soit elle n'apparait pas, soit en tant que commentaire seulement.
        "drop_column" not in source.split("source_description")[0].split("\n")[-1]
    )
