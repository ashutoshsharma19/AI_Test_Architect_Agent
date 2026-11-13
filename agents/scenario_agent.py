import json
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from agents.base import llm_json_step
from agents.state import AgentState
from utils.normalizer import normalize_scenarios, normalize_state
from utils.prompts import SCENARIO_GENERATOR_PROMPT


def scenario_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 2: Scenario Generator. Generates functional, negative, boundary, integration, and security test scenarios."""
    safe_state = normalize_state(state)
    interpreter_output = {
        "requirements": safe_state["requirements"],
        "business_rules": safe_state["business_rules"],
        "entities": safe_state["entities"],
        "validations": safe_state["validations"],
    }
    prompt = SCENARIO_GENERATOR_PROMPT.replace("{interpreter_output}", json.dumps(interpreter_output, indent=2))

    parsed, update = llm_json_step(state, config, "scenario_generator", "Scenario Generator", prompt)
    if parsed is None:
        return update
    return {**update, "scenarios": normalize_scenarios(parsed.get("scenarios", []))}
