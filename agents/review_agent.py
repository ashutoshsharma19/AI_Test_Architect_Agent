import json
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from agents.base import llm_json_step
from agents.state import AgentState
from utils.normalizer import _to_score, normalize_quality_scores, normalize_review_findings, normalize_state
from utils.prompts import REVIEW_AGENT_PROMPT


def review_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 6: Review Agent (LLM-as-Judge). Reviews quality of requirements, test cases, and coverage, grading each test case."""
    safe_state = normalize_state(state)
    coverage = {
        "rtm": safe_state["rtm"],
        "coverage_gaps": safe_state["coverage_gaps"],
        "duplicate_test_cases": safe_state["metrics"].get("duplicate_test_cases", []),
    }
    prompt = (
        REVIEW_AGENT_PROMPT
        .replace("{requirements}", json.dumps(safe_state["requirements"], indent=2))
        .replace("{scenarios}", json.dumps(safe_state["scenarios"], indent=2))
        .replace("{test_cases}", json.dumps(safe_state["test_cases"], indent=2))
        .replace("{coverage}", json.dumps(coverage, indent=2))
    )

    parsed, update = llm_json_step(state, config, "review_agent", "Review Agent", prompt)
    if parsed is None:
        return update

    update["metrics"]["overall_quality_score"] = _to_score(parsed.get("overall_quality_score", 0.0))
    recommendations = parsed.get("recommendations", [])
    if isinstance(recommendations, list):
        update["metrics"]["review_recommendations"] = [str(r) for r in recommendations]
    return {
        **update,
        "review_findings": normalize_review_findings(parsed.get("review_findings", [])),
        "quality_scores": normalize_quality_scores(parsed.get("quality_scores", {})),
    }
