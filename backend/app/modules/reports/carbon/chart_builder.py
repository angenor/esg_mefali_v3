"""F21 — Générateurs SVG pour les graphiques du rapport carbone.

Trois charts :
- Pie chart breakdown par catégorie (énergie/transport/déchets/...).
- Bar chart comparaison sectorielle.
- Line chart évolution multi-années.

Tous les graphiques sont rendus inline (SVG) compatibles WeasyPrint.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CATEGORY_LABELS_FR: dict[str, str] = {
    "energy": "Énergie",
    "transport": "Transport",
    "waste": "Déchets",
    "industrial": "Industriel",
    "agriculture": "Agriculture",
    "purchases": "Achats",
}

# Palette dérivée du thème Mefali (cohérence visuelle F06).
PALETTE: list[str] = [
    "#22c55e",  # vert (energy)
    "#3b82f6",  # bleu (transport)
    "#f59e0b",  # ambre (waste)
    "#a855f7",  # violet (industrial)
    "#ef4444",  # rouge (agriculture)
    "#0ea5e9",  # cyan (purchases)
]


def _fig_to_svg(fig: plt.Figure) -> str:
    """Convertir une figure matplotlib en chaîne SVG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")


def build_breakdown_pie_svg(categories: dict[str, float]) -> str:
    """Pie chart breakdown par catégorie (tCO2e par catégorie).

    Args:
        categories: ``{category_key: tco2e_total}``.
    """
    if not categories:
        return ""
    labels = [CATEGORY_LABELS_FR.get(k, k) for k in categories.keys()]
    values = list(categories.values())
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=PALETTE[: len(values)],
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1},
    )
    ax.set_title("Ventilation des émissions par catégorie", fontsize=12, pad=12)
    return _fig_to_svg(fig)


def build_sector_comparison_bar_svg(
    company_tco2e: float,
    sector_average: float,
    sector_label: str = "Secteur",
) -> str:
    """Bar chart comparaison entreprise vs moyenne sectorielle."""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    labels = ["Votre entreprise", f"Moyenne {sector_label}"]
    values = [company_tco2e, sector_average]
    colors = ["#22c55e" if company_tco2e <= sector_average else "#ef4444", "#94a3b8"]
    bars = ax.barh(labels, values, color=colors)
    ax.set_xlabel("tCO2e", fontsize=10)
    ax.set_title("Comparaison sectorielle", fontsize=12, pad=12)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    for bar, val in zip(bars, values):
        ax.text(
            val,
            bar.get_y() + bar.get_height() / 2,
            f" {val:.1f}",
            va="center",
            fontsize=9,
        )
    return _fig_to_svg(fig)


def build_yearly_line_svg(yearly: list[tuple[int, float]]) -> str:
    """Line chart évolution multi-années.

    Args:
        yearly: liste de tuples ``(year, total_tco2e)`` triés ascendant.
    """
    if not yearly or len(yearly) < 2:
        return ""
    years = [y for y, _ in yearly]
    values = [v for _, v in yearly]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(years, values, marker="o", color="#22c55e", linewidth=2)
    ax.set_xlabel("Année")
    ax.set_ylabel("tCO2e")
    ax.set_title("Évolution annuelle des émissions", fontsize=12, pad=12)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xticks(years)
    return _fig_to_svg(fig)


__all__ = [
    "CATEGORY_LABELS_FR",
    "build_breakdown_pie_svg",
    "build_sector_comparison_bar_svg",
    "build_yearly_line_svg",
]
