import json
from typing import Dict, Any
from agents.state import AgentState
from utils.prompts import AUTOMATION_AGENT_PROMPT
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_automation_scripts, normalize_state

def automation_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent 5: Automation Agent. Generates scripts in pytest, playwright, karate, or cucumber for eligible test cases."""
    cfg = config.get("configurable", {}) if config else {}
    api_key = cfg.get("api_key")
    # For speed-sensitive nodes like script generation, default to a smaller OpenAI model.
    model_name = cfg.get("model_flash", "gpt-4o-mini")
    request_timeout = cfg.get("request_timeout")
    model_provider = cfg.get("model_provider", "openai")
    
    metrics = state.get("metrics") or {}
    total_in = metrics.get("total_input_tokens", 0)
    total_out = metrics.get("total_output_tokens", 0)
    total_cost = metrics.get("total_cost", 0.0)
    model_calls = metrics.get("model_calls", [])
    
    errors = state.get("errors") or []
    
    safe_state = normalize_state(state)

    # Filter test cases that are eligible for automation (non-manual)
    eligible_test_cases = [tc for tc in safe_state.get("test_cases", []) if tc.get("test_type", "manual") != "manual"]
    
    if not eligible_test_cases:
        return {
            "automation_scripts": {},
            "errors": errors
        }
        
    prompt = AUTOMATION_AGENT_PROMPT.replace(
        "{test_cases_output}", json.dumps({"test_cases": eligible_test_cases}, indent=2)
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
            "agent": "automation_agent",
            "model": call_metrics["model"],
            "provider": call_metrics.get("provider", model_provider),
            "prompt_tokens": call_metrics["prompt_tokens"],
            "completion_tokens": call_metrics["completion_tokens"],
            "cost": call_metrics["cost"],
            "latency_seconds": call_metrics.get("latency_seconds", 0)
        })
        
        parsed_data = json.loads(clean_json_string(response_text))
        
        # Extract scripts from nested or flat structure
        scripts = parsed_data.get("automation_scripts", {})
        if not scripts and isinstance(parsed_data, dict):
            # sometimes LLM might output a flat dictionary of {tc_id: {framework, script}}
            # let's check if the keys look like test case IDs (e.g. starting with TC)
            has_tc_keys = any(isinstance(k, str) and (k.startswith("TC-") or k.startswith("TC")) for k in parsed_data.keys())
            if has_tc_keys:
                scripts = parsed_data
        scripts = normalize_automation_scripts(scripts)
                
        return {
            "automation_scripts": scripts,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            },
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Automation Agent failed: {str(e)}")
        return {
            "errors": errors,
            "metrics": {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            }
        }
