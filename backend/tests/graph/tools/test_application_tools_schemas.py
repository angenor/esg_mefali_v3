"""Tests unitaires des schemas Pydantic des tools application (story 10.1)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.graph.tools.application_tools import (
    CreateFundApplicationArgs,
    ExportApplicationArgs,
    ExportFormat,
    GenerateApplicationSectionArgs,
    GetApplicationChecklistArgs,
    SimulateFinancingArgs,
    UpdateApplicationSectionArgs,
)


pytestmark = pytest.mark.unit

UUID_OK = str(uuid.uuid4())


def test_create_valid():
    args = CreateFundApplicationArgs(fund_id=UUID_OK)
    assert args.fund_id == UUID_OK


def test_create_with_target_type():
    args = CreateFundApplicationArgs(fund_id=UUID_OK, target_type="fund_direct")
    assert args.target_type.value == "fund_direct"


@pytest.mark.parametrize(
    "field,value",
    [
        ("fund_id", "not-a-uuid"),
        ("fund_id", ""),
        ("target_type", "unknown_route"),
    ],
)
def test_create_invalid(field, value):
    payload = {"fund_id": UUID_OK}
    payload[field] = value
    with pytest.raises(ValidationError):
        CreateFundApplicationArgs(**payload)


def test_create_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        CreateFundApplicationArgs(fund_id=UUID_OK, junk="x")
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_generate_valid():
    args = GenerateApplicationSectionArgs(
        application_id=UUID_OK, section_key="company_presentation",
    )
    assert args.section_key == "company_presentation"


@pytest.mark.parametrize(
    "field,value",
    [
        ("application_id", "bad"),
        ("section_key", "Bad-Key"),
        ("section_key", "1invalid"),
        ("section_key", ""),
        ("instructions", ""),
        ("instructions", "x" * 2001),
    ],
)
def test_generate_invalid(field, value):
    payload = {"application_id": UUID_OK, "section_key": "budget"}
    payload[field] = value
    with pytest.raises(ValidationError):
        GenerateApplicationSectionArgs(**payload)


def test_generate_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        GenerateApplicationSectionArgs(
            application_id=UUID_OK, section_key="budget", junk=1,
        )
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_update_section_valid():
    args = UpdateApplicationSectionArgs(
        application_id=UUID_OK, section_key="budget", content="Mon budget",
    )
    assert args.content == "Mon budget"


@pytest.mark.parametrize(
    "field,value",
    [
        ("section_key", ""),
        ("section_key", "X"),
        ("content", ""),
        ("content", "x" * 50_001),
    ],
)
def test_update_section_invalid(field, value):
    payload = {"application_id": UUID_OK, "section_key": "budget", "content": "ok"}
    payload[field] = value
    with pytest.raises(ValidationError):
        UpdateApplicationSectionArgs(**payload)


def test_update_section_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        UpdateApplicationSectionArgs(
            application_id=UUID_OK, section_key="budget", content="ok", extra=1,
        )
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_checklist_valid():
    args = GetApplicationChecklistArgs(application_id=UUID_OK)
    assert args.application_id == UUID_OK


def test_checklist_invalid_uuid():
    with pytest.raises(ValidationError):
        GetApplicationChecklistArgs(application_id="bad")


def test_checklist_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        GetApplicationChecklistArgs(application_id=UUID_OK, x=1)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_simulate_valid():
    args = SimulateFinancingArgs(application_id=UUID_OK)
    assert args.application_id == UUID_OK


def test_simulate_invalid_uuid():
    with pytest.raises(ValidationError):
        SimulateFinancingArgs(application_id="bad")


def test_simulate_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        SimulateFinancingArgs(application_id=UUID_OK, junk=1)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


@pytest.mark.parametrize("fmt", ["pdf", "docx", "json"])
def test_export_valid_formats(fmt):
    args = ExportApplicationArgs(application_id=UUID_OK, format=fmt)
    assert args.format.value == fmt


@pytest.mark.parametrize("fmt", ["xlsx", "txt", "PDF", ""])
def test_export_invalid_formats(fmt):
    with pytest.raises(ValidationError):
        ExportApplicationArgs(application_id=UUID_OK, format=fmt)


def test_export_invalid_uuid():
    with pytest.raises(ValidationError):
        ExportApplicationArgs(application_id="bad", format="pdf")


def test_export_extra_forbidden():
    with pytest.raises(ValidationError) as exc:
        ExportApplicationArgs(application_id=UUID_OK, format="pdf", junk=1)
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_export_format_enum_exposed():
    assert {f.value for f in ExportFormat} == {"pdf", "docx", "json"}
