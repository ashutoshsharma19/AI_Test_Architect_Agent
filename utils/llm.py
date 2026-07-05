import os
import json
import time
from typing import Dict, Any, Tuple, Optional
from openai import OpenAI

# Default pricing per 1 Million tokens. Update if your selected models use
# different pricing in your account.
MODEL_PRICING = {
    "openai_pro": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai_mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gemini_pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
    "gemini_flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
}

def clean_json_string(text: str) -> str:
    """Strip markdown code block wrapper if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

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


def call_llm(
    prompt: str, 
    api_key: Optional[str] = None, 
    model_name: str = "gpt-4o",
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
    key = _resolve_api_key(provider, api_key)
    request_timeout = timeout_seconds or float(os.getenv("OPENAI_REQUEST_TIMEOUT", "90"))
    pricing = _pricing_for(provider, model_name)

    if provider == "gemini":
        return _call_gemini(
            prompt=prompt,
            api_key=key,
            model_name=model_name,
            enforce_json=enforce_json,
            timeout_seconds=request_timeout,
            pricing=pricing,
        )

    return _call_openai(
        prompt=prompt,
        api_key=key,
        model_name=model_name,
        enforce_json=enforce_json,
        timeout_seconds=request_timeout,
        pricing=pricing,
    )


def _call_openai(
    prompt: str,
    api_key: str,
    model_name: str,
    enforce_json: bool,
    timeout_seconds: float,
    pricing: Dict[str, float],
) -> Tuple[str, Dict[str, Any]]:
    client = OpenAI(api_key=api_key, timeout=timeout_seconds)
    request_params = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
    }
    if enforce_json:
        request_params["response_format"] = {"type": "json_object"}
    
    # 2. API Call with retry once
    last_error = None
    for attempt in range(2):
        try:
            started_at = time.perf_counter()
            response = client.chat.completions.create(**request_params)
            latency_seconds = round(time.perf_counter() - started_at, 2)
            
            # Extract usage
            prompt_tokens = 0
            completion_tokens = 0
            cost = 0.0
            
            if response.usage:
                prompt_tokens = response.usage.prompt_tokens or 0
                completion_tokens = response.usage.completion_tokens or 0
                cost = (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"])
                
            metrics = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "model": model_name,
                "provider": "openai",
                "latency_seconds": latency_seconds
            }
            
            return response.choices[0].message.content or "", metrics
            
        except Exception as e:
            last_error = e
            time.sleep(1) # wait 1 second before retry
            
    raise last_error or Exception("Failed to call OpenAI API after retries.")


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

    client = genai.Client(api_key=api_key)
    generation_config = None
    if enforce_json:
        generation_config = types.GenerateContentConfig(response_mime_type="application/json")
    last_error = None
    for attempt in range(2):
        try:
            started_at = time.perf_counter()
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )
            latency_seconds = round(time.perf_counter() - started_at, 2)

            prompt_tokens = 0
            completion_tokens = 0
            usage = getattr(response, "usage_metadata", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
                completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
            cost = (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"])

            metrics = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "model": model_name,
                "provider": "gemini",
                "latency_seconds": latency_seconds,
            }
            return response.text or "", metrics
        except Exception as e:
            last_error = e
            time.sleep(1)

    raise last_error or Exception("Failed to call Gemini API after retries.")


def call_openai(*args, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Backward-compatible alias for older imports."""
    kwargs["provider"] = "openai"
    return call_llm(*args, **kwargs)
