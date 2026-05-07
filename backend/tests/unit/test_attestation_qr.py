"""Tests unitaires QR code (F08 — T011)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.attestations.qr import (
    generate_qr_code,
    generate_qr_code_bytes,
)


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_generate_qr_code_creates_png(tmp_path):
    """``generate_qr_code`` crée un PNG valide à ``output_path``."""
    out = tmp_path / "test_qr.png"
    result = generate_qr_code("https://esg-mefali.com/verify/abc-123", out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 100
    with open(out, "rb") as f:
        magic = f.read(8)
    assert magic == PNG_MAGIC


def test_generate_qr_code_creates_parent_dirs(tmp_path):
    """Les dossiers parents inexistants sont créés."""
    out = tmp_path / "nested" / "deep" / "qr.png"
    generate_qr_code("https://example.com/abc", out)
    assert out.exists()
    assert out.parent.is_dir()


def test_generate_qr_code_rejects_empty_url(tmp_path):
    """URL vide → ValueError."""
    with pytest.raises(ValueError, match="vide"):
        generate_qr_code("", tmp_path / "x.png")
    with pytest.raises(ValueError, match="vide"):
        generate_qr_code("   ", tmp_path / "x.png")


def test_generate_qr_code_bytes_returns_png():
    """``generate_qr_code_bytes`` renvoie des bytes PNG."""
    data = generate_qr_code_bytes("https://esg-mefali.com/verify/xyz")
    assert isinstance(data, bytes)
    assert data[:8] == PNG_MAGIC
    assert len(data) > 100


def test_generate_qr_code_bytes_rejects_empty():
    """URL vide → ValueError."""
    with pytest.raises(ValueError):
        generate_qr_code_bytes("")


def test_generate_qr_code_for_different_urls_produces_different_files(tmp_path):
    """Deux URLs distinctes produisent des QR codes différents."""
    out1 = tmp_path / "qr1.png"
    out2 = tmp_path / "qr2.png"
    generate_qr_code("https://esg-mefali.com/verify/abc", out1)
    generate_qr_code("https://esg-mefali.com/verify/xyz", out2)
    assert out1.read_bytes() != out2.read_bytes()
