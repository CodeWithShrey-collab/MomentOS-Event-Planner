"""HTTP API regression tests using an isolated SQLite database and demo AI mode."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos import create_app  # noqa: E402
from momentos import api as api_module  # noqa: E402
from momentos.ai_provider import AIIncomplete, AIUsage  # noqa: E402
from momentos.ai_schemas import CopilotAnswer, EventBlueprint  # noqa: E402
from momentos.extensions import db  # noqa: E402


API = "/api/v1"
ORIGIN = "http://localhost"
WEDDING_BUDGET_MINOR = 60_000_000


@pytest.fixture
def app():
    application = create_app(
        {
            "app_env": "testing",
            "database_url": "sqlite:///:memory:",
            "secret_key": "api-test-secret-with-more-than-thirty-two-characters",
            "ai_mode": "demo",
            "openai_model": "gpt-6-luna",
            "app_base_url": ORIGIN,
            "trusted_origins": ORIGIN,
            "session_cookie_secure": False,
            "rate_limit_storage_uri": "memory://",
        }
    )
    application.config.update(TESTING=True)
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def create_session(client) -> str:
    response = client.post(f"{API}/session")
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["csrf_token"]
    assert data["expires_at"]
    return data["csrf_token"]


def mutation_headers(csrf: str, *, etag: str | None = None, key: str | None = None, origin: str = ORIGIN) -> dict[str, str]:
    headers = {"X-CSRF-Token": csrf, "Origin": origin}
    if etag is not None:
        headers["If-Match"] = etag
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def create_wedding(client, csrf: str):
    response = client.post(
        f"{API}/events",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={
            "event_type": "wedding",
            "title": "Nagpur Wedding",
            "currency": "INR",
            "budget_limit_minor": WEDDING_BUDGET_MINOR,
            "event_date": "2027-04-10",
            "timezone": "Asia/Kolkata",
            "location_label": "Nagpur",
            "guest_count": 150,
            "preferences": {"style": "elegant"},
            "constraints": {},
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"], response.headers["ETag"]


def create_offline_wedding_plan(client, csrf: str, *, include_tasks: bool = True):
    event, draft_etag = create_wedding(client, csrf)
    draft_response = client.post(
        f"{API}/events/{event['id']}/plan-drafts",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={
            "brief": {
                "guest_count": 150,
                "budget_limit_minor": WEDDING_BUDGET_MINOR,
                "location_label": "Nagpur",
                "venue_capacity": 180,
                "seats_per_table": 10,
                "invitation_unit": "unknown",
                "preferences": ["good food", "keep to budget"],
                "constraints": ["illustrative assumptions"],
            }
        },
    )
    assert draft_response.status_code == 200, draft_response.get_json()
    draft = draft_response.get_json()["data"]
    assert draft["ai_status"] == {
        "mode": "offline_demo",
        "generated_by": None,
        "label": "Offline demo plan",
    }


    if not include_tasks:
        draft["tasks"] = []

    # Draft generation is read-only. The event has no accepted plan or new revision yet.
    before_commit = client.get(f"{API}/events/{event['id']}")
    assert before_commit.status_code == 200
    assert before_commit.get_json()["data"]["current_version_no"] is None
    assert before_commit.get_json()["data"]["revision"] == event["revision"]

    commit_response = client.post(
        f"{API}/events/{event['id']}/plan-commits",
        headers=mutation_headers(csrf, etag=draft_etag, key=str(uuid.uuid4())),
        json={"base_version_no": None, "confirmed": True, "plan": draft},
    )
    assert commit_response.status_code == 201, commit_response.get_json()
    return event["id"], commit_response.headers["ETag"], commit_response.get_json()["data"]


def test_live_provider_constructs_the_configured_luna_client(app, monkeypatch) -> None:
    """Live mode must return the configured provider without making a request."""
    from pydantic import SecretStr
    from momentos.config import Settings

    settings = Settings(
        _env_file=None,
        app_env="testing",
        ai_mode="live",
        openai_api_key=SecretStr("test-only-provider-construction"),
        openai_model="gpt-6-luna",
    )
    monkeypatch.setitem(app.extensions, "momentos_settings", settings)
    captured = {}

    class ProviderSentinel:
        pass

    def provider_factory(**kwargs):
        captured.update(kwargs)
        return ProviderSentinel()

    monkeypatch.setattr(api_module, "OpenAIProvider", provider_factory)
    with app.app_context():
        provider = api_module._live_provider()

    assert isinstance(provider, ProviderSentinel)
    assert captured["model"] == "gpt-6-luna"
    assert captured["api_key"] == settings.openai_key
    assert captured["max_output_tokens"] == settings.openai_max_output_tokens
    assert captured["reasoning_effort"] == settings.openai_reasoning_effort


def test_session_creation_issues_opaque_cookie_and_csrf_token(client) -> None:
    response = client.post(f"{API}/session")

    assert response.status_code == 201
    body = response.get_json()
    assert set(body) == {"data", "request_id"}
    assert set(body["data"]) == {"csrf_token", "expires_at"}
    cookie = response.headers["Set-Cookie"]
    assert "momentos_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert body["data"]["csrf_token"] not in cookie

    refreshed = client.get(f"{API}/session")
    assert refreshed.status_code == 200
    assert refreshed.get_json()["data"]["authenticated"] is True
    assert refreshed.get_json()["data"]["csrf_token"]


def test_session_refresh_keeps_csrf_token_valid_across_tabs(client) -> None:
    create_session(client)
    first = client.get(f"{API}/session")
    second = client.get(f"{API}/session")
    first_token = first.get_json()["data"]["csrf_token"]
    second_token = second.get_json()["data"]["csrf_token"]
    assert first.status_code == second.status_code == 200
    assert first_token == second_token

    created = client.post(
        f"{API}/events",
        headers=mutation_headers(first_token, key=str(uuid.uuid4())),
        json={"event_type": "birthday", "title": "CSRF refresh test"},
    )
    assert created.status_code == 201, created.get_json()


def test_development_fallback_secret_supports_guest_sessions() -> None:
    application = create_app(
        {
            "app_env": "testing",
            "database_url": "sqlite:///:memory:",
            "ai_mode": "demo",
            "app_base_url": ORIGIN,
            "trusted_origins": ORIGIN,
            "session_cookie_secure": False,
        }
    )
    application.config.update(TESTING=True)
    try:
        client = application.test_client()
        created = client.post(f"{API}/session")
        assert created.status_code == 201
        csrf = created.get_json()["data"]["csrf_token"]
        refreshed = client.get(f"{API}/session")
        assert refreshed.status_code == 200
        assert refreshed.get_json()["data"]["csrf_token"] == csrf
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_offline_plan_is_explicit_and_requires_commit(client) -> None:
    csrf = create_session(client)
    event_id, etag, result = create_offline_wedding_plan(client, csrf)

    assert result["version_no"] == 1
    assert result["event"]["current_version_no"] == 1
    assert etag.startswith(f'"event:{event_id}:r')
    saved = client.get(f"{API}/events/{event_id}?include=summary")
    assert saved.status_code == 200
    assert saved.get_json()["data"]["summary"]["guest_count"] == 150
    assert saved.get_json()["data"]["summary"]["currency"] == "INR"


def test_mocked_live_blueprint_is_transformed_saved_and_reloaded(app, client, monkeypatch) -> None:
    """A valid typed provider result traverses draft, confirmation, and persistence."""
    app.extensions["momentos_settings"].ai_mode = "live"
    blueprint = EventBlueprint.model_validate({
        "concept": {
            "title": "A joyful afternoon",
            "description": "A relaxed birthday gathering with shared food and time together.",
            "style": "Warm and personal",
        },
        "assumptions": [],
        "unknowns": ["Venue capacity"],
        "budget_categories": [{
            "key": "celebration",
            "name": "Celebration essentials",
            "rationale": "A single editable allocation for the initial plan.",
            "priority": "high",
            "suggested_share_basis_points": 10_000,
        }],
        "budget_items": [],
        "tasks": [{
            "key": "confirm_venue",
            "title": "Confirm venue capacity",
            "rationale": "Check that the venue can host the planned group.",
            "relative_timing_suggestion": "After selecting a venue",
            "phase": "before_event",
            "priority": "high",
            "depends_on_keys": [],
            "owner": None,
            "status": "not_started",
        }],
        "vendor_categories": [],
        "ideas": [],
        "warnings": [],
    })
    usage = AIUsage(
        operation="generate_event_blueprint", model="gpt-6-luna", reasoning_effort="medium",
        status="success", request_id="req_mocked", input_tokens=120, output_tokens=300,
        total_tokens=420, elapsed_ms=20, estimated_cost_usd=Decimal("0"), pricing_version="test",
    )

    class MockProvider:
        provider_mode = "mock"

        def generate_event_blueprint(self, brief):
            assert brief.event_type.value == "birthday"
            assert brief.guest_count == 50
            assert brief.budget_limit_minor == 8_000_000
            return SimpleNamespace(data=blueprint, usage=usage)

    monkeypatch.setattr(api_module, "_live_provider", lambda: MockProvider())
    csrf = create_session(client)
    event_response = client.post(
        f"{API}/events",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={
            "event_type": "birthday", "title": "Nagpur Birthday", "currency": "INR",
            "budget_limit_minor": 8_000_000, "location_label": "Nagpur", "guest_count": 50,
        },
    )
    assert event_response.status_code == 201, event_response.get_json()
    event = event_response.get_json()["data"]
    original_etag = event_response.headers["ETag"]

    draft_response = client.post(
        f"{API}/events/{event['id']}/plan-drafts",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={"brief": {"guest_count": 50, "budget_limit_minor": 8_000_000, "location_label": "Nagpur"}},
    )
    assert draft_response.status_code == 200, draft_response.get_json()
    draft = draft_response.get_json()["data"]
    assert draft["ai_status"] == {"mode": "mock", "generated_by": "Mock Responses API provider (no live OpenAI request)", "model": "gpt-6-luna"}
    assert draft["budget_categories"][0]["planned_minor"] == 8_000_000
    assert draft["tasks"][0]["status"] == "not_started"
    unchanged = client.get(f"{API}/events/{event['id']}?include=summary").get_json()["data"]
    assert unchanged["current_version_no"] is None
    assert unchanged["summary"] is None

    commit_response = client.post(
        f"{API}/events/{event['id']}/plan-commits",
        headers=mutation_headers(csrf, etag=original_etag, key=str(uuid.uuid4())),
        json={"confirmed": True, "base_version_no": None, "plan": draft},
    )
    assert commit_response.status_code == 201, commit_response.get_json()
    saved = client.get(f"{API}/events/{event['id']}?include=summary").get_json()["data"]
    assert saved["current_version_no"] == 1
    assert saved["summary"]["guest_count"] == 50
    assert saved["summary"]["budget_categories"][0]["planned_minor"] == 8_000_000
    assert saved["summary"]["tasks"][0]["title"] == "Confirm venue capacity"


def test_incomplete_live_blueprint_returns_sanitized_recoverable_error(app, client, monkeypatch) -> None:
    app.extensions["momentos_settings"].ai_mode = "live"

    class MockProvider:
        def generate_event_blueprint(self, _brief):
            raise AIIncomplete(
                "internal incomplete detail that must not be returned",
                request_id="req_safe_mock",
                diagnostics={
                    "failure_stage": "incomplete_response",
                    "response_status": "incomplete",
                    "incomplete_reason": "max_output_tokens",
                    "output_tokens": 1_800,
                },
            )

    monkeypatch.setattr(api_module, "_live_provider", lambda: MockProvider())
    csrf = create_session(client)
    event_response = client.post(
        f"{API}/events",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={
            "event_type": "birthday", "title": "Nagpur Birthday", "currency": "INR",
            "budget_limit_minor": 8_000_000, "location_label": "Nagpur", "guest_count": 50,
        },
    )
    event = event_response.get_json()["data"]

    response = client.post(
        f"{API}/events/{event['id']}/plan-drafts",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={"brief": {"guest_count": 50, "budget_limit_minor": 8_000_000, "location_label": "Nagpur"}},
    )

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "ai_incomplete"
    assert "GPT-6 Luna could not complete" in response.get_json()["error"]["message"]
    assert "internal incomplete detail" not in response.get_data(as_text=True)
    unchanged = client.get(f"{API}/events/{event['id']}").get_json()["data"]
    assert unchanged["current_version_no"] is None


def test_event_and_vendor_data_are_isolated_between_sessions(app) -> None:
    owner = app.test_client()
    owner_csrf = create_session(owner)
    # An empty task list isolates this vendor ownership check from the task
    # snapshot cloning defect exercised separately by the task mutation test.
    event_id, etag, _ = create_offline_wedding_plan(owner, owner_csrf, include_tasks=False)
    vendor_response = owner.post(
        f"{API}/events/{event_id}/vendors",
        headers=mutation_headers(owner_csrf, etag=etag, key=str(uuid.uuid4())),
        json={"category": "catering", "display_name": "User-entered caterer", "status": "to_find"},
    )
    assert vendor_response.status_code == 201, vendor_response.get_json()
    vendor_id = vendor_response.get_json()["data"]["logical_id"]
    assert vendor_response.get_json()["data"]["information_source"] == "user_entered"

    stranger = app.test_client()
    stranger_csrf = create_session(stranger)
    assert stranger.get(f"{API}/events/{event_id}").status_code == 404
    assert stranger.get(f"{API}/events/{event_id}/vendors").status_code == 404
    foreign_quote = stranger.post(
        f"{API}/events/{event_id}/vendors/{vendor_id}/quotes",
        headers=mutation_headers(stranger_csrf, etag=vendor_response.headers["ETag"], key=str(uuid.uuid4())),
        json={"amount_minor": 100_000, "currency": "INR", "scope_note": "Foreign access attempt"},
    )
    assert foreign_quote.status_code == 404


@pytest.mark.parametrize(
    ("headers", "expected_code"),
    [
        ({"Origin": ORIGIN}, "csrf_failed"),
        ({"X-CSRF-Token": "not-the-token", "Origin": ORIGIN}, "csrf_failed"),
        ({"Origin": "https://untrusted.example"}, "csrf_failed"),
    ],
)
def test_event_write_rejects_missing_or_invalid_csrf(client, headers, expected_code) -> None:
    create_session(client)
    response = client.post(
        f"{API}/events",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"event_type": "birthday", "title": "Should not be created"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == expected_code


def test_event_write_rejects_untrusted_origin_after_valid_csrf(client) -> None:
    csrf = create_session(client)
    response = client.post(
        f"{API}/events",
        headers=mutation_headers(csrf, key=str(uuid.uuid4()), origin="https://untrusted.example"),
        json={"event_type": "birthday", "title": "Should not be created"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "origin_rejected"


def test_budget_totals_and_task_listing_are_consistent(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf)

    budget = client.get(f"{API}/events/{event_id}/budget")
    assert budget.status_code == 200
    budget_data = budget.get_json()["data"]
    assert budget_data["currency"] == "INR"
    assert budget_data["budget_limit_minor"] == WEDDING_BUDGET_MINOR
    assert budget_data["planned_minor"] == sum(row["planned_minor"] or 0 for row in budget_data["categories"])

    tasks_response = client.get(f"{API}/events/{event_id}/tasks")
    assert tasks_response.status_code == 200
    task_data = tasks_response.get_json()["data"]
    assert len(task_data["items"]) == 4
    assert all(task["status"] == "not_started" for task in task_data["items"])
    assert task_data["topological_order"]
    assert len(task_data["dependencies"]) == 3


def test_copilot_reads_only_the_session_owned_saved_event_context(client) -> None:
    csrf = create_session(client)
    event_id, _, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)

    response = client.post(
        f"{API}/events/{event_id}/copilot",
        headers=mutation_headers(csrf),
        json={"question": "How many guests are planned?", "context_sections": ["budget", "tasks", "vendors", "preferences"]},
    )

    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["ai_status"] == {"mode": "offline_demo", "generated_by": None}
    assert "OpenAI was not called" in data["answer"]
    assert data["budget_analysis"]["saved"] is False


def test_live_copilot_maps_saved_task_and_vendor_states_into_typed_context(app, monkeypatch) -> None:
    client = app.test_client()
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf)
    task_list = client.get(f"{API}/events/{event_id}/tasks").get_json()["data"]["items"]
    task = task_list[0]
    task_update = client.patch(
        f"{API}/events/{event_id}/tasks/{task['logical_id']}",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={"status": "completed"},
    )
    assert task_update.status_code == 200
    vendor = client.get(f"{API}/events/{event_id}/vendors").get_json()["data"]["items"][0]
    vendor_update = client.patch(
        f"{API}/events/{event_id}/vendors/{vendor['logical_id']}",
        headers=mutation_headers(csrf, etag=task_update.headers["ETag"], key=str(uuid.uuid4())),
        json={"status": "contacted_by_user"},
    )
    assert vendor_update.status_code == 200

    app.extensions["momentos_settings"].ai_mode = "live"
    answer = CopilotAnswer.model_validate({
        "answer": "The saved plan has 150 guests.",
        "known_references": ["guest_count"],
        "unknowns": [],
        "suggestions": [],
        "needs_user_confirmation": False,
    })
    usage = AIUsage(
        operation="answer_event_question", model="gpt-6-luna", reasoning_effort="low",
        status="success", request_id="req_mocked", input_tokens=40, output_tokens=20,
        total_tokens=60, elapsed_ms=10, estimated_cost_usd=Decimal("0"), pricing_version="test",
    )

    class MockProvider:
        provider_mode = "mock"

        def answer_event_question(self, request):
            assert request.event_context.guest_count == 150
            assert request.event_context.event_title == "Nagpur Wedding"
            assert any(item.status == "done" for item in request.event_context.task_statuses)
            assert any(item.status == "researching" for item in request.event_context.vendor_categories)
            assert all(item.category_key in {"venue", "catering", "decor", "photography", "entertainment"} for item in request.event_context.vendor_categories)
            return SimpleNamespace(data=answer, usage=usage)

    monkeypatch.setattr(api_module, "_live_provider", lambda: MockProvider())
    response = client.post(
        f"{API}/events/{event_id}/copilot",
        headers=mutation_headers(csrf, key=str(uuid.uuid4())),
        json={"question": "How many guests are planned?", "context_sections": ["budget", "tasks", "vendors", "preferences"]},
    )

    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]
    assert result["answer"] == "The saved plan has 150 guests."
    assert result["known_references"] == ["guest_count"]
    assert result["ai_status"] == {"mode": "mock", "generated_by": "Mock Responses API provider (no live OpenAI request)", "model": "gpt-6-luna"}


def test_task_creation_and_completion_are_versioned(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf)
    tasks = client.get(f"{API}/events/{event_id}/tasks").get_json()["data"]["items"]
    venue_task = next(task for task in tasks if task["title"] == "Confirm venue requirements")
    added = client.post(
        f"{API}/events/{event_id}/tasks",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={"title": "Book catering tasting", "depends_on_task_ids": [venue_task["logical_id"]]},
    )
    assert added.status_code == 201, added.get_json()
    added_task = added.get_json()["data"]
    assert added_task["status"] == "not_started"
    assert venue_task["logical_id"] in added_task["dependencies"]

    completed = client.patch(
        f"{API}/events/{event_id}/tasks/{added_task['logical_id']}",
        headers=mutation_headers(csrf, etag=added.headers["ETag"], key=str(uuid.uuid4())),
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.get_json()
    completed_task = completed.get_json()["data"]
    assert completed_task["status"] == "completed"
    assert completed_task["completion_source"] == "user"
    assert completed_task["completed_by_session_id"]
    assert completed.headers["ETag"] != etag


def test_stale_event_etag_cannot_overwrite_a_newer_revision(client) -> None:
    csrf = create_session(client)
    event_id, original_etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)

    updated = client.patch(
        f"{API}/events/{event_id}",
        headers=mutation_headers(csrf, etag=original_etag, key=str(uuid.uuid4())),
        json={"title": "Updated Nagpur Wedding"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.headers["ETag"] != original_etag

    stale = client.patch(
        f"{API}/events/{event_id}",
        headers=mutation_headers(csrf, etag=original_etag, key=str(uuid.uuid4())),
        json={"title": "Stale overwrite"},
    )
    assert stale.status_code == 412
    assert stale.get_json()["error"]["code"] == "stale_event_version"
    assert client.get(f"{API}/events/{event_id}").get_json()["data"]["title"] == "Updated Nagpur Wedding"


def test_ripple_preview_is_not_persisted_and_commit_replays_idempotently(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)
    before = client.get(f"{API}/events/{event_id}").get_json()["data"]
    preview = client.post(
        f"{API}/events/{event_id}/ripple-previews",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={
            "base_version_no": before["current_version_no"],
            "changes": [
                {"target": "event", "target_id": None, "field": "budget_limit_minor", "value": 70_000_000}
            ],
        },
    )
    assert preview.status_code == 201, preview.get_json()
    preview_data = preview.get_json()["data"]
    assert preview_data["commit_allowed"] is True
    assert preview_data["status"] == "ready"

    after_preview = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert after_preview["current_version_no"] == before["current_version_no"]
    assert after_preview["revision"] == before["revision"]
    assert after_preview["budget_limit_minor"] == WEDDING_BUDGET_MINOR

    key = str(uuid.uuid4())
    commit_headers = mutation_headers(csrf, etag=etag, key=key)
    commit_body = {"confirmed": True, "acknowledged_warning_codes": []}
    committed = client.post(
        f"{API}/events/{event_id}/ripple-previews/{preview_data['simulation_id']}/commit",
        headers=commit_headers,
        json=commit_body,
    )
    assert committed.status_code == 200, committed.get_json()
    committed_data = committed.get_json()["data"]
    assert committed_data["version_no"] == before["current_version_no"] + 1

    replayed = client.post(
        f"{API}/events/{event_id}/ripple-previews/{preview_data['simulation_id']}/commit",
        headers=commit_headers,
        json=commit_body,
    )
    assert replayed.status_code == 200
    assert replayed.headers["ETag"] == committed.headers["ETag"]
    assert replayed.get_json()["data"]["version_no"] == committed_data["version_no"]

    duplicate_with_new_key = client.post(
        f"{API}/events/{event_id}/ripple-previews/{preview_data['simulation_id']}/commit",
        headers=mutation_headers(csrf, etag=committed.headers["ETag"], key=str(uuid.uuid4())),
        json=commit_body,
    )
    assert duplicate_with_new_key.status_code == 409
    assert duplicate_with_new_key.get_json()["error"]["code"] == "domain_conflict"

    saved = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert saved["current_version_no"] == committed_data["version_no"]
    assert saved["budget_limit_minor"] == 70_000_000


def test_ripple_cancel_marks_preview_unused_without_mutating_event(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)
    before = client.get(f"{API}/events/{event_id}").get_json()["data"]
    preview = client.post(
        f"{API}/events/{event_id}/ripple-previews",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={
            "base_version_no": before["current_version_no"],
            "changes": [{"target": "event", "field": "budget_limit_minor", "value": 70_000_000}],
        },
    )
    assert preview.status_code == 201, preview.get_json()
    simulation_id = preview.get_json()["data"]["simulation_id"]

    cancelled = client.post(
        f"{API}/events/{event_id}/ripple-previews/{simulation_id}/cancel",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={"confirmed": False},
    )
    assert cancelled.status_code == 200, cancelled.get_json()
    assert cancelled.get_json()["data"]["status"] == "cancelled"
    assert client.get(f"{API}/events/{event_id}/ripple-previews/{simulation_id}").get_json()["data"]["status"] == "cancelled"
    after = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert after["current_version_no"] == before["current_version_no"]
    assert after["revision"] == before["revision"]
    assert after["budget_limit_minor"] == before["budget_limit_minor"]


def test_ripple_preview_rejects_a_competing_event_version(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)
    before = client.get(f"{API}/events/{event_id}").get_json()["data"]
    preview = client.post(
        f"{API}/events/{event_id}/ripple-previews",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={
            "base_version_no": before["current_version_no"],
            "changes": [{"target": "event", "field": "budget_limit_minor", "value": 70_000_000}],
        },
    )
    assert preview.status_code == 201, preview.get_json()
    simulation_id = preview.get_json()["data"]["simulation_id"]

    competing_edit = client.patch(
        f"{API}/events/{event_id}",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={"title": "Edited after the preview"},
    )
    assert competing_edit.status_code == 200, competing_edit.get_json()
    stale_commit = client.post(
        f"{API}/events/{event_id}/ripple-previews/{simulation_id}/commit",
        headers=mutation_headers(csrf, etag=competing_edit.headers["ETag"], key=str(uuid.uuid4())),
        json={"confirmed": True, "acknowledged_warning_codes": []},
    )
    assert stale_commit.status_code == 412
    assert stale_commit.get_json()["error"]["code"] == "stale_simulation"
    after = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert after["title"] == "Edited after the preview"
    assert after["budget_limit_minor"] == WEDDING_BUDGET_MINOR
    assert after["current_version_no"] == before["current_version_no"] + 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("guest_count", 0), ("guest_count", 100_001), ("venue_capacity", 100_001),
     ("seats_per_table", 1_001), ("budget_limit_minor", 2_147_483_648)],
)
def test_ripple_api_rejects_out_of_range_values_without_mutation(client, field: str, value: int) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)
    before = client.get(f"{API}/events/{event_id}").get_json()["data"]
    response = client.post(
        f"{API}/events/{event_id}/ripple-previews",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={
            "base_version_no": before["current_version_no"],
            "changes": [{"target": "event", "field": field, "value": value}],
        },
    )
    assert response.status_code == 422, response.get_json()
    assert response.get_json()["error"]["code"] == "validation_failed"
    after = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert after["current_version_no"] == before["current_version_no"]
    assert after["revision"] == before["revision"]


def test_ripple_hard_capacity_blocker_rolls_back_confirmation(client) -> None:
    csrf = create_session(client)
    event_id, etag, _ = create_offline_wedding_plan(client, csrf, include_tasks=False)
    before = client.get(f"{API}/events/{event_id}").get_json()["data"]

    preview = client.post(
        f"{API}/events/{event_id}/ripple-previews",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={
            "base_version_no": before["current_version_no"],
            "changes": [{"target": "event", "target_id": None, "field": "guest_count", "value": 200}],
        },
    )
    assert preview.status_code == 201, preview.get_json()
    preview_data = preview.get_json()["data"]
    assert preview_data["commit_allowed"] is False
    assert any(row["code"] == "venue_capacity_exceeded" for row in preview_data["blockers"])

    attempted = client.post(
        f"{API}/events/{event_id}/ripple-previews/{preview_data['simulation_id']}/commit",
        headers=mutation_headers(csrf, etag=etag, key=str(uuid.uuid4())),
        json={"confirmed": True, "acknowledged_warning_codes": []},
    )
    assert attempted.status_code == 409
    assert attempted.get_json()["error"]["code"] == "hard_constraint_violation"

    after = client.get(f"{API}/events/{event_id}").get_json()["data"]
    assert after["revision"] == before["revision"]
    assert after["current_version_no"] == before["current_version_no"]
    assert after["draft_fields"]["guest_count"] == 150
