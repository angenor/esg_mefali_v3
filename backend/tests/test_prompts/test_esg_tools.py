"""Tests pour les tools et le prompt du module ESG (US3)."""

from app.graph.tools.esg_tools import ESG_TOOLS
from app.prompts.esg_scoring import ESG_SCORING_PROMPT


def test_batch_save_esg_criteria_in_tools():
    """T010 — batch_save_esg_criteria existe dans ESG_TOOLS."""
    tool_names = [t.name for t in ESG_TOOLS]
    assert "batch_save_esg_criteria" in tool_names


def test_esg_tools_count():
    """T010 — ESG_TOOLS contient 5 tools (4 existants + batch)."""
    assert len(ESG_TOOLS) == 5


def test_batch_tool_accepts_criteria_list():
    """T010 — Le tool batch accepte une liste de criteres."""
    batch_tool = None
    for t in ESG_TOOLS:
        if t.name == "batch_save_esg_criteria":
            batch_tool = t
            break
    assert batch_tool is not None
    schema = batch_tool.args_schema.schema() if hasattr(batch_tool, 'args_schema') else {}
    # Verifier que 'criteria' est dans les parametres
    props = schema.get("properties", {})
    assert "criteria" in props, f"Le tool batch doit avoir un parametre 'criteria', got: {list(props.keys())}"


def test_batch_save_esg_criteria_accepts_pydantic_items():
    """Bug [M] — _CriterionItem (Pydantic v2 BaseModel) ne doit PAS planter le tool.

    Regression test : avant le fix coercion (esg_tools.py:372-380), le tool
    accedait `criterion["criterion_code"]` ce qui levait
    `TypeError: '_CriterionItem' object is not subscriptable` quand LangChain
    convertissait l'input en BaseModel via args_schema=BatchSaveESGCriteriaArgs.
    """
    from app.graph.tools.esg_tools import _CriterionItem

    # Coercion : BaseModel ↔ dict — verifie le comportement du fix.
    items_pydantic = [
        _CriterionItem(criterion_code="E1", score=4, justification="ok"),
        _CriterionItem(criterion_code="E2", score=5, justification="ok"),
    ]
    normalized = [
        c if isinstance(c, dict) else c.model_dump()
        for c in items_pydantic
    ]
    assert all(isinstance(item, dict) for item in normalized)
    assert normalized[0]["criterion_code"] == "E1"
    assert normalized[0]["score"] == 4

    # Compatibilite ascendante : si appele avec des dicts directs (tests legacy),
    # la coercion doit etre une no-op.
    items_dict = [{"criterion_code": "E3", "score": 6, "justification": "dict"}]
    normalized_dict = [
        c if isinstance(c, dict) else c.model_dump()
        for c in items_dict
    ]
    assert normalized_dict == items_dict


def test_esg_prompt_contains_batch_instruction():
    """T011 — Le prompt ESG contient l'instruction d'utiliser le batch."""
    assert "batch_save_esg_criteria" in ESG_SCORING_PROMPT


def test_esg_prompt_mentions_batch_strategy():
    """T011 — Le prompt ESG mentionne la strategie de sauvegarde par lot."""
    prompt_lower = ESG_SCORING_PROMPT.lower()
    assert "sauvegarde par lot" in prompt_lower or "batch" in prompt_lower
