"""
Live end-to-end smoke run against a real LLM provider.

    python test_pipeline.py            # uses MODEL_PROVIDER (default: openai) from .env

Writes the resulting state to examples/sample_output/sample_run.json, which the
Streamlit app can load via "Load Pre-run Demo Data". For offline tests run `pytest`.
"""
import json
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from agents.evaluation_agent import EvaluationAgent  # noqa: E402
from agents.graph import PIPELINE  # noqa: E402
from agents.state import empty_state  # noqa: E402
from utils.llm import default_model  # noqa: E402
from utils.normalizer import normalize_state  # noqa: E402

RAW_INPUT = (
    "The user login system shall allow registered users to log in using "
    "email and password. The system shall lock the account after 3 "
    "consecutive failed login attempts. Password must be minimum 8 "
    "characters with at least one uppercase, one number, and one special "
    "character. Session shall expire after 30 minutes."
)


def main() -> int:
    model_provider = os.getenv("MODEL_PROVIDER", "openai").lower()
    key_name = "GEMINI_API_KEY" if model_provider == "gemini" else "OPENAI_API_KEY"
    api_key = os.getenv(key_name) or (os.getenv("GOOGLE_API_KEY") if model_provider == "gemini" else None)
    if not api_key:
        print(f"Warning: {key_name} environment variable not found. Skipping live API execution.")
        return 0

    model_pro = os.getenv("MODEL_PRO", default_model(model_provider, "pro"))
    model_flash = os.getenv("MODEL_FLASH", default_model(model_provider, "flash"))
    run_config = {"configurable": {
        "api_key": api_key,
        "model_provider": model_provider,
        "model_pro": model_pro,
        "model_flash": model_flash,
        "request_timeout": 90,
    }}

    print(f"Testing end-to-end agentic pipeline ({model_provider}: {model_pro} / {model_flash})...")
    state = empty_state(RAW_INPUT)
    for name, label, fn in PIPELINE:
        print(f"\nRunning {label} ({name})...")
        state = normalize_state({**state, **fn(state, run_config)})

    print(f"\nRequirements: {len(state['requirements'])} | Scenarios: {len(state['scenarios'])} | "
          f"Test cases: {len(state['test_cases'])} | Scripts: {len(state['automation_scripts'])}")
    print(f"Requirement coverage: {state['metrics'].get('req_coverage_pct')}% | Gaps: {state['coverage_gaps']}")
    print(f"Overall quality score: {state['metrics'].get('overall_quality_score')}")

    print("\nRunning Evaluation Agent...")
    eval_metrics = EvaluationAgent(api_key=api_key, model_name=model_flash, request_timeout=90,
                                   model_provider=model_provider).evaluate_pipeline(state)
    print(f" - Coverage Completeness: {eval_metrics.get('coverage_completeness_pct')}%")
    print(f" - Req Understanding Score: {eval_metrics['requirement_understanding']['score']}/10")
    print(f" - Test Case Accuracy Score: {eval_metrics['test_case_accuracy']['score']}/10")
    print(f" - Automation Syntax Validity Rate: {eval_metrics.get('automation_script_validity_rate')}%")
    print(f" - Hallucination Rate: {eval_metrics.get('hallucination_rate')}%")
    print(f" - Total cost: ${state['metrics'].get('total_cost', 0):.4f}")

    os.makedirs("examples/sample_output", exist_ok=True)
    with open("examples/sample_output/sample_run.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("\nSample outputs saved to examples/sample_output/sample_run.json")

    if state["errors"]:
        print("\nErrors:\n - " + "\n - ".join(state["errors"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
