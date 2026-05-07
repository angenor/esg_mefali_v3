"""F11 — Tests Pydantic stricts pour MapArgs et MapMarker.

TDD strict : ces tests doivent FAIL initialement (avant T010).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.visualization import MapArgs, MapMarker


def _valid_marker(**overrides):
    base = {
        "lat": 7.6906,
        "lon": -5.0307,
        "label": "Site projet Bouaké",
        "type": "project",
    }
    base.update(overrides)
    return base


class TestMapMarkerValidation:
    def test_valid_minimal(self) -> None:
        m = MapMarker(**_valid_marker())
        assert m.lat == 7.6906
        assert m.type == "project"
        assert m.icon is None

    def test_lat_out_of_range_low(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(lat=-91.0))

    def test_lat_out_of_range_high(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(lat=91.0))

    def test_lon_out_of_range_low(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(lon=-181.0))

    def test_lon_out_of_range_high(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(lon=181.0))

    def test_type_enum_strict(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(type="ufo"))  # type: ignore[arg-type]

    def test_type_all_values(self) -> None:
        for t in ("project", "intermediary", "fund_office", "company_hq"):
            m = MapMarker(**_valid_marker(type=t))  # type: ignore[arg-type]
            assert m.type == t

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(boom="x"))

    def test_label_min_length(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(label=""))

    def test_label_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(label="X" * 121))

    def test_popup_content_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(popup_content="<b>" + "x" * 500))

    def test_drilldown_url_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MapMarker(**_valid_marker(drilldown_url="/x" + "a" * 500))


class TestMapArgsValidation:
    def test_valid_minimal(self) -> None:
        args = MapArgs(markers=[MapMarker(**_valid_marker())])
        assert args.zoom == 6  # défaut
        assert args.show_uemoa_overlay is False
        assert len(args.markers) == 1

    def test_markers_empty_rejected(self) -> None:
        """markers vides rejetés (min_length=1)."""
        with pytest.raises(ValidationError):
            MapArgs(markers=[])

    def test_markers_too_many(self) -> None:
        markers = [MapMarker(**_valid_marker()) for _ in range(51)]
        with pytest.raises(ValidationError):
            MapArgs(markers=markers)

    def test_zoom_borne_low(self) -> None:
        with pytest.raises(ValidationError):
            MapArgs(markers=[MapMarker(**_valid_marker())], zoom=0)

    def test_zoom_borne_high(self) -> None:
        with pytest.raises(ValidationError):
            MapArgs(markers=[MapMarker(**_valid_marker())], zoom=19)

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MapArgs(  # type: ignore[call-arg]
                markers=[MapMarker(**_valid_marker())], hallu="x",
            )

    def test_title_max_length(self) -> None:
        with pytest.raises(ValidationError):
            MapArgs(markers=[MapMarker(**_valid_marker())], title="X" * 121)

    def test_center_tuple(self) -> None:
        args = MapArgs(
            markers=[MapMarker(**_valid_marker())],
            center=(12.0, -2.0),
        )
        assert args.center == (12.0, -2.0)

    def test_uemoa_overlay_on(self) -> None:
        args = MapArgs(
            markers=[MapMarker(**_valid_marker())],
            show_uemoa_overlay=True,
        )
        assert args.show_uemoa_overlay is True
