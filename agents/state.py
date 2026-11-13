from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    raw_input: str
    requirements: List[Dict[str, Any]]
    business_rules: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    validations: List[Any]
    assumptions: List[str]
    ambiguities: List[str]
    scenarios: List[Dict[str, Any]]
    test_cases: List[Dict[str, Any]]
    rtm: Dict[str, List[str]]
    coverage_gaps: List[str]
    automation_scripts: Dict[str, Dict[str, Any]]
    review_findings: List[Dict[str, Any]]
    quality_scores: Dict[str, Dict[str, Any]]
    metrics: Dict[str, Any]
    errors: List[str]


def empty_metrics() -> Dict[str, Any]:
    return {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost": 0.0,
        "model_calls": [],
        "req_coverage_pct": 0.0,
        "auto_coverage_pct": 0.0,
        "risk_coverage_pct": 0.0,
        "test_design_quality_score": 0.0,
        "hallucination_rate": 0.0,
    }


def empty_state(raw_input: str = "") -> AgentState:
    """Fresh pipeline state. Single source of truth for the UI, CLI runner and tests."""
    return {
        "raw_input": raw_input,
        "requirements": [],
        "business_rules": [],
        "entities": [],
        "validations": [],
        "assumptions": [],
        "ambiguities": [],
        "scenarios": [],
        "test_cases": [],
        "rtm": {},
        "coverage_gaps": [],
        "automation_scripts": {},
        "review_findings": [],
        "quality_scores": {},
        "metrics": empty_metrics(),
        "errors": [],
    }
