"""F21 — Helpers de format de date français pour Jinja2."""

from __future__ import annotations

from datetime import date, datetime


def format_date_fr(value: str | date | datetime | None) -> str:
    """Formater une date (ou ISO string) en `DD/MM/YYYY`.

    Retourne une chaîne vide si ``value`` est ``None`` ou non parseable.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        # Tenter ISO 8601.
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return d.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return value
    return ""


__all__ = ["format_date_fr"]
