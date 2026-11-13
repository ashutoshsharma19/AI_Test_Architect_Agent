from typing import Dict, Any, Optional

from langchain_core.runnables import RunnableConfig
from agents.state import AgentState
from utils.normalizer import normalize_state

def metrics_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 7: QA Metrics Agent. Computes KPI metrics for display in the dashboard."""
    safe_state = normalize_state(state)
    requirements = safe_state.get("requirements", [])
    scenarios = safe_state.get("scenarios", [])
    test_cases = safe_state.get("test_cases", [])
    rtm = safe_state.get("rtm", {})
    quality_scores = safe_state.get("quality_scores", {})
    metrics = dict(state.get("metrics") or {})
    
    # 1. Requirement Coverage %
    total_reqs = len(requirements)
    known_req_ids = {req.get("id") for req in requirements if req.get("id")}
    covered_reqs = sum(1 for req_id in known_req_ids if len(rtm.get(req_id, [])) > 0)
    req_coverage = min((covered_reqs / total_reqs * 100), 100.0) if total_reqs > 0 else 0.0
    coverage_audit = []
    for req in requirements:
        req_id = req.get("id")
        tc_ids = rtm.get(req_id, [])
        coverage_audit.append({
            "requirement_id": req_id,
            "requirement_text": req.get("text", ""),
            "test_case_count": len(tc_ids),
            "test_case_ids": ", ".join(tc_ids),
            "status": "Covered" if tc_ids else "Uncovered",
        })
    
    # 2. Automation Coverage %
    total_tcs = len(test_cases)
    auto_tcs = sum(1 for tc in test_cases if tc.get("test_type", "manual") != "manual")
    auto_coverage = (auto_tcs / total_tcs * 100) if total_tcs > 0 else 0.0
    
    # 3. Risk Coverage % (High-risk scenarios are Security and Negative type scenarios)
    high_risk_scenarios = [s for s in scenarios if s.get("type") in ["security", "negative"]]
    total_high_risk = len(high_risk_scenarios)
    covered_high_risk = 0
    for hrs in high_risk_scenarios:
        # Check if the requirement this scenario tests has at least one test case
        req_id = hrs.get("req_id")
        scenario_id = hrs.get("scenario_id")
        
        # Check if there is any test case that covers this scenario
        has_tc = any(tc.get("scenario_id") == scenario_id for tc in test_cases)
        if has_tc:
            covered_high_risk += 1
            
    risk_coverage = (covered_high_risk / total_high_risk * 100) if total_high_risk > 0 else 100.0
    
    # 4. Test Design Quality Score (avg from Review Agent)
    # If not computed by Review Agent, calculate manually from scores dict
    avg_quality = 0.0
    if quality_scores:
        total_score = sum(item.get("score", 0) for item in quality_scores.values())
        avg_quality = total_score / len(quality_scores)
    else:
        avg_quality = metrics.get("overall_quality_score", 0.0)
        
    # 5. Token cost and tracking
    # Set final metric cards
    metrics["req_coverage_pct"] = round(req_coverage, 2)
    metrics["total_requirements"] = total_reqs
    metrics["covered_requirements"] = covered_reqs
    metrics["uncovered_requirements"] = total_reqs - covered_reqs
    metrics["requirement_coverage_formula"] = f"{covered_reqs}/{total_reqs} * 100"
    metrics["coverage_audit"] = coverage_audit
    metrics["auto_coverage_pct"] = round(auto_coverage, 2)
    metrics["risk_coverage_pct"] = round(risk_coverage, 2)
    metrics["test_design_quality_score"] = round(avg_quality, 2)
    
    # We will initialize hallucination rate as 0.0. The EvaluationAgent will compute it and override it.
    if "hallucination_rate" not in metrics:
        metrics["hallucination_rate"] = 0.0
        
    return {
        "metrics": metrics
    }
