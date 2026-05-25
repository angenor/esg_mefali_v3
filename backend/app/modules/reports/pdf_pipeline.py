"""Pipeline mutualisé HTML→PDF pour tous les rapports.

Stratégie en cascade (issue de F047 ESIA-light) :
1. ``WeasyPrint`` quand les libs natives Pango/Cairo sont disponibles.
2. ``reportlab`` en fallback si WeasyPrint est indisponible.
3. Générateur PDF minimal pure-Python en dernier recours.

Utilisé par :
- ``app.modules.esg.project_report`` (F047 — ESIA-light projet)
- ``app.modules.reports.pdf_renderer`` (F05 — ESG entreprise)
- ``app.modules.reports.carbon.pdf_renderer`` (F21 — empreinte carbone)
"""

from __future__ import annotations

import io
import logging
import re
from html import unescape

logger = logging.getLogger(__name__)


# Configuration de mise en page utilisée par les fallbacks PDF.
LEVEL_CONF: dict[str, tuple[str, int, int, int]] = {
    # (font, size, leading, space_before)
    "h1": ("F2", 16, 20, 14),
    "h2": ("F2", 13, 17, 12),
    "h3": ("F2", 11, 14, 8),
    "p": ("F1", 10, 13, 2),
}
_WIDTH_BY_SIZE = {16: 55, 13: 70, 11: 80, 10: 90}


def html_to_pdf_bytes(html: str) -> bytes:
    """Convertir un fragment HTML en bytes PDF.

    Tente WeasyPrint en priorité, puis ``reportlab``, puis un générateur
    pure-Python qui ne dépend d'aucune lib externe. Le résultat reste un
    PDF 1.4 multi-pages avec en-tête ``%PDF`` valide.
    """
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        logger.warning("WeasyPrint indisponible — fallback PDF reportlab.")
        try:
            return _reportlab_fallback_pdf(html)
        except Exception:  # noqa: BLE001
            return _minimal_pdf_bytes(html)


def html_to_structured_text(html: str) -> list[tuple[str, str]]:
    """Convertir l'HTML en suite de blocs ``(kind, text)`` exploitables.

    ``kind`` ∈ {``"h1"``, ``"h2"``, ``"h3"``, ``"p"``}.

    - Retire le contenu de ``<style>``/``<script>``/``<title>`` et les
      commentaires HTML avant le strip.
    - Préserve les sauts de ligne implicites des balises de bloc.
    - Normalise les espaces consécutifs.
    """
    cleaned = re.sub(
        r"<(style|script|title)\b[^>]*>.*?</\1>", " ", html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)

    cleaned = re.sub(
        r"<h1\b[^>]*>(.*?)</h1>", r"\nH1\1\n", cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<h2\b[^>]*>(.*?)</h2>", r"\nH2\1\n", cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<h3\b[^>]*>(.*?)</h3>", r"\nH3\1\n", cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"</?(p|li|tr|div|section|article|br|hr)\b[^>]*>", "\n", cleaned,
        flags=re.IGNORECASE,
    )

    plain = re.sub(r"<[^>]+>", " ", cleaned)
    plain = unescape(plain)

    blocks: list[tuple[str, str]] = []
    for raw in plain.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith("H1"):
            blocks.append(("h1", line[len("H1"):].strip()))
        elif line.startswith("H2"):
            blocks.append(("h2", line[len("H2"):].strip()))
        elif line.startswith("H3"):
            blocks.append(("h3", line[len("H3"):].strip()))
        else:
            blocks.append(("p", line))
    return blocks


def _reportlab_fallback_pdf(html: str) -> bytes:
    """PDF multi-pages lisible via reportlab.

    Titres H1/H2/H3 en gras (16/13/11), paragraphes 10pt, gestion des
    sauts de page, marges A4.
    """
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore
    from reportlab.pdfgen import canvas  # type: ignore

    page_w, page_h = A4
    margin_x, margin_y = 50, 50
    usable_w = page_w - 2 * margin_x

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = page_h - margin_y

    def _new_page() -> float:
        c.showPage()
        return page_h - margin_y

    def _wrap(text: str, font: str, size: float) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            if stringWidth(candidate, font, size) <= usable_w:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def _draw_block(
        text: str, font: str, size: float, leading: float,
        space_before: float, y_pos: float,
    ) -> float:
        y_pos -= space_before
        c.setFont(font, size)
        for line in _wrap(text, font, size):
            if y_pos < margin_y + leading:
                y_pos = _new_page()
                c.setFont(font, size)
            c.drawString(margin_x, y_pos, line)
            y_pos -= leading
        return y_pos

    for kind, text in html_to_structured_text(html):
        if kind == "h1":
            y = _draw_block(text, "Helvetica-Bold", 16, 20, 14, y)
        elif kind == "h2":
            y = _draw_block(text, "Helvetica-Bold", 13, 17, 12, y)
        elif kind == "h3":
            y = _draw_block(text, "Helvetica-Bold", 11, 14, 8, y)
        else:
            y = _draw_block(text, "Helvetica", 10, 13, 2, y)

    c.save()
    return buf.getvalue()


def _pdf_escape(text: str) -> str:
    """Échappe les caractères spéciaux dans une string PDF entre parenthèses."""
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _minimal_pdf_bytes(html: str) -> bytes:
    """PDF 1.4 multi-pages sans dépendance externe.

    Dernier recours quand ni WeasyPrint ni reportlab ne sont disponibles.
    Produit un rapport structuré avec titres H1/H2/H3 en gras + paragraphes
    avec wrap simple à ~90 caractères.
    """
    blocks = html_to_structured_text(html)

    max_line_chars = 90
    page_top = 800   # A4 height (842) - top margin (42)
    page_bottom = 50
    left_margin = 40

    def _wrap(text: str, width: int = max_line_chars) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            if len(candidate) <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                while len(w) > width:
                    lines.append(w[:width])
                    w = w[width:]
                current = w
        if current:
            lines.append(current)
        return lines

    pages: list[list[tuple[str, str, str, int]]] = []
    current_page: list[tuple[str, str, str, int]] = []
    y = page_top

    def _push_line(
        font: str, size: int, text: str, leading: int, space_before: int,
    ) -> None:
        nonlocal y, current_page
        y_after = y - space_before
        if y_after < page_bottom:
            pages.append(current_page)
            current_page = []
            y = page_top
            y_after = y - space_before
        current_page.append((font, str(size), text, y_after))
        y = y_after - leading

    for kind, text in blocks:
        font, size, leading, space_before = LEVEL_CONF.get(kind, LEVEL_CONF["p"])
        wrap_w = _WIDTH_BY_SIZE.get(size, max_line_chars)
        wrapped = _wrap(text, wrap_w)
        for i, line in enumerate(wrapped):
            sb = space_before if i == 0 else 0
            _push_line(font, size, line, leading, sb)

    if current_page:
        pages.append(current_page)

    if not pages:
        pages.append(
            [("F1", "10", "Rapport — contenu indisponible.", page_top)]
        )

    objects: list[bytes] = []

    def _add_obj(body: bytes) -> int:
        idx = len(objects) + 1
        objects.append(f"{idx} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
        return idx

    f1_idx = _add_obj(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    f2_idx = _add_obj(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )

    content_indices: list[int] = []
    for page_lines in pages:
        stream_parts: list[bytes] = [b"BT\n"]
        for font, size, text, y_pos in page_lines:
            escaped = _pdf_escape(text).encode("latin-1", errors="replace")
            stream_parts.append(
                f"/{font} {size} Tf 1 0 0 1 {left_margin} {y_pos} Tm ".encode("ascii")
                + b"(" + escaped + b") Tj\n"
            )
        stream_parts.append(b"ET")
        content_stream = b"".join(stream_parts)
        content_idx = _add_obj(
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\n"
            b"stream\n" + content_stream + b"\nendstream"
        )
        content_indices.append(content_idx)

    next_idx_first_page = len(objects) + 2
    page_refs = " ".join(
        f"{next_idx_first_page + i} 0 R" for i in range(len(content_indices))
    )
    pages_idx = _add_obj(
        f"<< /Type /Pages /Kids [{page_refs}] /Count {len(content_indices)} >>"
        .encode("ascii")
    )
    for content_idx in content_indices:
        _add_obj(
            (
                f"<< /Type /Page /Parent {pages_idx} 0 R "
                f"/MediaBox [0 0 595 842] /Contents {content_idx} 0 R "
                f"/Resources << /Font << /F1 {f1_idx} 0 R /F2 {f2_idx} 0 R >> >> >>"
            ).encode("ascii")
        )
    catalog_idx = _add_obj(
        f"<< /Type /Catalog /Pages {pages_idx} 0 R >>".encode("ascii")
    )

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offset = len(header)
    offsets: list[int] = []
    for obj in objects:
        offsets.append(offset)
        offset += len(obj)
    xref_offset = offset

    body = b"".join(objects)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_idx} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")
    return header + body + xref + trailer


__all__ = [
    "html_to_pdf_bytes",
    "html_to_structured_text",
]
