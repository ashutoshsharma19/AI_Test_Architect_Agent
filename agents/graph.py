from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.requirement_agent import requirement_interpreter_agent
from agents.scenario_agent import scenario_agent
from agents.testcase_agent import testcase_agent
from agents.coverage_agent import coverage_agent
from agents.automation_agent import automation_agent
from agents.review_agent import review_agent
from agents.metrics_agent import metrics_agent

def get_pipeline_graph(interrupt: bool = False):
    """
    Construct and compile the LangGraph workflow.
    Supports a Human-In-The-Loop toggle via the `interrupt` flag.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("requirement_interpreter", requirement_interpreter_agent)
    workflow.add_node("scenario_generator", scenario_agent)
    workflow.add_node("test_case_generator", testcase_agent)
    workflow.add_node("coverage_agent", coverage_agent)
    workflow.add_node("automation_agent", automation_agent)
    workflow.add_node("review_agent", review_agent)
    workflow.add_node("metrics_agent", metrics_agent)
    
    # Add edges
    workflow.add_edge(START, "requirement_interpreter")
    workflow.add_edge("requirement_interpreter", "scenario_generator")
    workflow.add_edge("scenario_generator", "test_case_generator")
    workflow.add_edge("test_case_generator", "coverage_agent")
    workflow.add_edge("coverage_agent", "automation_agent")
    workflow.add_edge("automation_agent", "review_agent")
    workflow.add_edge("review_agent", "metrics_agent")
    workflow.add_edge("metrics_agent", END)
    
    # Compile options
    if interrupt:
        # Checkpointing is omitted as requested for simplicity, 
        # but interrupt_before triggers the wait state in LangGraph.
        return workflow.compile(interrupt_before=["review_agent"])
    else:
        return workflow.compile()
