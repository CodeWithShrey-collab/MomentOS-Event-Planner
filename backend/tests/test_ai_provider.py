"""Mocked Responses API boundary tests; these tests never make a network call."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from openai import APIStatusError, APITimeoutError  # noqa: E402

from momentos.ai_provider import (  # noqa: E402
    AIConfigurationError,
    AIIncomplete,
    AIOutputInvalid,
    AIProviderRateLimit,
    AIProviderTimeout,
    AIRefused,
    OpenAIProvider,
)
from momentos.ai_schemas import EventBrief, EventRequirements, EventType, ExtractionRequest  # noqa: E402


class FakeResponses:
    def __init__(self, response: Any = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.arguments: dict[str, Any] | None = None

    def parse(self, **kwargs):
        self.arguments = kwargs
        if self.error:
            raise self.error
        return self.response

    def create(self, **kwargs):
        self.arguments = kwargs
        if self.error:
            raise self.error
        return self.response


def fake_response(*, status: str = "completed", parsed: Any = None, refusal: bool = False):
    output = []
    if refusal:
        output = [SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="not allowed")])]
    return SimpleNamespace(
        status=status,
        output_text=json.dumps(parsed.model_dump(mode="json") if hasattr(parsed, "model_dump") else parsed) if parsed is not None else ("OK" if status == "completed" and not refusal else ""),
        output=output,
        output_parsed=parsed,
        _request_id="req_test_123",
        usage=SimpleNamespace(input_tokens=120, output_tokens=35, total_tokens=155),
    )


def test_extraction_uses_locked_responses_model_and_validates_structured_output():
    parsed = EventRequirements.model_validate(
        {
            "location_candidate": {
                "value": "Nagpur",
                "source": "user_input",
                "evidence": "Nagpur",
            },
            "unknowns": ["event date"],
        }
    )
    responses = FakeResponses(fake_response(parsed=parsed))
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=responses))

    completion = provider.extract_event_requirements(ExtractionRequest(description="Outdoor wedding in Nagpur"))

    assert completion.data.location_candidate.value == "Nagpur"
    assert completion.usage.model == "gpt-6-luna"
    assert responses.arguments is not None
    assert responses.arguments["model"] == "gpt-6-luna"
    assert responses.arguments["reasoning"] == {"effort": "low"}
    assert responses.arguments["max_output_tokens"] == 700
    assert responses.arguments["store"] is False
    assert responses.arguments["timeout"] == 20.0
    assert "temperature" not in responses.arguments
    assert "top_p" not in responses.arguments


def test_provider_rejects_automatic_model_substitution():
    with pytest.raises(AIConfigurationError, match="exactly gpt-6-luna"):
        OpenAIProvider(api_key="sk-test-only", model="another-model", client=SimpleNamespace(responses=FakeResponses()))


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (fake_response(status="incomplete"), AIIncomplete),
        (fake_response(refusal=True), AIRefused),
        (fake_response(parsed=None), AIOutputInvalid),
    ],
)
def test_provider_maps_incomplete_refusal_and_missing_structured_output(response, error_type):
    provider = OpenAIProvider(
        api_key="sk-test-only",
        client=SimpleNamespace(responses=FakeResponses(response)),
    )

    with pytest.raises(error_type):
        provider.extract_event_requirements(ExtractionRequest(description="Wedding in Nagpur"))


def test_provider_maps_timeout_without_sdk_retry():
    timeout = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    responses = FakeResponses(error=timeout)
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=responses))

    with pytest.raises(AIProviderTimeout):
        provider.extract_event_requirements(ExtractionRequest(description="Wedding in Nagpur"))

    assert responses.arguments["model"] == "gpt-6-luna"


def test_provider_maps_http_429_without_automatic_retry():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(429, request=request, headers={"x-request-id": "req_rate_limit"})
    error = APIStatusError("rate limited", response=response, body={"error": {"message": "private"}})
    responses = FakeResponses(error=error)
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=responses))

    with pytest.raises(AIProviderRateLimit):
        provider.extract_event_requirements(ExtractionRequest(description="Wedding in Nagpur"))

    assert responses.arguments["model"] == "gpt-6-luna"
    assert "temperature" not in responses.arguments


def test_connectivity_check_is_one_low_cost_nonstored_luna_request():
    responses = FakeResponses(fake_response())
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=responses))

    result = provider.connectivity_check()

    assert responses.arguments["model"] == "gpt-6-luna"
    assert responses.arguments["reasoning"] == {"effort": "low"}
    assert responses.arguments["max_output_tokens"] == 128
    assert responses.arguments["store"] is False
    assert responses.arguments["timeout"] == 15.0
    assert "temperature" not in responses.arguments
    assert result.status == "completed"
    assert result.has_visible_output is True
    assert result.input_tokens == 120
    assert result.output_tokens == 35
    assert result.total_tokens == 155


def test_connectivity_check_reports_incomplete_token_cap_without_exposing_output():
    response = fake_response(status="incomplete")
    response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    response.output_text = ""
    responses = FakeResponses(response)
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=responses))

    result = provider.connectivity_check()

    assert result.status == "incomplete"
    assert result.incomplete_reason == "max_output_tokens"
    assert result.has_visible_output is False
    assert result.total_tokens == 155


def blueprint_brief():
    return EventBrief(
        event_type=EventType.BIRTHDAY,
        location_label="Nagpur",
        guest_count=50,
        budget_limit_minor=8_000_000,
        preferences=["good food", "relaxed gathering"],
    )


def minimal_blueprint(**updates):
    value = {
        "concept": {"title":"Garden afternoon", "description":"A relaxed birthday gathering with shared food and music.", "style":"Garden picnic"},
        "assumptions": [], "unknowns": ["Venue capacity"], "budget_categories": [],
        "budget_items": [], "tasks": [], "vendor_categories": [], "ideas": [], "warnings": [],
    }
    value.update(updates)
    return value


def test_valid_blueprint_structured_output_accepts_nullable_optional_values():
    response = fake_response(parsed=minimal_blueprint(
        budget_categories=[{"key":"catering","name":"Food","rationale":"A shared meal.","priority":"high","suggested_share_basis_points":None}],
    ))
    responses = FakeResponses(response)
    provider = OpenAIProvider(
        api_key="sk-test-only",
        max_output_tokens=3_000,
        client=SimpleNamespace(responses=responses),
    )

    result = provider.generate_event_blueprint(blueprint_brief())

    assert result.data.budget_categories[0].suggested_share_basis_points is None
    assert result.usage.model == "gpt-6-luna"
    assert responses.arguments is not None
    output_format = responses.arguments["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert set(output_format["schema"]["required"]) == set(output_format["schema"]["properties"])
    assert responses.arguments["reasoning"] == {"effort": "medium"}
    assert responses.arguments["max_output_tokens"] == 3_000
    assert responses.arguments["store"] is False
    assert "preference_0" in responses.arguments["instructions"]
    assert "Never put user text or a paraphrase in a reference" in responses.arguments["instructions"]
    assert "temperature" not in responses.arguments


@pytest.mark.parametrize("bad_output, expected_path", [
    ({"concept":{"title":"Only title"}}, "concept.description"),
    (minimal_blueprint(concept="not-an-object"), "concept"),
    (minimal_blueprint(budget_categories=[{"key":"food","name":"Food","rationale":"Reason","priority":"urgent","suggested_share_basis_points":None}]), "budget_categories.0.priority"),
])
def test_blueprint_schema_failures_have_safe_field_path_diagnostics(bad_output, expected_path):
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=FakeResponses(fake_response(parsed=bad_output))))

    with pytest.raises(AIOutputInvalid) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics["failure_stage"] == "application_validation"
    assert expected_path in caught.value.diagnostics["validation_paths"]
    assert "Only title" not in str(caught.value.diagnostics)


def test_blueprint_business_validation_classifies_unsupported_references():
    output = minimal_blueprint(ideas=[{"idea":"A custom moment.","personalization_rationale":"Fits.","input_references":["health"]}])
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=FakeResponses(fake_response(parsed=output))))

    with pytest.raises(AIOutputInvalid) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics["validation_categories"] == ["unsupported_context_reference"]
    assert caught.value.diagnostics["validation_paths"] == ["ideas.0.input_references"]


@pytest.mark.parametrize(("unsupported_item", "expected_path"), [
    ({"label": "Extra chairs", "category_key": "venue", "quantity": 99, "rate_minor": None, "estimate_basis": "illustrative", "provenance": "suggestion"}, "budget_items.0.quantity"),
    ({"label": "Extra chairs", "category_key": "venue", "quantity": None, "rate_minor": 999, "estimate_basis": "illustrative", "provenance": "suggestion"}, "budget_items.0.rate_minor"),
])
def test_blueprint_business_validation_rejects_unsupported_numeric_assumptions(unsupported_item, expected_path):
    output = minimal_blueprint(
        budget_categories=[{"key":"venue","name":"Venue","rationale":"A suitable space.","priority":"high","suggested_share_basis_points":None}],
        budget_items=[unsupported_item],
    )
    provider = OpenAIProvider(api_key="sk-test-only", max_output_tokens=3_000, client=SimpleNamespace(responses=FakeResponses(fake_response(parsed=output))))

    with pytest.raises(AIOutputInvalid) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics["validation_categories"] == ["unsupported_numeric_suggestion"]
    assert caught.value.diagnostics["failure_stage"] == "application_validation"
    assert caught.value.diagnostics["validation_paths"] == [expected_path]


def test_blueprint_provider_timeout_is_classified_without_retry():
    timeout = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    responses = FakeResponses(error=timeout)
    provider = OpenAIProvider(api_key="sk-test-only", max_output_tokens=3_000, client=SimpleNamespace(responses=responses))

    with pytest.raises(AIProviderTimeout) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics == {"failure_stage": "network_timeout", "response_status": "no_response"}
    assert responses.arguments["model"] == "gpt-6-luna"
    assert responses.arguments["max_output_tokens"] == 3_000


def test_blueprint_token_limit_incomplete_is_separate_from_invalid_schema():
    response = fake_response(status="incomplete")
    response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    response.output_text = '{"concept":'
    response.usage = SimpleNamespace(input_tokens=1_146, output_tokens=1_800, total_tokens=2_946)
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=FakeResponses(response)))

    with pytest.raises(AIIncomplete) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics["failure_stage"] == "incomplete_response"
    assert caught.value.diagnostics["incomplete_reason"] == "max_output_tokens"
    assert caught.value.diagnostics["output_tokens"] == 1_800
    assert caught.value.diagnostics["total_tokens"] == 2_946


def test_blueprint_refusal_is_detected_before_any_output_parsing():
    response = fake_response(status="completed", refusal=True)
    provider = OpenAIProvider(api_key="sk-test-only", client=SimpleNamespace(responses=FakeResponses(response)))

    with pytest.raises(AIRefused) as caught:
        provider.generate_event_blueprint(blueprint_brief())

    assert caught.value.diagnostics["failure_stage"] == "refusal"
    assert caught.value.diagnostics["refusal"] is True
