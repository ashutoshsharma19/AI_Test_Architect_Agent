import os
import sys
import json
from dotenv import load_dotenv

# Ensure workspace is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from agents.graph import get_pipeline_graph
from agents.evaluation_agent import EvaluationAgent

def main():
    model_provider = os.getenv("MODEL_PROVIDER", "openai").lower()
    if model_provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model_pro = os.getenv("MODEL_PRO", "gemini-1.5-pro")
        model_flash = os.getenv("MODEL_FLASH", "gemini-1.5-flash")
        key_name = "GEMINI_API_KEY"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        model_pro = os.getenv("MODEL_PRO", "gpt-4o")
        model_flash = os.getenv("MODEL_FLASH", "gpt-4o-mini")
        key_name = "OPENAI_API_KEY"

    if not api_key:
        print(f"Warning: {key_name} environment variable not found. Skipping live API execution.")
        print("Please check your .env file or environment settings.")
        return
        
    print("Testing end-to-end agentic pipeline...")
    raw_input = (
        "The user login system shall allow registered users to log in using "
        "email and password. The system shall lock the account after 3 "
        "consecutive failed login attempts. Password must be minimum 8 "
        "characters with at least one uppercase, one number, and one special "
        "character. Session shall expire after 30 minutes."
    )
    
    state = {
        "raw_input": raw_input,
        "requirements": [],
        "business_rules": [],
        "entities": [],
        "assumptions": [],
        "ambiguities": [],
        "scenarios": [],
        "test_cases": [],
        "rtm": {},
        "coverage_gaps": [],
        "automation_scripts": {},
        "review_findings": [],
        "quality_scores": {},
        "metrics": {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "model_calls": [],
            "req_coverage_pct": 0.0,
            "auto_coverage_pct": 0.0,
            "risk_coverage_pct": 0.0,
            "test_design_quality_score": 0.0,
            "hallucination_rate": 0.0
        },
        "errors": []
    }
    
    from agents.requirement_agent import requirement_interpreter_agent
    from agents.scenario_agent import scenario_agent
    from agents.testcase_agent import testcase_agent
    from agents.coverage_agent import coverage_agent
    from agents.automation_agent import automation_agent
    from agents.review_agent import review_agent
    from agents.metrics_agent import metrics_agent
    
    run_config = {
        "configurable": {
            "api_key": api_key,
            "model_provider": model_provider,
            "model_pro": model_pro,
            "model_flash": model_flash,
            "request_timeout": 90,
        }
    }
    
    print("\nRunning Requirement Interpreter...")
    res = requirement_interpreter_agent(state, run_config)
    state.update(res)
    print(f"Requirements: {len(state['requirements'])}")
    print(f"Business Rules: {len(state['business_rules'])}")
    print(f"Entities: {len(state['entities'])}")
    
    print("\nRunning Scenario Generator...")
    res = scenario_agent(state, run_config)
    state.update(res)
    print(f"Scenarios: {len(state['scenarios'])}")
    
    print("\nRunning Test Case Generator...")
    res = testcase_agent(state, run_config)
    state.update(res)
    print(f"Test Cases: {len(state['test_cases'])}")
    
    print("\nRunning Coverage Agent...")
    res = coverage_agent(state, run_config)
    state.update(res)
    print(f"RTM Coverage: {state['metrics'].get('coverage_percentage')}%")
    print(f"Coverage Gaps: {state['coverage_gaps']}")
    print(f"Duplicate Pairs: {len(state['metrics'].get('duplicate_test_cases', []))}")
    
    print("\nRunning Automation Agent...")
    res = automation_agent(state, run_config)
    state.update(res)
    print(f"Automation Scripts generated: {len(state['automation_scripts'])}")
    
    print("\nRunning Review Agent...")
    res = review_agent(state, run_config)
    state.update(res)
    print(f"Review Findings: {len(state['review_findings'])}")
    print(f"Overall Quality Score: {state['metrics'].get('overall_quality_score')}")
    
    print("\nRunning Metrics Agent...")
    res = metrics_agent(state, run_config)
    state.update(res)
    
    print("\nRunning Evaluation Agent...")
    eval_agent = EvaluationAgent(api_key=api_key, model_name=model_flash, request_timeout=90, model_provider=model_provider)
    eval_metrics = eval_agent.evaluate_pipeline(state)
    print("\nIndependent Evaluation Metrics:")
    print(f" - Coverage Completeness: {eval_metrics.get('coverage_completeness_pct')}%")
    print(f" - Req Understanding Score: {eval_metrics.get('requirement_understanding', {}).get('score')}/10")
    print(f" - Test Case Accuracy Score: {eval_metrics.get('test_case_accuracy', {}).get('score')}/10")
    print(f" - Automation Syntax Validity Rate: {eval_metrics.get('automation_script_validity_rate')}%")
    print(f" - Hallucination Rate: {eval_metrics.get('hallucination_rate')}%")
    
    # Save the output to sample_output for demo caching
    os.makedirs("examples/sample_output", exist_ok=True)
    with open("examples/sample_output/sample_run.json", "w") as f:
        json.dump(state, f, indent=2)
    print("\nSample outputs saved to examples/sample_output/sample_run.json")

if __name__ == "__main__":
    main()
