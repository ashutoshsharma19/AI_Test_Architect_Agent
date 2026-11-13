from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from agents.base import llm_json_step
from agents.state import AgentState
from utils.normalizer import _string_list, normalize_business_rules, normalize_entities, normalize_requirements
from utils.prompts import REQUIREMENT_INTERPRETER_PROMPT


def requirement_interpreter_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 1: Requirement Interpreter. Extracts requirements, rules, entities, validations, assumptions, ambiguities."""
    prompt = REQUIREMENT_INTERPRETER_PROMPT.replace("{input_text}", state.get("raw_input", ""))
    parsed, update = llm_json_step(state, config, "requirement_interpreter", "Requirement Interpreter", prompt)
    if parsed is None:
        return update

    return {
        **update,
        "requirements": normalize_requirements(parsed.get("requirements", [])),
        "business_rules": normalize_business_rules(parsed.get("business_rules", [])),
        "entities": normalize_entities(parsed.get("entities", [])),
        "validations": parsed.get("validations", []) if isinstance(parsed.get("validations"), list) else [],
        "assumptions": _string_list(parsed.get("assumptions", [])),
        "ambiguities": _string_list(parsed.get("ambiguities", [])),
    }
