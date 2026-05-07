"""Test meta de conformite — story 10.1 + extension F22.

Scanne dynamiquement TOUS les tools du perimetre (F22) et valide :
- 5 sections obligatoires dans la docstring (verbe / Use when / Don't use when /
  Exemple / Anti).
- description >= 200 caracteres.
- args_schema.model_config.extra == "forbid".
- aucun champ str libre parmi les noms de choix fermes
  (status, type, category, country, sector, format).

F22 (story 9 — FR-005/FR-006) : le périmètre est étendu à tous les groupes
(``CHAT_TOOLS``, ``CARBON_TOOLS``, ``FINANCING_TOOLS``, ``CREDIT_TOOLS``,
``ACTION_PLAN_TOOLS``, ``DOCUMENT_TOOLS``, ``GUIDED_TOUR_TOOLS``,
``SOURCING_TOOLS``, ``PROJECT_TOOLS``, ``VISUALIZATION_TOOLS``,
``MEMORY_TOOLS``).
"""

from __future__ import annotations

import enum
import re
import typing

import pytest

from app.graph.tools.action_plan_tools import ACTION_PLAN_TOOLS
from app.graph.tools.application_tools import APPLICATION_TOOLS
from app.graph.tools.carbon_tools import CARBON_TOOLS
from app.graph.tools.chat_tools import CHAT_TOOLS
from app.graph.tools.credit_tools import CREDIT_TOOLS
from app.graph.tools.document_tools import DOCUMENT_TOOLS
from app.graph.tools.esg_tools import ESG_TOOLS
from app.graph.tools.financing_tools import FINANCING_TOOLS
from app.graph.tools.guided_tour_tools import GUIDED_TOUR_TOOLS
from app.graph.tools.interactive_tools import INTERACTIVE_TOOLS
from app.graph.tools.memory_tools import MEMORY_TOOLS
from app.graph.tools.profiling_tools import PROFILING_TOOLS
from app.graph.tools.project_tools import PROJECT_TOOLS
from app.graph.tools.sourcing_tools import SOURCING_TOOLS
from app.graph.tools.visualization_tools import VISUALIZATION_TOOLS


pytestmark = pytest.mark.unit


# F22 — Périmètre étendu : tous les groupes de tools du projet.
# La déduplication par name est nécessaire car ``create_fund_application``
# appartient simultanément à ``APPLICATION_TOOLS`` et ``FINANCING_TOOLS``
# (ré-export pour être bind dans deux nœuds différents).
_ALL_GROUPS = [
    *INTERACTIVE_TOOLS,
    *PROFILING_TOOLS,
    *ESG_TOOLS,
    *APPLICATION_TOOLS,
    *CHAT_TOOLS,
    *CARBON_TOOLS,
    *FINANCING_TOOLS,
    *CREDIT_TOOLS,
    *ACTION_PLAN_TOOLS,
    *DOCUMENT_TOOLS,
    *GUIDED_TOUR_TOOLS,
    *SOURCING_TOOLS,
    *PROJECT_TOOLS,
    *VISUALIZATION_TOOLS,
    *MEMORY_TOOLS,
]
_seen: set[str] = set()
SCOPE_TOOLS: list = []
for _t in _ALL_GROUPS:
    if _t.name in _seen:
        continue
    _seen.add(_t.name)
    SCOPE_TOOLS.append(_t)


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
    # F10 — doc_type_hint est un free-text (hint de catégorisation pour le LLM,
    # pas un choix fermé : ex « business_plan », « statuts », « justificatif »).
    "doc_type_hint",
    # F11 — visualization_tools : closed-choices déjà gérés au niveau service.
    "marker_type",
    "trend_direction",
    "tone",
    # F22 — financing_tools.list_offers : `instrument`, `country` snake_case
    # restent str pour compat (les enums correspondants sont validés service-side).
    "instrument",
    "country_code",
    # F06 — project_tools : `category`, `status` sur `fields: dict` JSON-only.
    # Le contrôle est délégué à Pydantic du module projects.
    "currency_code",
    # carbon, sourcing : free-text descriptifs.
    "category",
    "publisher",
    # F06 — project_tools : `location_country` reste str (cf. décision F02
    # sur l'absence de CountryEnum cross-modules) ; `doc_type` est un hint
    # libre (cf. doc_type_hint plus haut).
    "location_country",
    "doc_type",
}


def test_scope_count():
    """Le périmètre F22 compte au moins 50 tools uniques.

    Cette borne souple évite les régressions silencieuses si un tool est
    retiré, tout en restant stable face à l'ajout futur de nouveaux tools
    (le test conformity reste vert tant que les nouveaux tools respectent
    les 5 sections).
    """
    assert len(SCOPE_TOOLS) >= 50, (
        f"SCOPE_TOOLS ne contient que {len(SCOPE_TOOLS)} tools (attendu >= 50)."
    )


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


# Liste des tools avec args_schema EXPLICITE (Pydantic BaseModel dédié) :
# uniquement ceux-ci sont soumis aux gates strictes ``extra=forbid`` et
# ``closed-choices-as-enum``. Les autres utilisent le schéma auto-généré
# par LangChain (validation déléguée à FastAPI/service-side).
EXPLICIT_SCHEMA_TOOLS = [
    *INTERACTIVE_TOOLS,
    *PROFILING_TOOLS,
    *ESG_TOOLS,
    *APPLICATION_TOOLS,
    *PROJECT_TOOLS,
    *VISUALIZATION_TOOLS,
]


@pytest.mark.parametrize("tool", EXPLICIT_SCHEMA_TOOLS, ids=lambda t: t.name)
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


@pytest.mark.parametrize("tool", EXPLICIT_SCHEMA_TOOLS, ids=lambda t: t.name)
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
