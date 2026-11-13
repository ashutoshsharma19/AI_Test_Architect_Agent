import json
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from agents.base import llm_json_step
from agents.state import AgentState
from utils.normalizer import normalize_automation_scripts, normalize_state
from utils.prompts import AUTOMATION_AGENT_PROMPT


def _extract_scripts(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either {"automation_scripts": {...}} or a flat {tc_id: {framework, script}} reply."""
    scripts = parsed.get("automation_scripts")
    if isinstance(scripts, dict) and scripts:
        return scripts
    if any(isinstance(key, str) and key.upper().startswith("TC") for key in parsed):
        return parsed
    return {}


def automation_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 5: Automation Agent. Generates scripts in pytest, playwright, karate, or cucumber for eligible test cases."""
    safe_state = normalize_state(state)
    eligible_test_cases = [tc for tc in safe_state["test_cases"] if tc.get("test_type", "manual") != "manual"]
    if not eligible_test_cases:
        return {"automation_scripts": {}}

    prompt = AUTOMATION_AGENT_PROMPT.replace(
        "{test_cases_output}", json.dumps({"test_cases": eligible_test_cases}, indent=2)
    )
    # Script generation is speed-sensitive, so it uses the smaller/faster model tier.
    parsed, update = llm_json_step(state, config, "automation_agent", "Automation Agent", prompt, tier="flash")
    if parsed is None:
        return update

    eligible_ids = {tc["test_case_id"] for tc in eligible_test_cases}
    scripts = normalize_automation_scripts(_extract_scripts(parsed))
    # Drop scripts for test cases that were never requested (hallucinated IDs).
    scripts = {tc_id: data for tc_id, data in scripts.items() if tc_id in eligible_ids}
    return {**update, "automation_scripts": scripts}
