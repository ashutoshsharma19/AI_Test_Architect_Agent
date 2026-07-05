from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    raw_input: str
    requirements: List[Dict[str, Any]]
    business_rules: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
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
