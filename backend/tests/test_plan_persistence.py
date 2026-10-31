"""Focused regression coverage for plan input validation boundaries."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos.errors import ApiError
from momentos.services.plans import _parse_datetime, _validate_plan_input


def _event() -> SimpleNamespace:
    return SimpleNamespace(
        current_plan_version_no=2,
        event_type="wedding",
        title="Nagpur Wedding",
        currency="INR",
        budget_limit_minor=60_000_000,
        event_date=None,
        timezone="Asia/Kolkata",
        location_label="Nagpur",
    )


def _plan() -> dict[str, object]:
    return {
        "event_brief": {"guest_count": 150},
        "concept": {},
        "budget_categories": [],
        "budget_items": [],
        "tasks": [],
        "dependencies": [],
        "vendor_categories": [],
        "ideas": [],
        "assumptions": [],
        "unknowns": [],
        "validation": [],
        "ai_status": "live",
    }


def test_plan_context_keeps_validated_event_constraints() -> None:
    context = _validate_plan_input(_event(), _plan(), 2)

    assert context.current_version_no == 2
    assert context.event_type == "wedding"
    assert context.title == "Nagpur Wedding"
    assert context.currency == "INR"
    assert context.budget_limit_minor == 60_000_000
    assert context.guest_count == 150
    assert context.timezone_name == "Asia/Kolkata"


def test_plan_validation_reports_missing_sections_in_stable_order() -> None:
    plan = _plan()
    del plan["tasks"]
    del plan["concept"]

    with pytest.raises(ApiError) as raised:
        _validate_plan_input(_event(), plan, 2)

    assert raised.value.status == 422
    assert raised.value.code == "validation_failed"
    assert [field["path"] for field in raised.value.fields] == ["concept", "tasks"]


@pytest.mark.parametrize(
    ("brief_change", "message"),
    [
        ({"guest_count": True}, "Guest count must be an integer between 1 and 100000."),
        ({"venue_capacity": 0}, "venue_capacity must be an integer between 1 and 100000."),
        ({"seats_per_table": 1001}, "seats_per_table must be an integer between 1 and 1000."),
        ({"title": "   "}, "The event title must contain 1 to 160 characters."),
        ({"timezone": "Not/A_Timezone"}, "Use a valid IANA time zone."),
        ({"currency": "USD"}, "The accepted plan must keep the event type and currency."),
    ],
)
def test_plan_validation_preserves_business_constraint_errors(
    brief_change: dict[str, object], message: str,
) -> None:
    plan = _plan()
    plan["event_brief"] = brief_change

    with pytest.raises(ApiError) as raised:
        _validate_plan_input(_event(), plan, 2)

    assert raised.value.status == 422
    assert raised.value.code == "validation_failed"
    assert raised.value.message == message


def test_plan_version_check_still_precedes_event_brief_validation() -> None:
    plan = _plan()
    plan["event_brief"] = None

    with pytest.raises(ApiError) as raised:
        _validate_plan_input(_event(), plan, 1)

    assert raised.value.status == 412
    assert raised.value.code == "stale_event_version"


def test_iso_utc_designator_remains_timezone_aware() -> None:
    parsed = _parse_datetime("2027-04-10T09:00:00Z")

    assert parsed.isoformat() == "2027-04-10T09:00:00+00:00"
