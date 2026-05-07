"""F11 — Tests sérialisation Money + UUID dans payloads visualization.

Vérifie que `model_dump(mode='json')` et `model_dump_json()` produisent
un payload conforme aux conventions F04 (Money) et UUID en string.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from app.core.money import Money
from app.schemas.visualization import (
    ComparisonRow,
    ComparisonSubject,
    ComparisonTableArgs,
    ComparisonValue,
    KPICardArgs,
    MapArgs,
    MapMarker,
    MatchCardArgs,
)


class TestKPICardSerialization:
    def test_money_serialized_as_string_amount(self) -> None:
        args = KPICardArgs(
            title="Revenu 2026",
            value="655 957 FCFA",
            value_money=Money(amount=Decimal("655957.50"), currency="XOF"),
        )
        payload = json.loads(args.model_dump_json())
        assert payload["value_money"] == {"amount": "655957.50", "currency": "XOF"}

    def test_uuid_serialized_as_string(self) -> None:
        sid = uuid.uuid4()
        args = KPICardArgs(title="Score", value="72", source_id=sid)
        payload = json.loads(args.model_dump_json())
        assert payload["source_id"] == str(sid)

    def test_optional_fields_none(self) -> None:
        args = KPICardArgs(title="Score", value="72")
        payload = json.loads(args.model_dump_json())
        assert payload["delta"] is None
        assert payload["source_id"] is None


class TestMatchCardSerialization:
    def test_uuid_project_offer(self) -> None:
        pid, oid = uuid.uuid4(), uuid.uuid4()
        args = MatchCardArgs(
            project_id=pid,
            offer_id=oid,
            fund_name="GCF",
            intermediary_name="BOAD",
            compatibility_score=78,
            amount_range="1-5 M",
            timeline="12 mois",
            instruments=["subvention"],
            missing_criteria_count=2,
            drilldown_url="/financing/offers/x",
        )
        payload = json.loads(args.model_dump_json())
        assert payload["project_id"] == str(pid)
        assert payload["offer_id"] == str(oid)


class TestMapSerialization:
    def test_markers_serialization(self) -> None:
        args = MapArgs(
            markers=[
                MapMarker(lat=7.6906, lon=-5.0307, label="Bouaké", type="project"),
            ],
            show_uemoa_overlay=True,
        )
        payload = json.loads(args.model_dump_json())
        assert payload["markers"][0]["lat"] == 7.6906
        assert payload["markers"][0]["type"] == "project"
        assert payload["show_uemoa_overlay"] is True


class TestComparisonSerialization:
    def test_money_in_value(self) -> None:
        args = ComparisonTableArgs(
            title="Comparaison",
            subjects=[
                ComparisonSubject(id="a", label="A"),
                ComparisonSubject(id="b", label="B"),
            ],
            rows=[
                ComparisonRow(
                    label="Frais",
                    type="money",
                    values=[
                        ComparisonValue(
                            subject_id="a",
                            value="500000",
                            money=Money(amount=Decimal("500000.00"), currency="XOF"),
                        ),
                        ComparisonValue(
                            subject_id="b",
                            value="600000",
                            money=Money(amount=Decimal("600000.00"), currency="XOF"),
                        ),
                    ],
                ),
            ],
        )
        payload = json.loads(args.model_dump_json())
        cell_a = payload["rows"][0]["values"][0]
        assert cell_a["money"] == {"amount": "500000.00", "currency": "XOF"}

    def test_source_id_in_cell(self) -> None:
        sid = uuid.uuid4()
        args = ComparisonTableArgs(
            title="X",
            subjects=[
                ComparisonSubject(id="a", label="A"),
                ComparisonSubject(id="b", label="B"),
            ],
            rows=[
                ComparisonRow(
                    label="X",
                    type="text",
                    values=[
                        ComparisonValue(subject_id="a", value="x", source_id=sid),
                        ComparisonValue(subject_id="b", value="y"),
                    ],
                ),
            ],
        )
        payload = json.loads(args.model_dump_json())
        assert payload["rows"][0]["values"][0]["source_id"] == str(sid)
