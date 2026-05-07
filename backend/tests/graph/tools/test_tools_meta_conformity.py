"""Test meta de conformite AC4 — story 10.1.

Scanne dynamiquement les 14 tools du perimetre et valide :
- 5 sections obligatoires dans la docstring (verbe / Use when / Don't use when /
  Exemple / Anti).
- description >= 200 caracteres.
- args_schema.model_config.extra == "forbid".
- aucun champ str libre parmi les noms de choix fermes
  (status, type, category, country, sector, format).
"""

from __future__ import annotations

import enum
import re
import typing

import pytest

from app.graph.tools.application_tools import APPLICATION_TOOLS
from app.graph.tools.esg_tools import ESG_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS


pytestmark = pytest.mark.unit


SCOPE_TOOLS = [
    *INTERACTIVE_TOOLS,
    *PROFILING_TOOLS,
    *ESG_TOOLS,
    *APPLICATION_TOOLS,
]

CLOSED_CHOICE_HINTS = ("_status", "_type", "_category", "country", "sector", "format")
EXEMPT_NAMES = {
    "assessment_id",
    "fund_id",
    "application_id",
    "match_id",
    "intermediary_id",
    "user_id",
    "conversation_id",
    "section_key",
    "criterion_code",
    "company_name",
    "sub_sector",
    # country reste str (CountryEnum non defini dans app/models/, hors scope 10.1)
    "country",
}


def test_scope_count():
    # 14 base + 3 F13 multi-référentiels (finalize_esg_assessment_multi_ref,
    # recompute_score, compare_referentials)
    assert len(SCOPE_TOOLS) == 17


@pytest.mark.parametrize("tool", SCOPE_TOOLS, ids=lambda t: t.name)
def test_description_min_length(tool):
    assert len(tool.description) >= 200, (
        f"{tool.name}: description trop courte ({len(tool.description)} chars)"
    )


@pytest.mark.parametrize("tool", SCOPE_TOOLS, ids=lambda t: t.name)
def test_description_has_5_sections(tool):
    desc = tool.description
    use_when_idx = desc.find("Use when")
    assert use_when_idx > 0, f"{tool.name}: section 'Use when:' manquante"
    verb_phrase = desc[:use_when_idx].strip()
    assert len(verb_phrase) >= 10, f"{tool.name}: verbe d'action trop court"

    for header in ("Use when:", "Don't use when:", "Exemple:", "Anti:"):
        assert header in desc, f"{tool.name}: section '{header}' manquante"

    use_when_block = re.search(r"Use when:\s*\n((?:- .+\n?)+)", desc)
    dont_block = re.search(r"Don't use when:\s*\n((?:- .+\n?)+)", desc)
    assert use_when_block, f"{tool.name}: aucun bullet sous 'Use when:'"
    assert dont_block, f"{tool.name}: aucun bullet sous 'Don't use when:'"
    assert use_when_block.group(1).count("- ") >= 2, (
        f"{tool.name}: Use when doit avoir >= 2 bullets"
    )
    assert dont_block.group(1).count("- ") >= 2, (
        f"{tool.name}: Don't use when doit avoir >= 2 bullets"
    )

    assert "`" in dont_block.group(1), (
        f"{tool.name}: Don't use when doit nommer un tool alternatif (backticks)"
    )


@pytest.mark.parametrize("tool", SCOPE_TOOLS, ids=lambda t: t.name)
def test_args_schema_extra_forbid(tool):
    schema_cls = tool.args_schema
    assert schema_cls is not None, f"{tool.name}: args_schema manquant"
    cfg = schema_cls.model_config
    extra = cfg.get("extra") if isinstance(cfg, dict) else getattr(cfg, "extra", None)
    assert extra == "forbid", (
        f"{tool.name}: args_schema.model_config.extra doit etre 'forbid', got {extra!r}"
    )


def _is_enum_typed(tp) -> bool:
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return True
    args = typing.get_args(tp)
    if not args:
        return False
    return any(isinstance(a, type) and issubclass(a, enum.Enum) for a in args)


@pytest.mark.parametrize("tool", SCOPE_TOOLS, ids=lambda t: t.name)
def test_closed_choices_are_enum(tool):
    schema_cls = tool.args_schema
    fields = schema_cls.model_fields  # type: ignore[attr-defined]
    for name, info in fields.items():
        if name in EXEMPT_NAMES:
            continue
        if not any(hint in name for hint in CLOSED_CHOICE_HINTS):
            continue
        annotation = info.annotation
        assert _is_enum_typed(annotation), (
            f"{tool.name}.{name}: choix ferme doit etre Enum, "
            f"got annotation={annotation!r}"
        )
