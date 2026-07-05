import re
from typing import Dict, Any, List, Tuple
from agents.state import AgentState
from utils.vector_store import find_duplicate_test_cases
from utils.normalizer import normalize_state


STOP_WORDS = {
    "a", "an", "and", "are", "as", "be", "by", "for", "from", "if", "in",
    "including", "into", "is", "it", "of", "on", "or", "shall", "should",
    "such", "system", "the", "their", "them", "to", "using", "user", "users",
    "when", "where", "with"
}


def _tokens(text: str) -> set:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def _test_case_text(tc: Dict[str, Any]) -> str:
    step_text = " ".join(
        f"{step.get('action', '')} {step.get('expected_result', '')}"
        for step in tc.get("steps", [])
    )
    return " ".join([
        tc.get("title", ""),
        tc.get("preconditions", ""),
        step_text,
        str(tc.get("test_data", "")),
        str(tc.get("sql_query", "")),
    ])


def _best_requirement_match(tc: Dict[str, Any], requirements: List[Dict[str, Any]]) -> Tuple[str, float]:
    tc_tokens = _tokens(_test_case_text(tc))
    if not tc_tokens:
        return "", 0.0

    best_req_id = ""
    best_score = 0.0
    for req in requirements:
        req_id = req.get("id", "")
        req_tokens = _tokens(f"{req_id} {req.get('text', '')}")
        if not req_tokens:
            continue
        overlap = len(tc_tokens & req_tokens)
        score = overlap / len(req_tokens)
        if score > best_score:
            best_req_id = req_id
            best_score = score
    return best_req_id, best_score

def coverage_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Agent 4: Coverage Agent.
    - Maps requirements to test cases (RTM)
    - Detects requirements with zero test coverage (gaps)
    - Identifies duplicate/redundant test cases using ChromaDB semantic search
    - Computes coverage percentage metrics
    """
    cfg = config.get("configurable", {}) if config else {}
    api_key = cfg.get("api_key")
    model_provider = cfg.get("model_provider", "openai")
    
    safe_state = normalize_state(state)
    requirements = safe_state.get("requirements", [])
    test_cases = safe_state.get("test_cases", [])
    errors = state.get("errors") or []
    
    # 1. Build RTM mapping only for extracted requirements. Generated test cases
    # can sometimes reference extra/malformed req_ids, but those must not inflate
    # requirement coverage above 100%.
    rtm: Dict[str, List[str]] = {req.get("id"): [] for req in requirements if req.get("id")}
    known_req_ids = set(rtm.keys())
    scenario_to_req = {
        scenario.get("scenario_id"): scenario.get("req_id")
        for scenario in safe_state.get("scenarios", [])
        if scenario.get("scenario_id") and scenario.get("req_id") in known_req_ids
    }
    unmapped_test_cases = []
    semantic_mappings = []
    
    for tc in test_cases:
        req_id = tc.get("req_id")
        tc_id = tc.get("test_case_id")
        if req_id and tc_id:
            if req_id in known_req_ids:
                rtm[req_id].append(tc_id)
            else:
                scenario_req_id = scenario_to_req.get(tc.get("scenario_id"))
                if scenario_req_id:
                    rtm[scenario_req_id].append(tc_id)
                    semantic_mappings.append({
                        "test_case_id": tc_id,
                        "original_req_id": req_id,
                        "mapped_req_id": scenario_req_id,
                        "basis": "scenario_id"
                    })
                else:
                    matched_req_id, score = _best_requirement_match(tc, requirements)
                    if matched_req_id and score >= 0.25:
                        rtm[matched_req_id].append(tc_id)
                        semantic_mappings.append({
                            "test_case_id": tc_id,
                            "original_req_id": req_id,
                            "mapped_req_id": matched_req_id,
                            "basis": f"semantic_overlap:{score:.2f}"
                        })
                    else:
                        unmapped_test_cases.append({"test_case_id": tc_id, "req_id": req_id})
            
    # 2. Detect coverage gaps (requirements with zero test cases mapped)
    coverage_gaps = [req_id for req_id, tc_list in rtm.items() if len(tc_list) == 0]
    
    # 3. Detect duplicate test cases using ChromaDB
    duplicate_pairs_raw = find_duplicate_test_cases(test_cases, api_key=api_key, provider=model_provider)
    
    # Format duplicate pairs for downstream use or reporting
    duplicate_pairs = []
    for id1, id2, score in duplicate_pairs_raw:
        duplicate_pairs.append({
            "tc1": id1,
            "tc2": id2,
            "similarity_score": round(1.0 - score, 2) # convert distance to similarity metric
        })
        
    # Calculate coverage metrics
    total_reqs = len(requirements)
    covered_reqs = total_reqs - len(coverage_gaps)
    coverage_percentage = (covered_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
    
    # Write to a helper dict in state if needed, or directly in metrics
    metrics = state.get("metrics") or {}
    metrics["coverage_percentage"] = round(coverage_percentage, 2)
    metrics["duplicate_test_cases"] = duplicate_pairs
    metrics["total_requirements"] = total_reqs
    metrics["covered_requirements"] = covered_reqs
    metrics["unmapped_test_cases"] = unmapped_test_cases
    metrics["semantic_requirement_mappings"] = semantic_mappings
    
    return {
        "rtm": rtm,
        "coverage_gaps": coverage_gaps,
        "metrics": metrics,
        "errors": errors
    }
