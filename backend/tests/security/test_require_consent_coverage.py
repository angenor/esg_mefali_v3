"""F05 — Test CI scanner pour vérifier la couverture de ``require_consent``.

Ce test est une garde-fou statique : il scanne les services backend qui
exécutent des traitements non-essentiels (matchant des regex ciblées) et
échoue si une fonction ne contient PAS d'appel à ``require_consent`` (ou
``consent_dependency``).

Approche pragmatique (cf. clarification spec Q7) :
- Regex sur les noms : ``analyze_*``, ``fetch_*_external``,
  ``generate_certificate_*``, ``process_*_sensitive``.
- Pour chaque match, vérifier que le corps contient ``require_consent(``
  OU ``consent_dependency(`` OU est dans la liste ``EXCLUSIONS``.
"""

from __future__ import annotations

import re
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

# Dossiers à scanner.
SCAN_PATHS = [
    BACKEND_DIR / "app" / "services",
    BACKEND_DIR / "app" / "modules",
    BACKEND_DIR / "app" / "graph" / "tools",
]

# Pattern : noms de fonctions concernés.
SENSITIVE_FUNCTION_RE = re.compile(
    r"(?:async\s+)?def\s+("
    r"analyze_[a-z_]+"
    r"|fetch_[a-z_]+_external"
    r"|generate_certificate_[a-z_]+"
    r"|process_[a-z_]+_sensitive"
    r")\s*\("
)

# Pattern : appel au helper.
GUARD_RE = re.compile(r"(?:require_consent|consent_dependency)\(")

# Liste explicite d'exclusions documentées (faux positifs).
# Toute fonction matchant l'un de ces noms est ignorée par le scanner.
EXCLUSIONS: set[str] = {
    # Analyse de score interne (pas de PII externe, pas de Mobile Money) —
    # le gating runtime est déjà fait au niveau du router via Depends.
    "analyze_self_assessed_score",
    # Helpers internes des services ESG/Carbon/Financing — analyse de
    # documents/évaluations utilisateur déjà couverte par les consentements
    # essentiels (granted=true par défaut au registration : profile_analysis
    # et document_analysis_ai).
    "analyze_document_chunks",
    "analyze_extracted_text",
    "analyze_section",
    "analyze_pdf",
    "analyze_summary",
    "analyze_emissions",
    "analyze_carbon_footprint",
    "analyze_esg_criteria",
    "analyze_project_match",
    "analyze_application_dossier",
    "analyze_action_plan",
    "analyze_dashboard_metrics",
    # Document analysis utilise le consentement essentiel
    # ``document_analysis_ai`` (granted=true par défaut au registration).
    # Le gating est appliqué en amont lors de l'upload, pas dans chaque
    # helper d'analyse interne.
    "analyze_document",
    "analyze_uploaded_document",
    # Génération PDF du certificat crédit : fonction utilitaire pure
    # (pas d'accès BDD, pas de PII externe). Le gating
    # ``credit_certificate_generation`` est appliqué dans le service
    # ``app/modules/attestations/service.py::generate_attestation`` (F08)
    # qui appelle cette fonction. Le require_consent est donc fait UPSTREAM.
    "generate_certificate_pdf",
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for base in SCAN_PATHS:
        if not base.exists():
            continue
        files.extend(base.rglob("*.py"))
    return [
        f
        for f in files
        if "__pycache__" not in f.parts
        and "venv" not in f.parts
        and not f.name.startswith("test_")
    ]


def _function_body(content: str, def_start: int) -> str:
    """Extrait le corps d'une fonction à partir de la position du ``def``."""
    lines = content[def_start:].split("\n")
    if not lines:
        return ""
    body_lines: list[str] = []
    for i, line in enumerate(lines):
        if i == 0:
            body_lines.append(line)
            continue
        stripped = line.lstrip()
        if stripped == "":
            body_lines.append(line)
            continue
        if not line.startswith((" ", "\t")):
            break
        body_lines.append(line)
        if len(body_lines) > 200:
            break
    return "\n".join(body_lines)


def test_require_consent_coverage_on_sensitive_services() -> None:
    """Couverture ``require_consent`` sur fonctions matchant les patterns sensibles.

    Toute fonction ``analyze_*|fetch_*_external|generate_certificate_*|process_*_sensitive``
    doit appeler ``require_consent`` ou ``consent_dependency`` (sauf si dans
    la liste ``EXCLUSIONS`` documentée ci-dessus).
    """
    violations: list[str] = []
    for py_file in _iter_python_files():
        content = py_file.read_text(encoding="utf-8")
        for match in SENSITIVE_FUNCTION_RE.finditer(content):
            func_name = match.group(1)
            if func_name in EXCLUSIONS:
                continue
            body = _function_body(content, match.start())
            if not GUARD_RE.search(body):
                violations.append(
                    f"{py_file.relative_to(BACKEND_DIR)}::{func_name}"
                )
    assert not violations, (
        "Fonctions sensibles sans appel à require_consent/consent_dependency :\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nSi le faux positif est intentionnel, ajouter le nom de la "
        "fonction à la liste EXCLUSIONS dans "
        "tests/security/test_require_consent_coverage.py."
    )


def test_consent_helper_module_exists() -> None:
    """Le module ``app/core/consent.py`` expose ``require_consent`` et ``consent_dependency``."""
    target = BACKEND_DIR / "app" / "core" / "consent.py"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "def require_consent" in content
    assert "def consent_dependency" in content
