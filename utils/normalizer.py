from typing import Any, Dict, List


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_dict(value: Any, text_key: str = "text") -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {text_key: str(value)}


def _string_list(value: Any) -> List[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def normalize_requirements(requirements: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(requirements), start=1):
        req = _as_dict(item)
        title = str(req.get("title") or req.get("name") or "").strip()
        text = str(req.get("text") or req.get("description") or req.get("requirement") or "").strip()
        if title and text and title.lower() not in text.lower():
            text = f"{title}: {text}"
        elif title and not text:
            text = title
        normalized.append({
            "id": str(req.get("id") or f"REQ-{idx:03d}"),
            "text": text,
            "type": str(req.get("type") or "functional"),
        })
    return normalized


def normalize_business_rules(rules: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(rules), start=1):
        rule = _as_dict(item, text_key="description")
        normalized.append({
            "id": str(rule.get("id") or f"BR-{idx:03d}"),
            "name": str(rule.get("name") or rule.get("title") or f"Business Rule {idx}"),
            "description": str(rule.get("description") or rule.get("rule") or ""),
        })
    return normalized


def normalize_entities(entities: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(entities), start=1):
        entity = _as_dict(item, text_key="name")
        normalized.append({
            "name": str(entity.get("name") or f"Entity {idx}"),
            "attributes": _string_list(entity.get("attributes", [])),
            "relationships": _string_list(entity.get("relationships", [])),
        })
    return normalized


def normalize_scenarios(scenarios: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(scenarios), start=1):
        scenario = _as_dict(item, text_key="description")
        normalized.append({
            "scenario_id": str(scenario.get("scenario_id") or scenario.get("id") or f"SC-{idx:03d}"),
            "req_id": str(scenario.get("req_id") or scenario.get("requirement_id") or ""),
            "type": str(scenario.get("type") or "functional"),
            "title": str(scenario.get("title") or f"Scenario {idx}"),
            "description": str(scenario.get("description") or scenario.get("text") or ""),
        })
    return normalized


def normalize_steps(steps: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(steps), start=1):
        step = _as_dict(item, text_key="action")
        normalized.append({
            "step_number": step.get("step_number") or idx,
            "action": str(step.get("action") or step.get("step") or ""),
            "expected_result": str(step.get("expected_result") or step.get("expected") or ""),
        })
    return normalized


def normalize_test_cases(test_cases: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(test_cases), start=1):
        tc = _as_dict(item, text_key="title")
        normalized.append({
            "test_case_id": str(tc.get("test_case_id") or tc.get("id") or f"TC-{idx:03d}"),
            "scenario_id": str(tc.get("scenario_id") or ""),
            "req_id": str(tc.get("req_id") or tc.get("requirement_id") or ""),
            "title": str(tc.get("title") or f"Test Case {idx}"),
            "priority": str(tc.get("priority") or "P2"),
            "preconditions": str(tc.get("preconditions") or ""),
            "test_type": str(tc.get("test_type") or "manual"),
            "steps": normalize_steps(tc.get("steps", [])),
            "test_data": tc.get("test_data") if isinstance(tc.get("test_data"), dict) else {},
            "sql_query": tc.get("sql_query") or None,
        })
    return normalized


def normalize_review_findings(findings: Any) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(_as_list(findings), start=1):
        finding = _as_dict(item, text_key="description")
        normalized.append({
            "id": str(finding.get("id") or f"RF-{idx:03d}"),
            "severity": str(finding.get("severity") or "Medium"),
            "category": str(finding.get("category") or "General"),
            "description": str(finding.get("description") or ""),
        })
    return normalized


def normalize_quality_scores(scores: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(scores, dict):
        return {}
    normalized = {}
    for key, value in scores.items():
        score = _as_dict(value, text_key="reason")
        normalized[str(key)] = {
            "score": score.get("score", 0),
            "reason": str(score.get("reason") or ""),
        }
    return normalized


def normalize_automation_scripts(scripts: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(scripts, dict):
        return {}
    normalized = {}
    for key, value in scripts.items():
        script_info = _as_dict(value, text_key="script")
        normalized[str(key)] = {
            "framework": str(script_info.get("framework") or "manual"),
            "script": str(script_info.get("script") or ""),
        }
    return normalized


def normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(state or {})
    normalized["requirements"] = normalize_requirements(normalized.get("requirements", []))
    normalized["business_rules"] = normalize_business_rules(normalized.get("business_rules", []))
    normalized["entities"] = normalize_entities(normalized.get("entities", []))
    normalized["scenarios"] = normalize_scenarios(normalized.get("scenarios", []))
    normalized["test_cases"] = normalize_test_cases(normalized.get("test_cases", []))
    normalized["review_findings"] = normalize_review_findings(normalized.get("review_findings", []))
    normalized["quality_scores"] = normalize_quality_scores(normalized.get("quality_scores", {}))
    normalized["assumptions"] = _string_list(normalized.get("assumptions", []))
    normalized["ambiguities"] = _string_list(normalized.get("ambiguities", []))
    normalized["coverage_gaps"] = _string_list(normalized.get("coverage_gaps", []))
    normalized["rtm"] = normalized.get("rtm", {}) if isinstance(normalized.get("rtm", {}), dict) else {}
    normalized["automation_scripts"] = normalize_automation_scripts(normalized.get("automation_scripts", {}))
    normalized["metrics"] = normalized.get("metrics", {}) if isinstance(normalized.get("metrics", {}), dict) else {}
    normalized["errors"] = _string_list(normalized.get("errors", []))
    return normalized
