import json
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple

# Default pricing per token (USD). Update if your selected models use
# different pricing in your account.
MODEL_PRICING = {
    "openai_pro": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai_mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gemini_pro": {"input": 1.25 / 1_000_000, "output": 10.00 / 1_000_000},
    "gemini_flash": {"input": 0.30 / 1_000_000, "output": 2.50 / 1_000_000},
}

DEFAULT_MODELS = {
    "openai": {"pro": "gpt-4o", "flash": "gpt-4o-mini"},
    "gemini": {"pro": "gemini-2.5-pro", "flash": "gemini-2.5-flash"},
}

MAX_ATTEMPTS = 3
# HTTP status codes that will not succeed on retry (bad key, bad model name, bad request).
NON_RETRYABLE_STATUS = {400, 401, 403, 404, 422}


def default_model(provider: str, tier: str) -> str:
    """Return the default model name for a provider and tier ("pro" or "flash")."""
    return DEFAULT_MODELS.get((provider or "openai").lower(), DEFAULT_MODELS["openai"])[tier]


def clean_json_string(text: str) -> str:
    """Strip a markdown code fence wrapper if present."""
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    return fence.group(1).strip() if fence else text


def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Parse an LLM response into a JSON object.
    Tolerates code fences and leading/trailing prose around the object.
    Raises ValueError when no JSON object can be recovered.
    """
    cleaned = clean_json_string(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"Model response was not valid JSON: {cleaned[:200]!r}")
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a JSON object from the model, got {type(parsed).__name__}.")
    return parsed


def _pricing_for(provider: str, model_name: str) -> Dict[str, float]:
    provider = provider.lower()
    model_name = model_name.lower()
    if provider == "gemini":
        return MODEL_PRICING["gemini_flash" if "flash" in model_name else "gemini_pro"]
    return MODEL_PRICING["openai_mini" if "mini" in model_name else "openai_pro"]


def _resolve_api_key(provider: str, api_key: Optional[str]) -> str:
    provider = provider.lower()
    if provider == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Gemini API key is not configured. Please set GEMINI_API_KEY in your environment, .env file, or Streamlit sidebar.")
        return key

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OpenAI API key is not configured. Please set OPENAI_API_KEY in your environment, .env file, or Streamlit sidebar.")
    return key


def _default_timeout() -> float:
    return float(os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("OPENAI_REQUEST_TIMEOUT") or "90")


def _status_code(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (ValueError, TypeError, ImportError)):
        return False
    return _status_code(exc) not in NON_RETRYABLE_STATUS


def _with_retries(fn: Callable[[], Tuple[str, Dict[str, Any]]], provider: str) -> Tuple[str, Dict[str, Any]]:
    """Run fn with exponential backoff, failing fast on errors a retry cannot fix."""
    last_error: Optional[Exception] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - provider SDKs raise many types
            last_error = exc
            if not _is_retryable(exc) or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(2 ** attempt)
    raise last_error or RuntimeError(f"Failed to call {provider} API after retries.")


def call_llm(
    prompt: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    enforce_json: bool = True,
    timeout_seconds: Optional[float] = None,
    provider: str = "openai"
) -> Tuple[str, Dict[str, Any]]:
    """
    Call the configured LLM provider with retry logic and token usage metrics.
    Returns:
        (response_text, usage_metrics)
    """
    provider = (provider or "openai").lower()
    model_name = model_name or default_model(provider, "pro")
    key = _resolve_api_key(provider, api_key)
    request_timeout = float(timeout_seconds or _default_timeout())
    pricing = _pricing_for(provider, model_name)
    caller = _call_gemini if provider == "gemini" else _call_openai
    return _with_retries(
        lambda: caller(
            prompt=prompt,
            api_key=key,
            model_name=model_name,
            enforce_json=enforce_json,
            timeout_seconds=request_timeout,
            pricing=pricing,
        ),
        provider,
    )


def _usage_metrics(provider: str, model_name: str, prompt_tokens: int, completion_tokens: int,
                   pricing: Dict[str, float], latency_seconds: float) -> Dict[str, Any]:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost": (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"]),
        "model": model_name,
        "provider": provider,
        "latency_seconds": latency_seconds,
    }


def _call_openai(
    prompt: str,
    api_key: str,
    model_name: str,
    enforce_json: bool,
    timeout_seconds: float,
    pricing: Dict[str, float],
) -> Tuple[str, Dict[str, Any]]:
    from openai import OpenAI

    # Retries are handled by _with_retries; disable the SDK's own to avoid multiplying them.
    client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
    request_params: Dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
    }
    if enforce_json:
        request_params["response_format"] = {"type": "json_object"}

    started_at = time.perf_counter()
    response = client.chat.completions.create(**request_params)
    latency_seconds = round(time.perf_counter() - started_at, 2)

    usage = response.usage
    prompt_tokens = (usage.prompt_tokens or 0) if usage else 0
    completion_tokens = (usage.completion_tokens or 0) if usage else 0
    metrics = _usage_metrics("openai", model_name, prompt_tokens, completion_tokens, pricing, latency_seconds)
    return response.choices[0].message.content or "", metrics


def _call_gemini(
    prompt: str,
    api_key: str,
    model_name: str,
    enforce_json: bool,
    timeout_seconds: float,
    pricing: Dict[str, float],
) -> Tuple[str, Dict[str, Any]]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError("Gemini provider requires the google-genai package. Install requirements.txt again.") from exc

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
    )
    generation_config = None
    if enforce_json:
        generation_config = types.GenerateContentConfig(response_mime_type="application/json")

    started_at = time.perf_counter()
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=generation_config,
    )
    latency_seconds = round(time.perf_counter() - started_at, 2)

    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = (getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
    completion_tokens = (getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
    metrics = _usage_metrics("gemini", model_name, prompt_tokens, completion_tokens, pricing, latency_seconds)
    return response.text or "", metrics


def call_openai(*args, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Backward-compatible alias for older imports."""
    kwargs["provider"] = "openai"
    return call_llm(*args, **kwargs)
