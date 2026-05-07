"""F11 — Tests centroïdes UEMOA.

Vérifie la présence des 8 codes ISO3 UEMOA et la cohérence des valeurs lat/lon
dans la bounding box de la zone UEMOA.
"""

from __future__ import annotations

from app.core.visualization_centroids import (
    UEMOA_COUNTRY_CENTROIDS,
    UEMOA_DEFAULT_ZOOM,
    UEMOA_REGION_CENTER,
)


# Bornes UEMOA approximatives (un peu larges pour tolérer la précision Natural Earth)
UEMOA_LAT_MIN = 4.0  # côte ivoirienne sud
UEMOA_LAT_MAX = 25.0  # nord du Mali
UEMOA_LON_MIN = -18.0  # ouest sénégalais
UEMOA_LON_MAX = 16.0  # est nigérien


def test_eight_iso3_codes_present() -> None:
    """Les 8 pays UEMOA sont présents avec leur code ISO3."""
    expected = {"BEN", "BFA", "CIV", "GNB", "MLI", "NER", "SEN", "TGO"}
    assert set(UEMOA_COUNTRY_CENTROIDS.keys()) == expected


def test_each_centroid_in_uemoa_bbox() -> None:
    """Chaque centroïde est dans la bounding box UEMOA."""
    for iso3, (lat, lon) in UEMOA_COUNTRY_CENTROIDS.items():
        assert UEMOA_LAT_MIN <= lat <= UEMOA_LAT_MAX, (
            f"Latitude hors bornes UEMOA pour {iso3} : {lat}"
        )
        assert UEMOA_LON_MIN <= lon <= UEMOA_LON_MAX, (
            f"Longitude hors bornes UEMOA pour {iso3} : {lon}"
        )


def test_centroid_values_are_floats() -> None:
    """Les coordonnées sont des floats (pas des int)."""
    for iso3, coords in UEMOA_COUNTRY_CENTROIDS.items():
        assert isinstance(coords, tuple), iso3
        assert len(coords) == 2, iso3
        assert isinstance(coords[0], float), f"{iso3} lat"
        assert isinstance(coords[1], float), f"{iso3} lon"


def test_uemoa_region_center_in_bbox() -> None:
    """Le centre régional est dans la zone."""
    lat, lon = UEMOA_REGION_CENTER
    assert UEMOA_LAT_MIN <= lat <= UEMOA_LAT_MAX
    assert UEMOA_LON_MIN <= lon <= UEMOA_LON_MAX


def test_default_zoom_within_leaflet_range() -> None:
    """Le zoom par défaut est compris entre 1 et 18 (bornes Leaflet)."""
    assert 1 <= UEMOA_DEFAULT_ZOOM <= 18


def test_specific_centroid_civ() -> None:
    """Côte d'Ivoire centré aux alentours du milieu du pays."""
    lat, lon = UEMOA_COUNTRY_CENTROIDS["CIV"]
    # Approximativement 7.5°N et -5.5°E ± 1°
    assert 6.0 < lat < 9.0
    assert -8.0 < lon < -4.0


def test_specific_centroid_sen() -> None:
    """Sénégal centré aux alentours du milieu du pays."""
    lat, lon = UEMOA_COUNTRY_CENTROIDS["SEN"]
    # Approximativement 14.5°N et -14.5°E ± 1°
    assert 13.0 < lat < 16.0
    assert -16.0 < lon < -13.0
