import json
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from agents.base import llm_json_step
from agents.state import AgentState
from utils.normalizer import normalize_scenarios, normalize_test_cases
from utils.prompts import TESTCASE_GENERATOR_PROMPT


def testcase_agent(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Agent 3: Test Case Generator. Expands scenarios into detailed test cases with test data and SQL validation queries."""
    scenarios_output = {"scenarios": normalize_scenarios(state.get("scenarios", []))}
    prompt = TESTCASE_GENERATOR_PROMPT.replace("{scenarios_output}", json.dumps(scenarios_output, indent=2))

    parsed, update = llm_json_step(state, config, "testcase_generator", "Test Case Generator", prompt)
    if parsed is None:
        return update
    return {**update, "test_cases": normalize_test_cases(parsed.get("test_cases", []))}
