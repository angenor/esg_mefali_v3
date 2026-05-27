"""Régression — nettoyage des fences markdown des sections de dossier.

Bug : le LLM enveloppe le HTML d'une section dans ```html … ```, ce qui pollue
la fiche dossier ET les exports PDF/Word. ``strip_code_fences`` retire ces
marqueurs ; appliqué à la génération, au rendu PDF (`_prepare_sections`) et au
rendu Word (`_export_docx`).
"""

from __future__ import annotations

import pytest

from app.modules.applications.export import _prepare_sections, strip_code_fences


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("```html\n<p>Bonjour</p>\n```", "<p>Bonjour</p>"),
        ("```HTML\n<h3>Titre</h3>\n```", "<h3>Titre</h3>"),
        ("```\n<p>X</p>\n```", "<p>X</p>"),
        ("<p>déjà propre</p>", "<p>déjà propre</p>"),
        ("```html\n<p>orpheline ouverture</p>", "<p>orpheline ouverture</p>"),
        ("<p>orpheline fermeture</p>\n```", "<p>orpheline fermeture</p>"),
        ("  ```html\n<p>espaces</p>\n```  ", "<p>espaces</p>"),
    ],
)
def test_strip_code_fences_cases(raw: str, expected: str) -> None:
    assert strip_code_fences(raw) == expected


def test_strip_code_fences_none_and_empty() -> None:
    assert strip_code_fences(None) is None
    assert strip_code_fences("") == ""


def test_strip_code_fences_idempotent() -> None:
    once = strip_code_fences("```html\n<p>X</p>\n```")
    assert strip_code_fences(once) == once == "<p>X</p>"


def test_strip_code_fences_preserves_inner_fenced_code() -> None:
    """Un bloc de code interne (non englobant) n'est pas altéré."""
    content = "<p>Voici du code :</p>\n```python\nx = 1\n```\n<p>fin</p>"
    # Pas de fence englobante → le contenu est conservé tel quel (trim).
    assert strip_code_fences(content) == content


def test_prepare_sections_strips_fences() -> None:
    sections = {
        "intro": {"title": "Intro", "content": "```html\n<p>Contenu</p>\n```", "status": "generated"},
    }
    prepared = _prepare_sections(sections)
    assert prepared[0]["content"] == "<p>Contenu</p>"
