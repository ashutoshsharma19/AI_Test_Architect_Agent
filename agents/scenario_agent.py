import json
from typing import Dict, Any
from agents.state import AgentState
from utils.prompts import SCENARIO_GENERATOR_PROMPT
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_scenarios, normalize_state

def scenario_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent 2: Scenario Generator. Generates functional, negative, boundary, integration, and security test scenarios."""
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
    
    # Format requirements and rules for the prompt input
    safe_state = normalize_state(state)
    interpreter_output = {
        "requirements": safe_state.get("requirements", []),
        "business_rules": safe_state.get("business_rules", []),
        "entities": safe_state.get("entities", []),
        "validations": safe_state.get("validations", [])
    }
    
    prompt = SCENARIO_GENERATOR_PROMPT.replace(
        "{interpreter_output}", json.dumps(interpreter_output, indent=2)
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
            "agent": "scenario_generator",
            "model": call_metrics["model"],
            "provider": call_metrics.get("provider", model_provider),
            "prompt_tokens": call_metrics["prompt_tokens"],
            "completion_tokens": call_metrics["completion_tokens"],
            "cost": call_metrics["cost"],
            "latency_seconds": call_metrics.get("latency_seconds", 0)
        })
        
        parsed_data = json.loads(clean_json_string(response_text))
        scenarios = normalize_scenarios(parsed_data.get("scenarios", []))
        
        return {
            "scenarios": scenarios,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            },
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Scenario Generator failed: {str(e)}")
        return {
            "errors": errors,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            }
        }
