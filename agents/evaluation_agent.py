import ast
import json
from typing import Any, Dict, List, Optional

from agents.base import record_model_call
from utils.llm import call_llm, default_model, parse_json_response
from utils.normalizer import _to_score, normalize_state
from utils.prompts import (
    EVALUATION_AGENT_ACCURACY_PROMPT,
    EVALUATION_AGENT_HALLUCINATION_PROMPT,
    EVALUATION_AGENT_UNDERSTANDING_PROMPT,
)

GHERKIN_STEP_KEYWORDS = ("Given ", "When ", "Then ", "And ", "But ", "* ")


def _is_yes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"yes", "true", "y", "1"}


class EvaluationAgent:
    """
    Independent Evaluation Agent that runs POST-pipeline to score:
    1. Requirement Understanding (0-10)
    2. Test Case Accuracy (0-10)
    3. Automation Script Validity (Pytest ast.parse(), Karate structural checks)
    4. Coverage Completeness
    5. Hallucination Rate (Yes/No check per sampled test case)
    """
    def __init__(self, api_key: str = None, model_name: Optional[str] = None, request_timeout: float = None,
                 model_provider: str = "openai", hallucination_sample_size: int = 3):
        self.api_key = api_key
        self.model_provider = (model_provider or "openai").lower()
        self.model_name = model_name or default_model(self.model_provider, "flash")
        self.request_timeout = request_timeout
        self.hallucination_sample_size = hallucination_sample_size
        self._usage: List[Dict[str, Any]] = []

    def _judge(self, prompt: str) -> Dict[str, Any]:
        response_text, call_metrics = call_llm(
            prompt=prompt,
            api_key=self.api_key,
            model_name=self.model_name,
            enforce_json=True,
            timeout_seconds=self.request_timeout,
            provider=self.model_provider,
        )
        self._usage.append(call_metrics)
        return parse_json_response(response_text)

    @staticmethod
    def validate_automation_scripts(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Validate generated scripts using AST parsing or structure rules."""
        state = normalize_state(state)
        validation_results = {}

        for tc_id, data in state.get("automation_scripts", {}).items():
            framework = data.get("framework", "").lower()
            script = data.get("script", "")

            if not script.strip():
                validation_results[tc_id] = {"valid": False, "reason": "Empty script."}
                continue

            if framework in ("pytest", "playwright"):
                try:
                    ast.parse(script)
                    validation_results[tc_id] = {"valid": True, "reason": "AST parsing successful. Valid Python syntax."}
                except SyntaxError as e:
                    validation_results[tc_id] = {"valid": False, "reason": f"Syntax Error: {e.msg} on line {e.lineno}"}
            elif framework in ("karate", "cucumber"):
                lines = [line.strip() for line in script.splitlines()]
                has_feature = any(line.startswith("Feature:") for line in lines)
                has_scenario = any(line.startswith(("Scenario:", "Scenario Outline:")) for line in lines)
                has_steps = any(line.startswith(GHERKIN_STEP_KEYWORDS) for line in lines)

                if has_feature and has_scenario and has_steps:
                    validation_results[tc_id] = {"valid": True, "reason": "Valid Gherkin/Karate feature structure."}
                else:
                    reasons = []
                    if not has_feature:
                        reasons.append("Missing 'Feature:' block")
                    if not has_scenario:
                        reasons.append("Missing 'Scenario:' block")
                    if not has_steps:
                        reasons.append("Missing steps (Given/When/Then)")
                    validation_results[tc_id] = {"valid": False, "reason": "Structure check failed: " + ", ".join(reasons)}
            else:
                validation_results[tc_id] = {"valid": True, "reason": f"Framework '{framework}' not syntax-checked."}

        return validation_results

    def evaluate_pipeline(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run all post-pipeline evaluations and return consolidated grades."""
        original_state = state
        state = normalize_state(state)
        self._usage = []
        eval_metrics: Dict[str, Any] = {}
        errors: List[str] = []

        requirements = state["requirements"]
        test_cases = state["test_cases"]
        raw_input = state.get("raw_input", "")

        # 1. Coverage Completeness (direct calculation)
        rtm = state["rtm"]
        known_req_ids = {req.get("id") for req in requirements if req.get("id")}
        covered_reqs = sum(1 for req_id in known_req_ids if rtm.get(req_id))
        coverage = min(covered_reqs / len(requirements) * 100, 100.0) if requirements else 0.0
        eval_metrics["coverage_completeness_pct"] = round(coverage, 2)

        # 2. Requirement Understanding and 3. Test Case Accuracy (LLM-as-judge)
        judged = {
            "requirement_understanding": (
                "Req Understanding",
                EVALUATION_AGENT_UNDERSTANDING_PROMPT
                .replace("{raw_input}", raw_input)
                .replace("{requirements}", json.dumps(requirements, indent=2))
                .replace("{business_rules}", json.dumps(state["business_rules"], indent=2))
                .replace("{entities}", json.dumps(state["entities"], indent=2)),
            ),
            "test_case_accuracy": (
                "Test Case Accuracy",
                EVALUATION_AGENT_ACCURACY_PROMPT
                .replace("{requirements}", json.dumps(requirements, indent=2))
                .replace("{test_cases}", json.dumps(test_cases, indent=2)),
            ),
        }
        for key, (label, prompt) in judged.items():
            try:
                res = self._judge(prompt)
                eval_metrics[key] = {"score": _to_score(res.get("score", 0)), "reason": str(res.get("reason", ""))}
            except Exception as e:  # noqa: BLE001
                errors.append(f"Eval - {label} failed: {e}")
                eval_metrics[key] = {"score": 0, "reason": f"Evaluation error: {e}"}

        # 4. Automation Script Validity Checks
        script_validations = self.validate_automation_scripts(state)
        eval_metrics["automation_script_validity"] = script_validations
        total_scripts = len(script_validations)
        valid_scripts = sum(1 for v in script_validations.values() if v["valid"])
        eval_metrics["automation_script_validity_rate"] = round(
            (valid_scripts / total_scripts * 100) if total_scripts else 100.0, 2
        )

        # 5. Hallucination Rate on a sample of test cases (keeps token cost bounded)
        hallucinated_count = 0
        judged_count = 0
        hallucination_details = {}
        for tc in test_cases[: self.hallucination_sample_size]:
            tc_id = tc.get("test_case_id", "")
            try:
                res = self._judge(
                    EVALUATION_AGENT_HALLUCINATION_PROMPT
                    .replace("{raw_input}", raw_input)
                    .replace("{test_cases}", json.dumps(tc, indent=2))
                )
                has_h = _is_yes(res.get("has_hallucination", "No"))
                hallucination_details[tc_id] = {"has_hallucination": "Yes" if has_h else "No",
                                                "reason": str(res.get("reason", ""))}
                judged_count += 1
                hallucinated_count += int(has_h)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Eval - Hallucination test case {tc_id} failed: {e}")
                hallucination_details[tc_id] = {"has_hallucination": "Error", "reason": str(e)}

        # Errored checks are excluded from the denominator so failures don't masquerade as "clean".
        hallucination_rate = round((hallucinated_count / judged_count * 100) if judged_count else 0.0, 2)
        eval_metrics["hallucination_rate"] = hallucination_rate
        eval_metrics["hallucination_sample_size"] = judged_count
        eval_metrics["hallucination_details"] = hallucination_details
        eval_metrics["eval_errors"] = errors

        # Write results (and the evaluator's own token spend) back into the caller's state.
        if isinstance(original_state, dict):
            metrics = dict(original_state.get("metrics") or {})
            for call_metrics in self._usage:
                metrics = record_model_call(metrics, "evaluation_agent", call_metrics)
            metrics["evaluation_scores"] = eval_metrics
            metrics["hallucination_rate"] = hallucination_rate
            original_state["metrics"] = metrics

        return eval_metrics
