import json
from typing import Dict, Any
from agents.state import AgentState
from utils.prompts import REQUIREMENT_INTERPRETER_PROMPT
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_business_rules, normalize_entities, normalize_requirements

def requirement_interpreter_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent 1: Requirement Interpreter. Extracts requirements, rules, entities, validations, assumptions, ambiguities."""
    # Retrieve configuration parameters
    cfg = config.get("configurable", {}) if config else {}
    api_key = cfg.get("api_key")
    model_name = cfg.get("model_pro", "gpt-4o")
    request_timeout = cfg.get("request_timeout")
    model_provider = cfg.get("model_provider", "openai")
    
    # Initialize metrics if not present
    metrics = state.get("metrics") or {}
    total_in = metrics.get("total_input_tokens", 0)
    total_out = metrics.get("total_output_tokens", 0)
    total_cost = metrics.get("total_cost", 0.0)
    model_calls = metrics.get("model_calls", [])
    
    errors = state.get("errors") or []
    
    prompt = REQUIREMENT_INTERPRETER_PROMPT.replace("{input_text}", state["raw_input"])
    
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
            "agent": "requirement_interpreter",
            "model": call_metrics["model"],
            "provider": call_metrics.get("provider", model_provider),
            "prompt_tokens": call_metrics["prompt_tokens"],
            "completion_tokens": call_metrics["completion_tokens"],
            "cost": call_metrics["cost"],
            "latency_seconds": call_metrics.get("latency_seconds", 0)
        })
        
        # Parse JSON output
        parsed_data = json.loads(clean_json_string(response_text))
        requirements = normalize_requirements(parsed_data.get("requirements", []))
        business_rules = normalize_business_rules(parsed_data.get("business_rules", []))
        entities = normalize_entities(parsed_data.get("entities", []))
        
        return {
            "requirements": requirements,
            "business_rules": business_rules,
            "entities": entities,
            "validations": parsed_data.get("validations", []),
            "assumptions": parsed_data.get("assumptions", []),
            "ambiguities": parsed_data.get("ambiguities", []),
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            },
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Requirement Interpreter failed: {str(e)}")
        return {
            "errors": errors,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            }
        }
