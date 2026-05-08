"""Tests unitaires pour app.core.uemoa_capitals."""

import pytest

from app.core.uemoa_capitals import (
    UEMOA_CAPITAL_COORDINATES,
    get_capital_coordinates,
)


class TestUemoaCapitals:
    """Constante UEMOA_CAPITAL_COORDINATES."""

    def test_eight_countries_present_alpha3(self) -> None:
        """Les 8 codes alpha-3 UEMOA sont présents."""
        for code in ("BEN", "BFA", "CIV", "GNB", "MLI", "NER", "SEN", "TGO"):
            assert code in UEMOA_CAPITAL_COORDINATES

    def test_eight_countries_present_alpha2(self) -> None:
        """Les 8 codes alpha-2 UEMOA sont présents."""
        for code in ("BJ", "BF", "CI", "GW", "ML", "NE", "SN", "TG"):
            assert code in UEMOA_CAPITAL_COORDINATES

    def test_coordinates_within_uemoa_bounds(self) -> None:
        """Les coordonnées sont plausibles pour la zone UEMOA (Afrique de l'Ouest)."""
        for code, (lat, lon) in UEMOA_CAPITAL_COORDINATES.items():
            # Latitude UEMOA ~5N à 22N
            assert 4.0 <= lat <= 22.0, f"Latitude hors UEMOA pour {code}: {lat}"
            # Longitude UEMOA ~-18W à 5E
            assert -18.0 <= lon <= 5.0, f"Longitude hors UEMOA pour {code}: {lon}"

    def test_alpha2_alpha3_match(self) -> None:
        """Les coordonnées alpha-2 et alpha-3 d'un même pays sont identiques."""
        pairs = [
            ("BJ", "BEN"), ("BF", "BFA"), ("CI", "CIV"), ("GW", "GNB"),
            ("ML", "MLI"), ("NE", "NER"), ("SN", "SEN"), ("TG", "TGO"),
        ]
        for a2, a3 in pairs:
            assert UEMOA_CAPITAL_COORDINATES[a2] == UEMOA_CAPITAL_COORDINATES[a3]


class TestGetCapitalCoordinates:
    """Fonction helper get_capital_coordinates."""

    def test_returns_tuple_for_known_alpha3(self) -> None:
        result = get_capital_coordinates("SEN")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_tuple_for_known_alpha2(self) -> None:
        result = get_capital_coordinates("SN")
        assert result is not None
        assert isinstance(result, tuple)

    def test_case_insensitive(self) -> None:
        assert get_capital_coordinates("sn") == get_capital_coordinates("SN")
        assert get_capital_coordinates("ben") == get_capital_coordinates("BEN")

    def test_strips_whitespace(self) -> None:
        assert get_capital_coordinates("  SEN  ") == get_capital_coordinates("SEN")

    def test_unknown_country_returns_none(self) -> None:
        assert get_capital_coordinates("USA") is None
        assert get_capital_coordinates("FR") is None
        assert get_capital_coordinates("ZZZ") is None

    def test_empty_or_none_returns_none(self) -> None:
        assert get_capital_coordinates(None) is None
        assert get_capital_coordinates("") is None

    @pytest.mark.parametrize(
        "code,expected_lat,expected_lon",
        [
            ("SEN", 14.7167, -17.4677),
            ("BFA", 12.3714, -1.5197),
            ("CIV", 6.8276, -5.2893),
            ("TGO", 6.1725, 1.2314),
        ],
    )
    def test_specific_capitals(
        self, code: str, expected_lat: float, expected_lon: float
    ) -> None:
        result = get_capital_coordinates(code)
        assert result == (expected_lat, expected_lon)
