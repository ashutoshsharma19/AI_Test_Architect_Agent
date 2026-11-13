import pytest

from agents.evaluation_agent import EvaluationAgent
from utils import llm
from utils.normalizer import _to_score, normalize_state
from utils.vector_store import fallback_duplicate_detection, find_duplicate_test_cases


@pytest.mark.parametrize("text", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}\n```',
    'Here you go:\n{"a": 1}\nThanks!',
])
def test_parse_json_response_tolerates_wrappers(text):
    assert llm.parse_json_response(text) == {"a": 1}


def test_parse_json_response_rejects_non_objects():
    with pytest.raises(ValueError):
        llm.parse_json_response("[1, 2]")
    with pytest.raises(ValueError):
        llm.parse_json_response("no json here")


@pytest.mark.parametrize("value,expected", [(8, 8.0), ("7.5", 7.5), ("9/10", 9.0), (None, 0.0), (42, 10.0), (True, 0.0)])
def test_to_score(value, expected):
    assert _to_score(value) == expected


class _HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_retries_transient_errors_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise _HttpError(503)
        return "ok", {}

    assert llm._with_retries(flaky, "openai") == ("ok", {})
    assert len(attempts) == 3


def test_does_not_retry_auth_errors(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    attempts = []

    def unauthorized():
        attempts.append(1)
        raise _HttpError(401)

    with pytest.raises(_HttpError):
        llm._with_retries(unauthorized, "openai")
    assert len(attempts) == 1


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenAI API key"):
        llm.call_llm("hi", provider="openai")


def test_default_models_per_provider():
    assert llm.default_model("gemini", "flash") == "gemini-2.5-flash"
    assert llm.default_model("openai", "pro") == "gpt-4o"


def test_normalize_state_handles_garbage():
    state = normalize_state({"requirements": "single string", "quality_scores": {"TC-1": "great"}, "rtm": [], "validations": None})
    assert state["requirements"][0]["id"] == "REQ-001"
    assert state["quality_scores"]["TC-1"]["score"] == 0.0
    assert state["rtm"] == {}
    assert state["validations"] == []


def test_script_validation_rules():
    state = {"automation_scripts": {
        "A": {"framework": "pytest", "script": "def test(:\n  pass"},
        "B": {"framework": "karate", "script": "Feature: x\nScenario: y\n* url 'http://x'"},
        "C": {"framework": "cucumber", "script": "Feature: x\n  Scenario: y\n  The user waits"},
        "D": {"framework": "pytest", "script": "   "},
    }}
    result = EvaluationAgent.validate_automation_scripts(state)
    assert not result["A"]["valid"]
    assert result["B"]["valid"]
    assert not result["C"]["valid"] and "Missing steps" in result["C"]["reason"]
    assert not result["D"]["valid"]


def _tc(tc_id, title):
    return {"test_case_id": tc_id, "title": title, "steps": [{"action": title, "expected_result": "ok"}]}


def test_semantic_duplicates_with_chroma(monkeypatch):
    vectors = {"Login works": [1.0, 0.0], "Login succeeds": [0.99, 0.01], "Logout works": [0.0, 1.0]}

    def fake_embed(texts, api_key=None, provider="openai", model_name=None):
        return [next(v for title, v in vectors.items() if f"Title: {title}\n" in t) for t in texts]

    monkeypatch.setattr("utils.vector_store.embed_texts", fake_embed)
    pairs = find_duplicate_test_cases([_tc("TC-1", "Login works"), _tc("TC-2", "Login succeeds"), _tc("TC-3", "Logout works")])
    assert [(a, b) for a, b, _ in pairs] == [("TC-1", "TC-2")]
    assert pairs[0][2] < 0.075


def test_duplicate_detection_falls_back_when_embeddings_fail(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("no network")

    monkeypatch.setattr("utils.vector_store.embed_texts", broken)
    pairs = find_duplicate_test_cases([
        _tc("TC-1", "verify user can log in with valid credentials"),
        _tc("TC-2", "verify user can log in with valid credentials now"),
        _tc("TC-3", "something different entirely"),
    ])
    assert [(a, b) for a, b, _ in pairs] == [("TC-1", "TC-2")]


def test_fallback_ignores_repeated_ids():
    assert fallback_duplicate_detection([_tc("TC-1", "same title"), _tc("TC-1", "same title")]) == []
