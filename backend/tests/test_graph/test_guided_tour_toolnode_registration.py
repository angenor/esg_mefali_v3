"""Anti-regression : GUIDED_TOUR_TOOLS doit etre enregistre dans les ToolNodes.

Contexte (bug 019-guided-tour-toolnode-missing, 2026-04-15) :
`trigger_guided_tour` etait binde cote LLM (via llm.bind_tools) dans 6 noeuds
mais ABSENT de la liste `tools=` passee au ToolNode via `create_tool_loop`.
Consequence : le LLM emettait bien le tool_call, mais le ToolNode ne trouvait
pas le tool a executer ; au 2e tour LLM (ToolNode → chat_node), le modele
generait un texte hallucinant « l'outil trigger_guided_tour est temporairement
inaccessible / hors service / indisponible ».

Fix : ajouter `GUIDED_TOUR_TOOLS` dans les 6 appels `create_tool_loop` des
noeuds qui bindent le tool cote LLM (chat, esg_scoring, carbon, financing,
credit, action_plan). `application` est exclu : il ne bind pas GUIDED_TOUR_TOOLS
(cf. app/graph/nodes.py application_node).

Ce test verrouille la coherence bind_tools (cote LLM) ↔ ToolNode (cote runtime).
"""

import pytest

from app.graph.graph import build_graph

# Paires (module_name, expected_has_guided_tour) — cote execution ToolNode
_EXPECTED_TOOLNODE_GUIDED = [
    ("chat_tools", True),
    ("esg_scoring_tools", True),
    ("carbon_tools", True),
    ("financing_tools", True),
    ("credit_tools", True),
    ("action_plan_tools", True),
    ("application_tools", False),  # ne bind pas GUIDED_TOUR_TOOLS cote LLM
]


def _tool_names_of_toolnode(graph, toolnode_name: str) -> list[str]:
    """Extraire les noms des tools enregistres dans un (Validating)ToolNode du graphe.

    Story 10.4 : `ToolNode` a ete substitue par `ValidatingToolNode` (composition).
    Quand LangGraph enveloppe un callable instance, il l'expose via `runnable.afunc`.
    On suit donc deux chemins : direct sur `runnable`, ou via `runnable.afunc`/`func`.
    """
    runnable = graph.nodes[toolnode_name].runnable
    candidates = [runnable]
    afunc = getattr(runnable, "afunc", None)
    if afunc is not None:
        candidates.append(afunc)
    func = getattr(runnable, "func", None)
    if func is not None:
        candidates.append(func)

    for node in candidates:
        if hasattr(node, "tools_by_name"):
            return list(node.tools_by_name.keys())
        if hasattr(node, "tools"):
            return [t.name for t in node.tools]
    raise AssertionError(f"ToolNode {toolnode_name} expose ni tools_by_name ni tools")


@pytest.mark.parametrize("toolnode_name,expected_has_guided", _EXPECTED_TOOLNODE_GUIDED)
def test_toolnode_guided_tour_registration(toolnode_name: str, expected_has_guided: bool):
    """Chaque ToolNode qui bind GUIDED_TOUR_TOOLS cote LLM doit aussi l'executer.

    Les 6 noeuds specialises (chat, esg_scoring, carbon, financing, credit,
    action_plan) binding `trigger_guided_tour` cote LLM DOIVENT avoir le tool
    dans leur ToolNode ; sinon le tool_call emis par le LLM echoue et produit
    une hallucination "tool indisponible" au tour suivant.
    """
    graph = build_graph()
    tool_names = _tool_names_of_toolnode(graph, toolnode_name)
    has_guided = "trigger_guided_tour" in tool_names

    if expected_has_guided:
        assert has_guided, (
            f"ToolNode {toolnode_name} ne contient PAS trigger_guided_tour. "
            f"Sans ce tool dans la liste `tools=` du ToolNode, l'executeur ne peut "
            f"pas honorer les tool_calls emis par le LLM (qui le bind via bind_tools) "
            f"— le LLM hallucine ensuite 'outil indisponible' au tour suivant. "
            f"Tools presents : {sorted(tool_names)}"
        )
    else:
        assert not has_guided, (
            f"ToolNode {toolnode_name} contient trigger_guided_tour alors qu'il "
            f"n'est pas cense le binder cote LLM. Incoherence a verifier dans "
            f"graph.py et nodes.py."
        )


def test_bind_tools_matches_toolnode_for_guided_tour():
    """Invariant : si un noeud bind GUIDED_TOUR_TOOLS au LLM, son ToolNode l'execute.

    Couvre tous les noeuds sauf `application` (seul cas ou le tool n'est ni
    binde ni execute, par design : les dossiers de candidature n'utilisent pas
    le guidage visuel).
    """
    graph = build_graph()
    # Les 6 noeuds qui bindent GUIDED_TOUR_TOOLS cote LLM (cf. nodes.py lignes
    # 672, 831, 891, 1066, 1137, 1298). Ils doivent tous avoir le tool dans
    # leur ToolNode respectif.
    for module in ("chat", "esg_scoring", "carbon", "financing", "credit", "action_plan"):
        toolnode_name = f"{module}_tools"
        tool_names = _tool_names_of_toolnode(graph, toolnode_name)
        assert "trigger_guided_tour" in tool_names, (
            f"{module}_node bind GUIDED_TOUR_TOOLS au LLM mais le ToolNode "
            f"{toolnode_name} ne le contient pas. Ajouter GUIDED_TOUR_TOOLS "
            f"dans l'appel create_tool_loop(..., '{module}', ..., tools=...) "
            f"dans app/graph/graph.py."
        )
