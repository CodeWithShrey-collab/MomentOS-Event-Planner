"""Focused tests for the pure MomentOS domain helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos.domain import (  # noqa: E402
    DomainValidationError,
    calculate_budget,
    calculate_line_amount,
    simulate_ripple,
    topological_task_order,
    validate_task_dependencies,
)


@pytest.fixture
def wedding_snapshot() -> dict:
    """Illustrative Nagpur wedding plan used by the frozen Ripple example."""

    return {
        "event_id": "wedding-demo",
        "version_no": 4,
        "revision": 9,
        "currency": "INR",
        "guest_count": 150,
        "budget_limit_minor": 60_000_000,
        "venue_capacity": 180,
        "seats_per_table": 10,
        "invitation_unit": "unknown",
        "budget_categories": [
            {"id": "venue", "name": "Venue", "planned_minor": 10_000_000},
            {
                "id": "food",
                "name": "Catering",
                "planned_minor": 15_000_000,
                "rate_per_guest_minor": 100_000,
            },
            {"id": "decor", "name": "Decor", "planned_minor": 7_500_000},
            {"id": "photo", "name": "Photography", "planned_minor": 8_500_000},
            {"id": "music", "name": "Music", "planned_minor": 5_000_000},
            {"id": "attire", "name": "Attire", "planned_minor": 6_500_000},
            {"id": "travel", "name": "Travel", "planned_minor": 2_000_000},
            {"id": "reserve", "name": "Reserve", "planned_minor": 3_500_000},
        ],
        "tasks": [
            {"id": "venue-confirm", "status": "not_started", "dependencies": []},
            {
                "id": "catering-tasting",
                "status": "in_progress",
                "category_id": "food",
                "dependencies": ["venue-confirm"],
            },
            {
                "id": "invite-proof",
                "status": "not_started",
                "category_id": "invitations",
                "dependencies": [],
            },
        ],
        "vendors": [{"id": "caterer", "budget_category_id": "food"}],
    }


def test_line_amount_uses_integer_minor_units_and_decimal_half_up() -> None:
    assert calculate_line_amount(3, 101) == 303
    assert calculate_line_amount("2.5", 101) == 253

    with pytest.raises(DomainValidationError, match="float"):
        calculate_line_amount(2.5, 101)  # type: ignore[arg-type]

    with pytest.raises(DomainValidationError):
        calculate_line_amount(2, -1)


def test_budget_keeps_minor_units_and_reports_unknown_amounts() -> None:
    budget = calculate_budget(
        {
            "currency": "INR",
            "guest_count": 150,
            "budget_limit_minor": 60_000_000,
            "budget_categories": [
                {"id": "food", "planned_minor": 15_000_000},
                {"id": "music", "planned_minor": 5_000_000},
            ],
        }
    )
    assert budget["planned_minor"] == 20_000_000
    assert budget["remaining_minor"] == 40_000_000
    assert budget["over_budget_minor"] == 0

    incomplete = calculate_budget(
        {
            "currency": "INR",
            "budget_limit_minor": 1_000,
            "guest_count": None,
            "budget_categories": [{"id": "food", "rate_per_guest_minor": 100}],
        }
    )
    assert incomplete["planned_minor"] is None
    assert incomplete["unknown_category_ids"] == ["food"]


def test_task_graph_has_stable_topological_order_and_rejects_cycles() -> None:
    tasks = [
        {"id": "serve", "dependencies": ["prepare"]},
        {"id": "prepare", "dependencies": []},
        {"id": "invite", "dependencies": []},
    ]
    report = validate_task_dependencies(tasks)
    assert report["valid"] is True
    assert topological_task_order(tasks) == ["invite", "prepare", "serve"]

    cyclic = [
        {"id": "a", "dependencies": ["b"]},
        {"id": "b", "dependencies": ["a"]},
    ]
    cycle_report = validate_task_dependencies(cyclic)
    assert cycle_report["valid"] is False
    assert cycle_report["errors"][0]["code"] == "dependency_cycle"
    with pytest.raises(DomainValidationError, match="directed acyclic"):
        topological_task_order(cyclic)


def test_ripple_wedding_example_is_deterministic_and_never_invents_invites(
    wedding_snapshot: dict,
) -> None:
    preview = simulate_ripple(wedding_snapshot, {"guest_count": 200})
    repeated_preview = simulate_ripple(wedding_snapshot, {"guest_count": 200})

    assert preview["budget_summary"]["before"]["planned_minor"] == 58_000_000
    assert preview["budget_summary"]["after"]["categories"][1]["planned_minor"] == 20_000_000
    assert preview["budget_summary"]["after"]["planned_minor"] == 63_000_000
    # ₹30,000 is 3,000,000 paise; this follows directly from ₹6,30,000 − ₹6,00,000.
    assert preview["budget_summary"]["after"]["over_budget_minor"] == 3_000_000
    assert preview["capacity_summary"]["after"]["required_tables"] == 20
    assert preview["capacity_summary"]["after"]["state"] == "exceeded"
    assert "venue_capacity_exceeded" in {item["code"] for item in preview["blockers"]}
    assert "budget_limit_exceeded" in {item["code"] for item in preview["blockers"]}
    assert preview["invitation_summary"]["quantity"] is None
    assert preview["affected_task_ids"] == ["catering-tasting"]
    assert preview["affected_vendor_ids"] == ["caterer"]
    assert preview["commit_allowed"] is False
    assert preview["preview_hash"] == repeated_preview["preview_hash"]
    assert wedding_snapshot["guest_count"] == 150  # A preview does not mutate its snapshot.


def test_ripple_rejects_unallowlisted_changes(wedding_snapshot: dict) -> None:
    with pytest.raises(DomainValidationError) as error:
        simulate_ripple(wedding_snapshot, {"arbitrary_path": "value"})

    assert error.value.code == "unsupported_field"


def test_guest_count_decrease_recalculates_per_guest_item_and_dependency_totals(wedding_snapshot: dict) -> None:
    snapshot = {
        **wedding_snapshot,
        "budget_items": [{
            "id": "catering-item", "category_id": "food", "label": "Catering per guest",
            "quantity": "150", "quantity_basis": "guest_count", "unit_rate_minor": 100_000,
            "planned_minor": 15_000_000,
        }],
    }

    preview = simulate_ripple(snapshot, {"guest_count": 100})

    assert preview["budget_summary"]["before"]["planned_minor"] == 58_000_000
    assert preview["budget_summary"]["after"]["planned_minor"] == 53_000_000
    assert preview["budget_summary"]["planned_delta_minor"] == -5_000_000
    assert preview["budget_summary"]["after"]["categories"][1]["planned_minor"] == 10_000_000
    assert preview["capacity_summary"]["after"]["required_tables"] == 10
    assert preview["affected_task_ids"] == ["catering-tasting"]
    assert preview["affected_vendor_ids"] == ["caterer"]
    assert snapshot["budget_items"][0]["quantity"] == "150"


def test_ripple_recalculates_item_rate_changes_deterministically(wedding_snapshot: dict) -> None:
    snapshot = {
        **wedding_snapshot,
        "budget_items": [{
            "id": "catering-item", "category_id": "food", "label": "Catering per guest",
            "quantity": "150", "quantity_basis": "guest_count", "unit_rate_minor": 100_000,
            "planned_minor": 15_000_000,
        }],
    }

    preview = simulate_ripple(snapshot, [{
        "target": "budget_item", "target_id": "catering-item", "field": "unit_rate_minor", "value": 110_000,
    }])

    assert preview["budget_summary"]["before"]["planned_minor"] == 58_000_000
    assert preview["budget_summary"]["after"]["planned_minor"] == 59_500_000
    assert preview["budget_summary"]["planned_delta_minor"] == 1_500_000
    assert preview["affected_task_ids"] == ["catering-tasting"]
    assert preview["affected_vendor_ids"] == ["caterer"]


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ({"guest_count": 0}, "out_of_range"),
        ({"guest_count": -1}, "out_of_range"),
        ({"guest_count": 100_001}, "out_of_range"),
        ({"venue_capacity": 100_001}, "out_of_range"),
        ({"seats_per_table": 1_001}, "out_of_range"),
        ({"budget_limit_minor": 2_147_483_648}, "out_of_range"),
    ],
)
def test_ripple_rejects_database_and_domain_numeric_limits(wedding_snapshot: dict, change: dict, expected_code: str) -> None:
    with pytest.raises(DomainValidationError) as error:
        simulate_ripple(wedding_snapshot, change)

    assert error.value.code == expected_code
