import json
from typing import Dict, Any
from agents.state import AgentState
from utils.prompts import REVIEW_AGENT_PROMPT
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_quality_scores, normalize_review_findings, normalize_state

def review_agent(state: AgentState, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent 6: Review Agent (LLM-as-Judge). Reviews quality of requirements, test cases, and coverage, grading each test case."""
    cfg = config.get("configurable", {}) if config else {}
    api_key = cfg.get("api_key")
    # For complex reasoning (QA Architect Review), use Pro model
    model_name = cfg.get("model_pro", "gpt-4o")
    request_timeout = cfg.get("request_timeout")
    model_provider = cfg.get("model_provider", "openai")
    
    metrics = state.get("metrics") or {}
    total_in = metrics.get("total_input_tokens", 0)
    total_out = metrics.get("total_output_tokens", 0)
    total_cost = metrics.get("total_cost", 0.0)
    model_calls = metrics.get("model_calls", [])
    
    errors = state.get("errors") or []
    
    safe_state = normalize_state(state)
    prompt = REVIEW_AGENT_PROMPT
    prompt = prompt.replace("{requirements}", json.dumps(safe_state.get("requirements", []), indent=2))
    prompt = prompt.replace("{scenarios}", json.dumps(safe_state.get("scenarios", []), indent=2))
    prompt = prompt.replace("{test_cases}", json.dumps(safe_state.get("test_cases", []), indent=2))
    prompt = prompt.replace(
        "{coverage}",
        json.dumps({
            "rtm": state.get("rtm", {}),
            "coverage_gaps": state.get("coverage_gaps", []),
            "duplicate_test_cases": metrics.get("duplicate_test_cases", [])
        }, indent=2)
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
            "agent": "review_agent",
            "model": call_metrics["model"],
            "provider": call_metrics.get("provider", model_provider),
            "prompt_tokens": call_metrics["prompt_tokens"],
            "completion_tokens": call_metrics["completion_tokens"],
            "cost": call_metrics["cost"],
            "latency_seconds": call_metrics.get("latency_seconds", 0)
        })
        
        parsed_data = json.loads(clean_json_string(response_text))
        
        findings = normalize_review_findings(parsed_data.get("review_findings", []))
        scores = normalize_quality_scores(parsed_data.get("quality_scores", {}))
        overall_score = parsed_data.get("overall_quality_score", 0.0)
        recommendations = parsed_data.get("recommendations", [])
        
        # Sync metrics
        metrics["overall_quality_score"] = overall_score
        
        return {
            "review_findings": findings,
            "quality_scores": scores,
            "metrics": {
                **metrics,
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            },
            "errors": errors
        }
        
    except Exception as e:
        errors.append(f"Review Agent failed: {str(e)}")
        return {
            "errors": errors,
            "metrics": {
                **metrics,
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost": total_cost,
                "model_calls": model_calls
            }
        }
