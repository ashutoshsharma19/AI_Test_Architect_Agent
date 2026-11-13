from typing import Callable, Dict, List, Tuple

from langgraph.graph import END, START, StateGraph

from agents.automation_agent import automation_agent
from agents.coverage_agent import coverage_agent
from agents.metrics_agent import metrics_agent
from agents.requirement_agent import requirement_interpreter_agent
from agents.review_agent import review_agent
from agents.scenario_agent import scenario_agent
from agents.state import AgentState
from agents.testcase_agent import testcase_agent

# Ordered pipeline: (node name, human label, node function).
# The LangGraph graph, the Streamlit UI and the CLI runner all iterate this list,
# so adding/reordering an agent only needs a change here.
PIPELINE: List[Tuple[str, str, Callable]] = [
    ("requirement_interpreter", "Extract Requirements", requirement_interpreter_agent),
    ("scenario_generator", "Generate Scenarios", scenario_agent),
    ("test_case_generator", "Generate Test Cases", testcase_agent),
    ("coverage_agent", "Map Coverage (RTM)", coverage_agent),
    ("automation_agent", "Generate Automation Scripts", automation_agent),
    ("review_agent", "Senior QA Review", review_agent),
    ("metrics_agent", "Calculate QA Metrics", metrics_agent),
]
NODE_FUNCTIONS: Dict[str, Callable] = {name: fn for name, _, fn in PIPELINE}
# Human-in-the-loop pause point: the user can inspect generated artefacts before the review.
INTERRUPT_BEFORE = "review_agent"


def get_pipeline_graph(interrupt: bool = False):
    """
    Construct and compile the LangGraph workflow.
    With `interrupt=True` the graph pauses before the review agent; resuming requires
    invoking with the same `thread_id`, so an in-memory checkpointer is attached.
    """
    workflow = StateGraph(AgentState)
    for name, _, fn in PIPELINE:
        workflow.add_node(name, fn)

    names = [name for name, _, _ in PIPELINE]
    workflow.add_edge(START, names[0])
    for current, nxt in zip(names, names[1:]):
        workflow.add_edge(current, nxt)
    workflow.add_edge(names[-1], END)

    if interrupt:
        from langgraph.checkpoint.memory import MemorySaver

        return workflow.compile(checkpointer=MemorySaver(), interrupt_before=[INTERRUPT_BEFORE])
    return workflow.compile()
