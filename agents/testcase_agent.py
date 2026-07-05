import json
from typing import Dict, Any
from agents.state import AgentState
from utils.prompts import TESTCASE_GENERATOR_PROMPT
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_scenarios, normalize_test_cases

def testcase_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent 3: Test Case Generator. Expands scenarios into detailed test cases with test data and SQL validation queries."""
    cfg = config.get("configurable", {}) if config else {}
    api_key = cfg.get("api_key")
    model_name = cfg.get("model_pro", "gpt-4o")
    request_timeout = cfg.get("request_timeout")
    model_provider = cfg.get("model_provider", "openai")
    
    metrics = state.get("metrics") or {}
    total_in = metrics.get("total_input_tokens", 0)
    total_out = metrics.get("total_output_tokens", 0)
    total_cost = metrics.get("total_cost", 0.0)
    model_calls = metrics.get("model_calls", [])
    
    errors = state.get("errors") or []
    
    scenarios_output = {
        "scenarios": normalize_scenarios(state.get("scenarios", []))
    }
    
    prompt = TESTCASE_GENERATOR_PROMPT.replace(
        "{scenarios_output}", json.dumps(scenarios_output, indent=2)
    )
    
    try:
        response_text, call_metrics = call_llm(
            prompt=prompt,
            api_key=api_key,
            model_name=model_name,
            enforce_json=True,
            timeout_seconds=request_timeout,
            provider=model_provider
        )
        
        # Accumulate metrics
        total_in += call_metrics["prompt_tokens"]
        total_out += call_metrics["completion_tokens"]
        total_cost += call_metrics["cost"]
        model_calls.append({
            "agent": "testcase_generator",
            "model": call_metrics["model"],
            "provider": call_metrics.get("provider", model_provider),
            "prompt_tokens": call_metrics["prompt_tokens"],
            "completion_tokens": call_metrics["completion_tokens"],
            "cost": call_metrics["cost"],
            "latency_seconds": call_metrics.get("latency_seconds", 0)
        })
        
        parsed_data = json.loads(clean_json_string(response_text))
        test_cases = normalize_test_cases(parsed_data.get("test_cases", []))
        
        return {
            "test_cases": test_cases,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            },
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Test Case Generator failed: {str(e)}")
        return {
            "errors": errors,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            }
        }
