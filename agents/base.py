"""Shared plumbing for LLM-backed agent nodes: config parsing, metric accounting, error capture."""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from utils.llm import call_llm, default_model, parse_json_response


@dataclass(frozen=True)
class RunSettings:
    api_key: Optional[str]
    provider: str
    model_pro: str
    model_flash: str
    request_timeout: Optional[float]

    def model(self, tier: str) -> str:
        return self.model_flash if tier == "flash" else self.model_pro


def run_settings(config: Optional[Dict[str, Any]]) -> RunSettings:
    cfg = (config or {}).get("configurable", {}) or {}
    provider = (cfg.get("model_provider") or "openai").lower()
    return RunSettings(
        api_key=cfg.get("api_key"),
        provider=provider,
        model_pro=cfg.get("model_pro") or default_model(provider, "pro"),
        model_flash=cfg.get("model_flash") or default_model(provider, "flash"),
        request_timeout=cfg.get("request_timeout"),
    )


def record_model_call(metrics: Dict[str, Any], agent: str, call_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of metrics with one model call added to the running totals."""
    updated = dict(metrics or {})
    updated["total_input_tokens"] = updated.get("total_input_tokens", 0) + call_metrics.get("prompt_tokens", 0)
    updated["total_output_tokens"] = updated.get("total_output_tokens", 0) + call_metrics.get("completion_tokens", 0)
    updated["total_cost"] = updated.get("total_cost", 0.0) + call_metrics.get("cost", 0.0)
    updated["model_calls"] = list(updated.get("model_calls", [])) + [{
        "agent": agent,
        "model": call_metrics.get("model"),
        "provider": call_metrics.get("provider"),
        "prompt_tokens": call_metrics.get("prompt_tokens", 0),
        "completion_tokens": call_metrics.get("completion_tokens", 0),
        "cost": call_metrics.get("cost", 0.0),
        "latency_seconds": call_metrics.get("latency_seconds", 0),
    }]
    return updated


def llm_json_step(
    state: Dict[str, Any],
    config: Optional[Dict[str, Any]],
    agent: str,
    label: str,
    prompt: str,
    tier: str = "pro",
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Call the LLM for one agent node and parse its JSON reply.

    Returns (parsed, update) where `update` always carries the accumulated
    `metrics` and `errors` for the node to return. `parsed` is None on failure,
    in which case a readable error has been appended to `update["errors"]`.
    """
    settings = run_settings(config)
    metrics = dict(state.get("metrics") or {})
    errors = list(state.get("errors") or [])
    parsed: Optional[Dict[str, Any]] = None

    try:
        response_text, call_metrics = call_llm(
            prompt=prompt,
            api_key=settings.api_key,
            model_name=settings.model(tier),
            enforce_json=True,
            timeout_seconds=settings.request_timeout,
            provider=settings.provider,
        )
        metrics = record_model_call(metrics, agent, call_metrics)
        parsed = parse_json_response(response_text)
    except Exception as exc:  # noqa: BLE001 - surface any provider/parse failure in the UI
        errors.append(f"{label} failed: {exc}")

    return parsed, {"metrics": metrics, "errors": errors}
