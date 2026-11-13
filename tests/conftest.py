"""Offline test fixtures: a scripted fake LLM so the whole pipeline runs without API keys."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAW_INPUT = (
    "The system shall lock the account after 3 consecutive failed login attempts. "
    "Password must be minimum 8 characters."
)

CANNED = {
    "Lead Business Analyst": {
        "requirements": [
            {"id": "REQ-001", "text": "Lock the account after 3 consecutive failed login attempts.", "type": "functional"},
            {"id": "REQ-002", "text": "Password must be minimum 8 characters.", "type": "functional"},
        ],
        "business_rules": [{"id": "BR-001", "name": "Lockout", "description": "3 strikes"}],
        "entities": [{"name": "User", "attributes": ["status"], "relationships": []}],
        "validations": [{"id": "VAL-001", "target": "Password", "rule": "len >= 8"}],
        "assumptions": ["Admin unlocks accounts."],
        "ambiguities": ["Does the counter reset?"],
    },
    "Senior QA Test Architect": {
        "scenarios": [
            {"scenario_id": "SC-001", "req_id": "REQ-001", "type": "negative", "title": "Lockout", "description": "3 failures"},
            {"scenario_id": "SC-002", "req_id": "REQ-002", "type": "boundary", "title": "Password length", "description": "7 vs 8"},
        ]
    },
    "Principal QA Engineer": {
        "test_cases": [
            {"test_case_id": "TC-001", "scenario_id": "SC-001", "req_id": "REQ-001", "title": "Account locks after three failures",
             "priority": "P1", "test_type": "pytest", "steps": [{"step_number": 1, "action": "Fail login 3x", "expected_result": "Locked"}]},
            # Unknown req_id: should be recovered through its scenario.
            {"test_case_id": "TC-002", "scenario_id": "SC-002", "req_id": "REQ-999", "title": "Seven character password rejected",
             "priority": "P2", "test_type": "cucumber", "steps": [{"step_number": 1, "action": "Enter 7 chars", "expected_result": "Rejected"}]},
        ]
    },
    "Automation Test Engineer": {
        "automation_scripts": {
            "TC-001": {"framework": "pytest", "script": "def test_lockout():\n    assert True\n"},
            "TC-002": {"framework": "cucumber", "script": "Feature: Password\n  Scenario: short\n    Given a 7 char password\n    Then it is rejected\n"},
            "TC-404": {"framework": "pytest", "script": "def test_ghost(): pass"},
        }
    },
    "Senior QA Director": {
        "review_findings": [{"id": "RF-001", "severity": "Low", "category": "Data", "description": "Add more data."}],
        "quality_scores": {"TC-001": {"score": "9/10", "reason": "Good"}, "TC-002": {"score": 7, "reason": "OK"}},
        "overall_quality_score": "8",
        "recommendations": ["Add unlock tests."],
    },
    "Requirement Understanding Score": {"score": 9, "reason": "Accurate"},
    "Test Case Accuracy Score": {"score": "8", "reason": "Mostly accurate"},
    "detect if the generated test cases contain hallucinations": {"has_hallucination": False, "reason": "Grounded"},
}


class FakeLLM:
    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def __call__(self, prompt, api_key=None, model_name=None, enforce_json=True, timeout_seconds=None, provider="openai"):
        for marker, payload in {**CANNED, **self.overrides}.items():
            if marker in prompt:
                self.calls.append((marker, model_name))
                if isinstance(payload, Exception):
                    raise payload
                text = payload if isinstance(payload, str) else "```json\n" + json.dumps(payload) + "\n```"
                return text, {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.001,
                              "model": model_name, "provider": provider, "latency_seconds": 0.1}
        raise AssertionError(f"Unexpected prompt: {prompt[:120]}")


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr("agents.base.call_llm", llm)
    monkeypatch.setattr("agents.evaluation_agent.call_llm", llm)

    # Deterministic embeddings: TC titles map to orthogonal vectors -> no semantic duplicates.
    def fake_embed(texts, api_key=None, provider="openai", model_name=None):
        return [[1.0 if i == j else 0.0 for j in range(len(texts))] for i in range(len(texts))]

    monkeypatch.setattr("utils.vector_store.embed_texts", fake_embed)
    return llm


@pytest.fixture
def run_config():
    return {"configurable": {"api_key": "test-key", "model_provider": "openai",
                             "model_pro": "pro-model", "model_flash": "flash-model", "request_timeout": 5}}
