import ast
import json
from typing import Dict, Any, List, Tuple
from utils.llm import call_llm, clean_json_string
from utils.normalizer import normalize_state
from utils.prompts import (
    EVALUATION_AGENT_UNDERSTANDING_PROMPT,
    EVALUATION_AGENT_ACCURACY_PROMPT,
    EVALUATION_AGENT_HALLUCINATION_PROMPT
)

class EvaluationAgent:
    """
    Independent Evaluation Agent that runs POST-pipeline to score:
    1. Requirement Understanding (0-10)
    2. Test Case Accuracy (0-10)
    3. Automation Script Validity (Pytest ast.parse(), Karate structural checks)
    4. Coverage Completeness
    5. Hallucination Rate (Yes/No check per test case)
    """
    def __init__(self, api_key: str = None, model_name: str = "gpt-4o", request_timeout: float = None, model_provider: str = "openai"):
        self.api_key = api_key
        self.model_name = model_name
        self.request_timeout = request_timeout
        self.model_provider = model_provider

    def validate_automation_scripts(self, state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Validate generated scripts using AST parsing or structure rules."""
        state = normalize_state(state)
        scripts_data = state.get("automation_scripts", {})
        validation_results = {}
        
        for tc_id, data in scripts_data.items():
            framework = data.get("framework", "").lower()
            script = data.get("script", "")
            
            if not script:
                validation_results[tc_id] = {"valid": False, "reason": "Empty script."}
                continue
                
            if framework in ["pytest", "playwright"]:
                try:
                    ast.parse(script)
                    validation_results[tc_id] = {"valid": True, "reason": "AST parsing successful. Valid Python syntax."}
                except SyntaxError as e:
                    validation_results[tc_id] = {"valid": False, "reason": f"Syntax Error: {e.msg} on line {e.lineno}"}
            elif framework in ["karate", "cucumber"]:
                # Validate Feature, Scenario, and standard Given/When/Then steps
                has_feature = "Feature:" in script
                has_scenario = "Scenario:" in script
                has_given_then = "Given " in script or "When " in script or "Then " in script or "*" in script
                
                if has_feature and has_scenario and has_given_then:
                    validation_results[tc_id] = {"valid": True, "reason": "Valid Gherkin/Karate feature structure."}
                else:
                    reasons = []
                    if not has_feature: reasons.append("Missing 'Feature:' block")
                    if not has_scenario: reasons.append("Missing 'Scenario:' block")
                    if not has_given_then: reasons.append("Missing steps (Given/When/Then)")
                    validation_results[tc_id] = {"valid": False, "reason": "Structure check failed: " + ", ".join(reasons)}
            else:
                validation_results[tc_id] = {"valid": True, "reason": "Manual script, validation skipped."}
                
        return validation_results

    def evaluate_pipeline(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run all post-pipeline evaluations and return consolidated grades."""
        original_state = state
        state = normalize_state(state)
        eval_metrics = {}
        errors = []
        
        # 1. Coverage Completeness (direct calculation)
        requirements = state.get("requirements", [])
        rtm = state.get("rtm", {})
        total_reqs = len(requirements)
        known_req_ids = {req.get("id") for req in requirements if req.get("id")}
        covered_reqs = sum(1 for req_id in known_req_ids if rtm.get(req_id))
        coverage_completeness = min((covered_reqs / total_reqs * 100), 100.0) if total_reqs > 0 else 0.0
        eval_metrics["coverage_completeness_pct"] = round(coverage_completeness, 2)
        
        # 2. Requirement Understanding Score
        try:
            prompt = EVALUATION_AGENT_UNDERSTANDING_PROMPT
            prompt = prompt.replace("{raw_input}", state.get("raw_input", ""))
            prompt = prompt.replace("{requirements}", json.dumps(requirements, indent=2))
            prompt = prompt.replace("{business_rules}", json.dumps(state.get("business_rules", []), indent=2))
            prompt = prompt.replace("{entities}", json.dumps(state.get("entities", []), indent=2))
            response_text, _ = call_llm(
                prompt=prompt,
                api_key=self.api_key,
                model_name=self.model_name,
                enforce_json=True,
                timeout_seconds=self.request_timeout,
                provider=self.model_provider
            )
            res = json.loads(clean_json_string(response_text))
            eval_metrics["requirement_understanding"] = {
                "score": res.get("score", 0),
                "reason": res.get("reason", "")
            }
        except Exception as e:
            errors.append(f"Eval - Req Understanding failed: {str(e)}")
            eval_metrics["requirement_understanding"] = {"score": 0, "reason": f"Evaluation error: {str(e)}"}
            
        # 3. Test Case Accuracy Score
        try:
            prompt = EVALUATION_AGENT_ACCURACY_PROMPT
            prompt = prompt.replace("{requirements}", json.dumps(requirements, indent=2))
            prompt = prompt.replace("{test_cases}", json.dumps(state.get("test_cases", []), indent=2))
            response_text, _ = call_llm(
                prompt=prompt,
                api_key=self.api_key,
                model_name=self.model_name,
                enforce_json=True,
                timeout_seconds=self.request_timeout,
                provider=self.model_provider
            )
            res = json.loads(clean_json_string(response_text))
            eval_metrics["test_case_accuracy"] = {
                "score": res.get("score", 0),
                "reason": res.get("reason", "")
            }
        except Exception as e:
            errors.append(f"Eval - Test Case Accuracy failed: {str(e)}")
            eval_metrics["test_case_accuracy"] = {"score": 0, "reason": f"Evaluation error: {str(e)}"}

        # 4. Automation Script Validity Checks
        script_validations = self.validate_automation_scripts(state)
        eval_metrics["automation_script_validity"] = script_validations
        
        # Calculate automation validity rate
        total_scripts = len(script_validations)
        valid_scripts = sum(1 for v in script_validations.values() if v["valid"])
        script_validity_rate = (valid_scripts / total_scripts * 100) if total_scripts > 0 else 100.0
        eval_metrics["automation_script_validity_rate"] = round(script_validity_rate, 2)
        
        # 5. Hallucination Rate evaluation
        hallucinated_count = 0
        hallucination_details = {}
        test_cases = state.get("test_cases", [])
        
        # Evaluate up to 3 test cases to conserve tokens, or all if small
        tc_to_evaluate = test_cases[:3] if len(test_cases) > 3 else test_cases
        
        for tc in tc_to_evaluate:
            tc_id = tc.get("test_case_id", "")
            try:
                prompt = EVALUATION_AGENT_HALLUCINATION_PROMPT
                prompt = prompt.replace("{raw_input}", state.get("raw_input", ""))
                prompt = prompt.replace("{test_cases}", json.dumps(tc, indent=2))
                response_text, _ = call_llm(
                    prompt=prompt,
                    api_key=self.api_key,
                    model_name=self.model_name,
                    enforce_json=True,
                    timeout_seconds=self.request_timeout,
                    provider=self.model_provider
                )
                res = json.loads(clean_json_string(response_text))
                has_h = res.get("has_hallucination", "No")
                reason = res.get("reason", "")
                
                hallucination_details[tc_id] = {
                    "has_hallucination": has_h,
                    "reason": reason
                }
                
                if has_h.lower() == "yes":
                    hallucinated_count += 1
            except Exception as e:
                errors.append(f"Eval - Hallucination test case {tc_id} failed: {str(e)}")
                hallucination_details[tc_id] = {"has_hallucination": "Error", "reason": str(e)}
                
        # Calculate Hallucination Rate
        hallucination_rate = (hallucinated_count / len(tc_to_evaluate) * 100) if tc_to_evaluate else 0.0
        eval_metrics["hallucination_rate"] = round(hallucination_rate, 2)
        eval_metrics["hallucination_details"] = hallucination_details
        eval_metrics["eval_errors"] = errors
        
        # Inject the evaluations back into the caller's state metrics for display in Tab 7.
        # normalize_state returns a shallow copy, so write to both the normalized state and
        # the original object passed by Streamlit/test_pipeline.
        for target_state in (state, original_state):
            if isinstance(target_state, dict):
                target_state.setdefault("metrics", {})
                target_state["metrics"]["evaluation_scores"] = eval_metrics
                target_state["metrics"]["hallucination_rate"] = round(hallucination_rate, 2)
            
        return eval_metrics
