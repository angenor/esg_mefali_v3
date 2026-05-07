"""Génération de QR codes PNG pour les attestations (F08 — T019).

Utilise ``segno`` (lightweight, pas de Pillow obligatoire) avec
``error="M"`` (15 % récupération, idéal pour QR scanné depuis PDF imprimé)
et ``scale=10`` (300x300 px environ).

API :

- :func:`generate_qr_code` — produit un PNG sur disque, retourne le chemin.
"""

from __future__ import annotations

import logging
from pathlib import Path

import segno

logger = logging.getLogger(__name__)

# Constantes (extractibles en config si besoin post-MVP).
QR_ERROR_LEVEL = "M"  # Récupération moyenne (15 %).
QR_SCALE = 10  # Module size en pixels (10 → ~300x300 px pour URL ~50 chars).


def generate_qr_code(verification_url: str, output_path: Path) -> Path:
    """Génère un QR code PNG pointant vers ``verification_url`` à ``output_path``.

    Crée les dossiers parents si nécessaire. Renvoie le chemin final.

    :param verification_url: URL complète encodée dans le QR.
    :param output_path: Chemin de destination du fichier PNG.
    :raises ValueError: si ``verification_url`` est vide.
    """
    if not verification_url or not verification_url.strip():
        raise ValueError("verification_url ne peut pas être vide")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    qr = segno.make(verification_url, error=QR_ERROR_LEVEL)
    # ``segno`` accepte des kwargs pour le rendu PNG : scale, dark, light, border.
    qr.save(
        str(output_path),
        scale=QR_SCALE,
        dark="black",
        light="white",
        border=2,
    )

    logger.info(
        "QR code généré : url=%s path=%s size_bytes=%d",
        verification_url,
        output_path,
        output_path.stat().st_size,
    )
    return output_path


def generate_qr_code_bytes(verification_url: str) -> bytes:
    """Génère un QR code PNG en mémoire (pas d'écriture disque).

    Utilisé par le PDF builder pour embarquer directement le QR en base64
    sans aller-retour disque.
    """
    if not verification_url or not verification_url.strip():
        raise ValueError("verification_url ne peut pas être vide")

    import io

    buffer = io.BytesIO()
    qr = segno.make(verification_url, error=QR_ERROR_LEVEL)
    qr.save(buffer, kind="png", scale=QR_SCALE, dark="black", light="white", border=2)
    return buffer.getvalue()
