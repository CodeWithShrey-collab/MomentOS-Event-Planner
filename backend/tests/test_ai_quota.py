"""Per-session AI quota and successful-response idempotency tests."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from momentos import create_app  # noqa: E402
from momentos.ai_provider import AICompletion, AIUsage  # noqa: E402
from momentos.ai_schemas import EventRequirements  # noqa: E402
from momentos.extensions import db  # noqa: E402
from momentos.models import AIQuotaBucket, AIUsageRecord  # noqa: E402


API = "/api/v1"
ORIGIN = "http://localhost"


@pytest.fixture
def app():
    application = create_app(
        {
            "app_env": "testing",
            "database_url": "sqlite:///:memory:",
            "secret_key": "quota-tests-have-a-long-random-looking-test-secret",
            "ai_mode": "live",
            "openai_api_key": "sk-test-only",
            "ai_daily_request_limit": 1,
            "app_base_url": ORIGIN,
            "trusted_origins": ORIGIN,
            "session_cookie_secure": False,
        }
    )
    application.config.update(TESTING=True)
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def extract_event_requirements(self, _request):
        self.calls += 1
        return AICompletion(
            data=EventRequirements(unknowns=["event date"]),
            usage=AIUsage(
                operation="extract_event_requirements",
                model="gpt-6-luna",
                reasoning_effort="low",
                status="completed",
                request_id="req_mocked",
                input_tokens=25,
                output_tokens=10,
                total_tokens=35,
                elapsed_ms=1,
                estimated_cost_usd=None,
                pricing_version=None,
            ),
        )


def test_daily_quota_reserves_atomically_and_same_key_replays_without_provider_call(app, monkeypatch):
    from momentos import api as api_module

    provider = FakeProvider()
    monkeypatch.setattr(api_module, "_live_provider", lambda: provider)
    client = app.test_client()
    session = client.post(f"{API}/session")
    csrf = session.get_json()["data"]["csrf_token"]
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid.uuid4())}
    event = client.post(
        f"{API}/events",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"event_type": "wedding", "title": "Quota test"},
    )
    assert event.status_code == 201, event.get_json()
    event_id = event.get_json()["data"]["id"]

    request_headers = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    body = {"description": "An outdoor wedding in Nagpur."}
    first = client.post(f"{API}/events/{event_id}/intake", headers=request_headers, json=body)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()["data"]["ai_status"]["model"] == "gpt-6-luna"
    assert provider.calls == 1

    replay = client.post(f"{API}/events/{event_id}/intake", headers=request_headers, json=body)
    assert replay.status_code == 200
    assert replay.get_json() == first.get_json()
    assert provider.calls == 1

    conflicting = client.post(
        f"{API}/events/{event_id}/intake",
        headers=request_headers,
        json={"description": "A birthday in Nagpur."},
    )
    assert conflicting.status_code == 409
    assert conflicting.get_json()["error"]["code"] == "idempotency_conflict"

    over_limit = client.post(
        f"{API}/events/{event_id}/intake",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert over_limit.status_code == 429
    assert over_limit.get_json()["error"]["code"] == "rate_limited"
    assert provider.calls == 1

    with app.app_context():
        bucket = db.session.query(AIQuotaBucket).one()
        usage = db.session.query(AIUsageRecord).one()
        assert bucket.reserved_count == 1
        assert usage.status == "success"
        assert usage.model_id == "gpt-6-luna"
