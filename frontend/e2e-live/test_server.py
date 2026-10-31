"""Isolated Flask API using valid mocked Responses results for browser tests."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from flask import jsonify  # noqa: E402
from momentos import create_app  # noqa: E402
from momentos.ai_provider import AIUsage, OpenAIProvider  # noqa: E402
from momentos.ai_schemas import (  # noqa: E402
    CopilotAnswer,
    EventBlueprint,
    RippleExplanation,
)


app = create_app(
    {
        "app_env": "testing",
        "database_url": "sqlite:///:memory:",
        "secret_key": "stage-07-playwright-isolated-test-secret",
        "ai_mode": "live",
        # Harmless local placeholder: the test factory below is injected and
        # no OpenAI client/request is constructed by this server.
        "openai_api_key": "playwright-mock-provider-only",
        "openai_model": "gpt-6-luna",
        "app_base_url": "http://127.0.0.1:4174",
        "trusted_origins": "http://127.0.0.1:4174",
        "session_cookie_secure": False,
        "rate_limit_storage_uri": "memory://",
    }
)
app.extensions["stage07_mock_ai_calls"] = []


def usage(operation: str, effort: str) -> AIUsage:
    return AIUsage(
        operation=operation,
        model="gpt-6-luna",
        reasoning_effort=effort,
        status="success",
        request_id=f"req_stage07_{operation}",
        input_tokens=320,
        output_tokens=180,
        total_tokens=500,
        elapsed_ms=2,
        estimated_cost_usd=Decimal("0"),
        pricing_version="stage07-mock-no-charge",
    )


class MockResponsesProvider:
    provider_mode = "mock"

    def _record(self, operation: str, context_fields: list[str] | None = None, known_facts: list[str] | None = None) -> None:
        app.extensions["stage07_mock_ai_calls"].append(
            {"operation": operation, "context_fields": context_fields or [], "known_fact_fields": known_facts or []}
        )

    def generate_event_blueprint(self, brief):
        self._record("generate_event_blueprint")
        result = EventBlueprint.model_validate(
            {
                "concept": {
                    "title": "A garden wedding with room to gather",
                    "description": "A warm, considered celebration with a shared meal and an easy flow between moments.",
                    "style": "Garden editorial",
                },
                "assumptions": ["The catering amount is an editable user-provided planning assumption."],
                "unknowns": ["Venue capacity and supplier quotations must be confirmed."],
                "budget_categories": [
                    {"key": "venue", "name": "Venue", "rationale": "A comfortable space for the gathering.", "priority": "high", "suggested_share_basis_points": 2_000},
                    {"key": "catering", "name": "Catering", "rationale": "A shared meal scaled to attendance.", "priority": "high", "suggested_share_basis_points": 2_500},
                    {"key": "decor", "name": "Flowers & decor", "rationale": "A light visual treatment.", "priority": "medium", "suggested_share_basis_points": 1_000},
                    {"key": "photography", "name": "Photography", "rationale": "Capture key moments.", "priority": "medium", "suggested_share_basis_points": 1_000},
                    {"key": "entertainment", "name": "Music", "rationale": "A considered sound plan.", "priority": "medium", "suggested_share_basis_points": 1_000},
                ],
                "budget_items": [
                    {
                        "label": "Catering per guest",
                        "category_key": "catering",
                        "quantity": brief.guest_count,
                        "rate_minor": 100_000,
                        "quantity_basis": "guest_count",
                        "estimate_basis": "user_supplied",
                        "provenance": "user_input",
                    }
                ],
                "tasks": [
                    {"key": "confirm_venue", "title": "Confirm venue capacity", "rationale": "Check access and capacity with the venue.", "relative_timing_suggestion": "Before invitations", "phase": "before_event", "priority": "high", "depends_on_keys": [], "owner": None, "status": "not_started"},
                    {"key": "confirm_catering", "title": "Confirm catering requirements", "rationale": "Confirm menu, dietaries, and service.", "relative_timing_suggestion": "After venue selection", "phase": "before_event", "priority": "high", "depends_on_keys": ["confirm_venue"], "owner": None, "status": "not_started"},
                    {"key": "prepare_run_of_show", "title": "Prepare the event-day timeline", "rationale": "Set the sequence for arrivals and key moments.", "relative_timing_suggestion": "In the final planning week", "phase": "event_day", "priority": "medium", "depends_on_keys": ["confirm_venue"], "owner": None, "status": "not_started"},
                ],
                "vendor_categories": [
                    {"key": key, "category": category, "why": f"Illustrative {category.lower()} checklist category.", "follow_up_checklist": ["Record the contact and user-entered quotation."]}
                    for key, category in [("venue", "Venue"), ("catering", "Catering"), ("decor", "Flowers and decor"), ("photography", "Photography"), ("entertainment", "Music")]
                ],
                "ideas": [{"idea": "Use a shared table as the visual and social centre of the celebration.", "personalization_rationale": "A broad, editable idea for a gathering built around a meal.", "input_references": ["general"]}],
                "warnings": [],
            }
        )
        OpenAIProvider._validate_domain("generate_event_blueprint", brief, result)
        return SimpleNamespace(data=result, usage=usage("generate_event_blueprint", "medium"))

    def explain_ripple_impact(self, request):
        self._record("explain_ripple_results")
        result = RippleExplanation.model_validate(
            {
                "summary": "The proposed attendance change updates the linked catering estimate and may affect venue capacity.",
                "causal_steps": [],
                "options": [],
                "unknowns": ["The venue's current capacity has not been verified."],
            }
        )
        OpenAIProvider._validate_domain("explain_ripple_results", request, result)
        return SimpleNamespace(data=result, usage=usage("explain_ripple_results", "low"))

    def answer_event_question(self, request):
        context = request.event_context
        dumped = context.model_dump(mode="json", exclude_none=True)
        self._record("answer_event_question", sorted(dumped.keys()), [fact.field for fact in context.facts])
        # MinimalEventContext is strict and allowlisted. These assertions make
        # accidental forwarding of free-form notes/vendor contact data fail.
        assert "notes" not in dumped and "email" not in dumped and "phone" not in dumped
        result = CopilotAnswer.model_validate(
            {
                "answer": f"The saved plan is for {context.guest_count} guests.",
                "known_references": ["guest_count"],
                "unknowns": [],
                "suggestions": [],
                "needs_user_confirmation": False,
            }
        )
        OpenAIProvider._validate_domain("answer_event_question", request, result)
        return SimpleNamespace(data=result, usage=usage("answer_event_question", "low"))


app.extensions["momentos_ai_provider_factory"] = MockResponsesProvider


@app.get("/__test__/ai-calls")
def test_ai_call_observations():
    # Test-only metadata endpoint; no prompts or event values are exposed.
    return jsonify(app.extensions["stage07_mock_ai_calls"])


port = int(os.environ.get("MOMENTOS_LIVE_TEST_PORT", "5002"))
app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
