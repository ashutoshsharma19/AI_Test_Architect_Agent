import uuid

from agents.evaluation_agent import EvaluationAgent
from agents.graph import PIPELINE, get_pipeline_graph
from agents.state import empty_state
from tests.conftest import RAW_INPUT


def _run_all(state, config):
    for _, _, fn in PIPELINE:
        state = {**state, **fn(state, config)}
    return state


def test_full_pipeline_with_fake_llm(fake_llm, run_config):
    state = _run_all(empty_state(RAW_INPUT), run_config)

    assert state["errors"] == []
    assert [r["id"] for r in state["requirements"]] == ["REQ-001", "REQ-002"]
    assert state["validations"], "validations must flow from the interpreter to later agents"
    # TC-002 had an unknown req_id and must be recovered via its scenario.
    assert state["rtm"] == {"REQ-001": ["TC-001"], "REQ-002": ["TC-002"]}
    assert state["coverage_gaps"] == []
    assert state["metrics"]["req_coverage_pct"] == 100.0
    # Hallucinated TC-404 script is dropped.
    assert set(state["automation_scripts"]) == {"TC-001", "TC-002"}
    # String scores are coerced to numbers.
    assert state["quality_scores"]["TC-001"]["score"] == 9.0
    assert state["metrics"]["overall_quality_score"] == 8.0
    assert state["metrics"]["test_design_quality_score"] == 8.0
    # Five LLM agents -> five recorded calls; automation uses the flash tier.
    calls = state["metrics"]["model_calls"]
    assert [c["agent"] for c in calls] == [
        "requirement_interpreter", "scenario_generator", "testcase_generator", "automation_agent", "review_agent"
    ]
    assert calls[3]["model"] == "flash-model"
    assert state["metrics"]["total_input_tokens"] == 500


def test_validations_reach_scenario_prompt(fake_llm, run_config, monkeypatch):
    prompts = []
    original = fake_llm.__call__

    def spy(prompt, **kwargs):
        prompts.append(prompt)
        return original(prompt, **kwargs)

    monkeypatch.setattr("agents.base.call_llm", spy)
    _run_all(empty_state(RAW_INPUT), run_config)
    scenario_prompt = next(p for p in prompts if "Senior QA Test Architect" in p)
    assert "VAL-001" in scenario_prompt


def test_langgraph_keeps_validations(fake_llm, run_config):
    result = get_pipeline_graph().invoke(empty_state(RAW_INPUT), run_config)
    assert result["validations"][0]["id"] == "VAL-001"
    # Run config (api key / model tiers) must reach nodes executed inside the compiled graph.
    assert {c["model"] for c in result["metrics"]["model_calls"]} == {"pro-model", "flash-model"}
    assert result["metrics"]["req_coverage_pct"] == 100.0


def test_langgraph_interrupt_and_resume(fake_llm, run_config):
    graph = get_pipeline_graph(interrupt=True)
    config = {"configurable": {**run_config["configurable"], "thread_id": uuid.uuid4().hex}}
    paused = graph.invoke(empty_state(RAW_INPUT), config)
    assert paused["test_cases"] and not paused["review_findings"]
    assert graph.get_state(config).next == ("review_agent",)

    finished = graph.invoke(None, config)
    assert finished["review_findings"]
    assert graph.get_state(config).next == ()


def test_agent_failure_is_reported_not_raised(fake_llm, run_config):
    fake_llm.overrides["Senior QA Test Architect"] = RuntimeError("boom")
    state = _run_all(empty_state(RAW_INPUT), run_config)
    assert any("Scenario Generator failed: boom" in e for e in state["errors"])
    assert state["scenarios"] == []


def test_evaluation_agent_scores_and_usage(fake_llm, run_config):
    state = _run_all(empty_state(RAW_INPUT), run_config)
    calls_before = len(state["metrics"]["model_calls"])
    result = EvaluationAgent(api_key="k", model_name="flash-model").evaluate_pipeline(state)

    assert result["coverage_completeness_pct"] == 100.0
    assert result["requirement_understanding"]["score"] == 9.0
    assert result["test_case_accuracy"]["score"] == 8.0
    assert result["automation_script_validity_rate"] == 100.0
    # Boolean has_hallucination=False is handled (previously crashed on .lower()).
    assert result["hallucination_rate"] == 0.0
    assert result["hallucination_sample_size"] == 2
    assert state["metrics"]["evaluation_scores"] is result
    # 2 judge calls + 2 hallucination checks are now included in token accounting.
    assert len(state["metrics"]["model_calls"]) == calls_before + 4


def test_hallucination_rate_ignores_errored_checks(fake_llm, run_config):
    state = _run_all(empty_state(RAW_INPUT), run_config)
    fake_llm.overrides["detect if the generated test cases contain hallucinations"] = RuntimeError("quota")
    result = EvaluationAgent(api_key="k").evaluate_pipeline(state)
    assert result["hallucination_sample_size"] == 0
    assert all(d["has_hallucination"] == "Error" for d in result["hallucination_details"].values())
