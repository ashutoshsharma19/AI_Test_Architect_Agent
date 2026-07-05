import os
import json
import streamlit as st
import pandas as pd
import io
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env variables if present
load_dotenv()

# App Page Configurations
st.set_page_config(
    page_title="AI Test Architect Agent Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Premium Dark/Glassmorphic Look
st.markdown("""
<style>
    /* Metric Cards Styling */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #58a6ff;
    }
    div[data-testid="stMetricLabel"] {
        color: #8b949e;
        font-size: 0.9rem;
    }
    
    /* Custom Badge Classes */
    .badge-green {
        background-color: #1f6feb;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-amber {
        background-color: #d29922;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-red {
        background-color: #f85149;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    
    /* Styled Containers */
    .card-container {
        background-color: #1f242c;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        color: #c9d1d9;
    }
</style>
""", unsafe_allow_html=True)

# Imports from project
from utils.document_parser import parse_document
from utils.exporter import export_to_excel, export_to_csv, export_to_jira_format
from utils.normalizer import normalize_state
from agents.graph import get_pipeline_graph
from agents.evaluation_agent import EvaluationAgent

# Session State Initialization
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = {
        "raw_input": "",
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

if "step_index" not in st.session_state:
    st.session_state.step_index = 0

if "run_mode" not in st.session_state:
    st.session_state.run_mode = "idle" # "idle", "running_full", "running_step"

if "last_active_agent" not in st.session_state:
    st.session_state.last_active_agent = "Idle"

# Load default requirement demo
DEFAULT_REQUIREMENTS = (
    "The user login system shall allow registered users to log in using\n"
    "email and password. The system shall lock the account after 3\n"
    "consecutive failed login attempts. Password must be minimum 8\n"
    "characters with at least one uppercase, one number, and one special\n"
    "character. The system shall send a password reset email within\n"
    "2 minutes of request. Session shall expire after 30 minutes of\n"
    "inactivity."
)

# ----------------- SIDEBAR -----------------
st.sidebar.title("⚙️ AI Test Architect")
st.sidebar.caption("Stateful LangGraph QA Pipeline")

# Provider, API Key, and Model Settings
model_provider = st.sidebar.selectbox(
    "Model Provider",
    ["openai", "gemini"],
    format_func=lambda value: "OpenAI" if value == "openai" else "Google Gemini",
    index=0,
    help="Switches the LLM backend while keeping the same agent workflow."
)

provider_settings = {
    "openai": {
        "label": "OpenAI API Key",
        "env": "OPENAI_API_KEY",
        "timeout_label": "OpenAI Request Timeout (seconds)",
        "reasoning_models": ["gpt-4o", "gpt-4.1", "gpt-4.1-mini"],
        "speed_models": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o"],
    },
    "gemini": {
        "label": "Gemini API Key",
        "env": "GEMINI_API_KEY",
        "timeout_label": "Gemini Request Timeout (seconds)",
        "reasoning_models": ["gemini-1.5-pro", "gemini-2.0-pro-exp-02-05", "gemini-2.5-pro"],
        "speed_models": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"],
    },
}
provider_config = provider_settings[model_provider]

api_key = st.sidebar.text_input(
    provider_config["label"],
    type="password",
    value=os.getenv(provider_config["env"], ""),
    help=f"Provide a key here or set {provider_config['env']} in a .env file."
)
api_key = api_key.strip()

if not api_key:
    st.sidebar.warning(f"Enter a {provider_config['label']} to enable pipeline execution.")

request_timeout = st.sidebar.number_input(
    provider_config["timeout_label"],
    min_value=15,
    max_value=300,
    value=90,
    step=15,
    help=f"Maximum time to wait for each {provider_config['label'].replace(' API Key', '')} model call before showing an error."
)

model_pro = st.sidebar.selectbox(
    "Reasoning Model (Agents 1-4, 6)",
    provider_config["reasoning_models"],
    index=0
)
model_flash = st.sidebar.selectbox(
    "Speed Model (Agents 5, 7, Eval)",
    provider_config["speed_models"],
    index=0
)

# Document Ingestion
st.sidebar.subheader("📥 Input Requirements")
uploaded_file = st.sidebar.file_uploader("Upload Requirement Doc", type=["pdf", "docx", "txt"])

# Text Input Option
text_input = st.sidebar.text_area(
    "Or Enter Requirements Text",
    value=DEFAULT_REQUIREMENTS,
    height=150
)

# Set final input string. Uploaded documents take precedence over the sample text.
raw_input_text = ""
input_source = "Text box"
input_warning = ""
if uploaded_file is not None:
    # Save file locally to parse
    temp_dir = "./scratch"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    with st.spinner(f"Parsing {uploaded_file.name}..."):
        parsed_text = parse_document(file_path).strip()

    if parsed_text and not parsed_text.startswith("Error") and not parsed_text.startswith("Unsupported"):
        raw_input_text = parsed_text
        input_source = f"Uploaded file: {uploaded_file.name}"
    else:
        raw_input_text = text_input
        input_warning = parsed_text or "Uploaded file did not contain readable text."
else:
    raw_input_text = text_input

if input_warning:
    st.sidebar.error(input_warning)

st.sidebar.info(f"Input Source: {input_source}")
st.sidebar.info(f"Input Length: {len(raw_input_text)} characters")
with st.sidebar.expander("Preview active requirements", expanded=False):
    st.text(raw_input_text[:2000] if raw_input_text else "No requirements text available.")

# Toggles and Buttons
step_by_step = st.sidebar.toggle("Run Step by Step", value=False)
interrupt_enabled = st.sidebar.toggle("Human-in-the-Loop Interrupt", value=False)
st.sidebar.caption(f"Pipeline status: {st.session_state.last_active_agent}")

# Control Actions
if st.sidebar.button("🚀 Run Full Pipeline", disabled=not api_key):
    st.session_state.run_mode = "running_full"
    st.session_state.step_index = 0
    # Reset State
    st.session_state.pipeline_state = {
        "raw_input": raw_input_text,
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

if st.sidebar.button("📂 Load Pre-run Demo Data"):
    try:
        with open("examples/sample_output/sample_run.json", "r") as f:
            demo_data = json.load(f)
        st.session_state.pipeline_state = demo_data
        st.session_state.step_index = 0
        st.toast("Loaded pre-run demo data successfully!", icon="📂")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to load demo data: {e}")

# Step by Step flow handling
pipeline_steps = [
    ("Extract Requirements", "requirement_interpreter"),
    ("Generate Scenarios", "scenario_generator"),
    ("Generate Test Cases", "test_case_generator"),
    ("Map Coverage (RTM)", "coverage_agent"),
    ("Generate Automation Scripts", "automation_agent"),
    ("Senior QA Review", "review_agent"),
    ("Calculate QA Metrics", "metrics_agent"),
    ("Post-Run Evaluation", "evaluation_agent")
]

if step_by_step and st.session_state.step_index < len(pipeline_steps):
    step_name, node_name = pipeline_steps[st.session_state.step_index]
    if st.sidebar.button(f"➡️ Run Step: {step_name}", disabled=not api_key):
        st.session_state.run_mode = "running_step"

if st.sidebar.button("🧹 Reset / Clear", type="secondary"):
    st.session_state.run_mode = "idle"
    st.session_state.step_index = 0
    st.session_state.pipeline_state = {
        "raw_input": "",
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

    st.rerun()


# ----------------- MAIN TITLE -----------------
st.title("🛡️ AI Test Architect Agent Platform")
st.markdown("An end-to-end multi-agent orchestration platform converting raw requirements into full QA deliverable packages.")

# ----------------- PIPELINE EXECUTION ENGINE -----------------
# Define Config dict
run_config = {
    "configurable": {
        "api_key": api_key,
        "model_provider": model_provider,
        "model_pro": model_pro,
        "model_flash": model_flash,
        "request_timeout": request_timeout
    }
}

if st.session_state.run_mode == "running_full":
    # Compile graph
    graph = get_pipeline_graph(interrupt=interrupt_enabled)
    initial_state = {
        "raw_input": raw_input_text,
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
    
    # Progress tracker
    progress_bar = st.progress(0)
    status_box = st.status("Initializing Multi-Agent Pipeline...")
    
    # Nodes in execution order
    nodes = [
        "requirement_interpreter", 
        "scenario_generator", 
        "test_case_generator", 
        "coverage_agent", 
        "automation_agent", 
        "review_agent", 
        "metrics_agent"
    ]
    
    current_state = initial_state
    
    # Run the graph sequentially for streaming updates in Streamlit UI
    for idx, node in enumerate(nodes):
        if interrupt_enabled and node == "review_agent":
            status_box.warning("Interrupt triggered before Review Agent! Human review optional.")
            if not st.button("Proceed to Review & Metrics"):
                st.session_state.run_mode = "idle"
                st.session_state.pipeline_state = current_state
                st.stop()
                
        status_box.update(label=f"Executing Agent {idx+1}: {node.replace('_', ' ').title()}...", state="running")
        st.session_state.last_active_agent = node
        st.caption(f"Currently executing: {node.replace('_', ' ').title()}")
        progress_bar.progress((idx) / (len(nodes) + 1))
        
        # Invoke node function
        try:
            # We fetch node function from graph or run manually to allow intermediate streaming
            # To ensure compatibility and ease of UI updates, we execute agent functions directly
            if node == "requirement_interpreter":
                from agents.requirement_agent import requirement_interpreter_agent
                res = requirement_interpreter_agent(current_state, run_config)
            elif node == "scenario_generator":
                from agents.scenario_agent import scenario_agent
                res = scenario_agent(current_state, run_config)
            elif node == "test_case_generator":
                from agents.testcase_agent import testcase_agent
                res = testcase_agent(current_state, run_config)
            elif node == "coverage_agent":
                from agents.coverage_agent import coverage_agent
                res = coverage_agent(current_state, run_config)
            elif node == "automation_agent":
                from agents.automation_agent import automation_agent
                res = automation_agent(current_state, run_config)
            elif node == "review_agent":
                from agents.review_agent import review_agent
                res = review_agent(current_state, run_config)
            elif node == "metrics_agent":
                from agents.metrics_agent import metrics_agent
                res = metrics_agent(current_state, run_config)
                
            # Update state dict
            current_state.update(res)
            current_state = normalize_state(current_state)
        except Exception as err:
            current_state["errors"].append(f"Node '{node}' crashed: {str(err)}")
            
    # Post-run: EvaluationAgent
    status_box.update(label="Executing Agent 8: Independent Post-Run Evaluator...", state="running")
    progress_bar.progress((len(nodes)) / (len(nodes) + 1))
    
    try:
        st.session_state.last_active_agent = "evaluation_agent"
        eval_agent = EvaluationAgent(api_key=api_key, model_name=model_flash, request_timeout=request_timeout, model_provider=model_provider)
        eval_metrics = eval_agent.evaluate_pipeline(current_state)
        current_state.setdefault("metrics", {})
        current_state["metrics"]["evaluation_scores"] = eval_metrics
        current_state["metrics"]["hallucination_rate"] = eval_metrics.get("hallucination_rate", 0.0)
    except Exception as err:
        current_state["errors"].append(f"EvaluationAgent crashed: {str(err)}")
        
    status_box.update(label="Pipeline run completed successfully!", state="complete")
    progress_bar.progress(1.0)
    
    st.session_state.pipeline_state = current_state
    st.session_state.run_mode = "idle"
    st.session_state.last_active_agent = "Idle"
    st.session_state.step_index = 0
    st.success("End-to-End QA Pipeline execution finished!")

elif st.session_state.run_mode == "running_step":
    step_name, node = pipeline_steps[st.session_state.step_index]
    current_state = st.session_state.pipeline_state

    if st.session_state.step_index == 0:
        current_state = {
            "raw_input": raw_input_text,
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
    
    with st.spinner(f"Running step: {step_name}..."):
        try:
            st.session_state.last_active_agent = node
            if node == "requirement_interpreter":
                from agents.requirement_agent import requirement_interpreter_agent
                res = requirement_interpreter_agent(current_state, run_config)
            elif node == "scenario_generator":
                from agents.scenario_agent import scenario_agent
                res = scenario_agent(current_state, run_config)
            elif node == "test_case_generator":
                from agents.testcase_agent import testcase_agent
                res = testcase_agent(current_state, run_config)
            elif node == "coverage_agent":
                from agents.coverage_agent import coverage_agent
                res = coverage_agent(current_state, run_config)
            elif node == "automation_agent":
                from agents.automation_agent import automation_agent
                res = automation_agent(current_state, run_config)
            elif node == "review_agent":
                from agents.review_agent import review_agent
                res = review_agent(current_state, run_config)
            elif node == "metrics_agent":
                from agents.metrics_agent import metrics_agent
                res = metrics_agent(current_state, run_config)
            elif node == "evaluation_agent":
                eval_agent = EvaluationAgent(api_key=api_key, model_name=model_flash, request_timeout=request_timeout, model_provider=model_provider)
                res_eval = eval_agent.evaluate_pipeline(current_state)
                current_state.setdefault("metrics", {})
                current_state["metrics"]["evaluation_scores"] = res_eval
                current_state["metrics"]["hallucination_rate"] = res_eval.get("hallucination_rate", 0.0)
                res = {"metrics": current_state["metrics"]}
                
            current_state.update(res)
            current_state = normalize_state(current_state)
            st.session_state.pipeline_state = current_state
            st.session_state.step_index += 1
            st.toast(f"Finished {step_name} step!", icon="✅")
        except Exception as err:
            st.session_state.pipeline_state["errors"].append(f"Step '{step_name}' crashed: {str(err)}")
            st.error(f"Error during step: {err}")
            
    st.session_state.run_mode = "idle"
    st.session_state.last_active_agent = "Idle"

# ----------------- EXPORT ACTIONS -----------------
def get_export_buttons(tab_data: List[Dict[str, Any]], fields: List[str], file_prefix: str):
    """Render export download buttons for Excel, CSV and Jira."""
    excel_file = export_to_excel(st.session_state.pipeline_state)
    csv_str = export_to_csv(tab_data, fields)
    jira_json = export_to_jira_format(st.session_state.pipeline_state)
    
    col_ex1, col_ex2, col_ex3 = st.columns(3)
    with col_ex1:
        st.download_button(
            label="📊 Export Full QA Package (Excel)",
            data=excel_file,
            file_name=f"{file_prefix}_QA_Package.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{file_prefix}_xlsx_btn"
        )
    with col_ex2:
        st.download_button(
            label="📄 Export Tab Data (CSV)",
            data=csv_str,
            file_name=f"{file_prefix}_data.csv",
            mime="text/csv",
            key=f"{file_prefix}_csv_btn"
        )
    with col_ex3:
        st.download_button(
            label="🎫 Download Jira Import Format (JSON)",
            data=jira_json,
            file_name=f"{file_prefix}_jira_import.json",
            mime="application/json",
            key=f"{file_prefix}_jira_btn"
        )

# Render error list if any
if st.session_state.pipeline_state.get("errors"):
    with st.expander("⚠️ Pipeline Warnings/Errors", expanded=True):
        for err in st.session_state.pipeline_state["errors"]:
            st.error(err)

# ----------------- MAIN TABS -----------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋 Requirements", 
    "🎯 Test Scenarios", 
    "📝 Test Cases", 
    "🧬 RTM & Coverage", 
    "💻 Automation Scripts", 
    "🔍 QA Judge", 
    "📈 Metrics & Eval"
])

p_state = normalize_state(st.session_state.pipeline_state)
if p_state.get("requirements") and p_state.get("rtm"):
    from agents.metrics_agent import metrics_agent as calculate_metrics_agent
    p_state.update(calculate_metrics_agent(p_state))
st.session_state.pipeline_state = p_state

# TAB 1: Requirements
with tab1:
    st.subheader("Parsed Functional Requirements & Entities")
    if p_state.get("requirements"):
        get_export_buttons(p_state["requirements"], ["id", "text", "type"], "requirements")
        
        # Display as styled dataframe
        df_reqs = pd.DataFrame(p_state["requirements"])
        st.dataframe(df_reqs, use_container_width=True)
        
        # Business Rules & Entities
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.subheader("Business Rules")
            if p_state.get("business_rules"):
                df_rules = pd.DataFrame(p_state["business_rules"])
                st.dataframe(df_rules, use_container_width=True)
            else:
                st.info("No business rules extracted.")
                
        with col_r2:
            st.subheader("System Entities & Relations")
            for ent in p_state.get("entities", []):
                with st.container():
                    st.markdown(f"**Entity:** {ent.get('name')}")
                    st.markdown(f"- Attributes: {', '.join(ent.get('attributes', []))}")
                    st.markdown(f"- Relationships: {', '.join(ent.get('relationships', []))}")
                    st.divider()
                    
        # Assumptions & Ambiguities
        st.subheader("Assumptions & Incomplete Requirements")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.markdown("#### Assumptions Made:")
            for idx, ass in enumerate(p_state.get("assumptions", [])):
                st.info(f"{idx+1}. {ass}")
        with col_a2:
            st.markdown("#### Ambiguities & Clarifications Needed:")
            for idx, amb in enumerate(p_state.get("ambiguities", [])):
                st.warning(f"{idx+1}. {amb}")
    else:
        st.info("Run the pipeline to extract and parse functional requirements.")

# TAB 2: Test Scenarios
with tab2:
    st.subheader("Generated Test Scenarios")
    if p_state.get("scenarios"):
        get_export_buttons(p_state["scenarios"], ["scenario_id", "req_id", "type", "title", "description"], "scenarios")
        
        # Filter scenario type
        sc_types = ["all", "functional", "negative", "boundary", "integration", "security"]
        selected_type = st.selectbox("Filter Scenarios by Type", sc_types)
        
        filtered_scenarios = p_state["scenarios"]
        if selected_type != "all":
            filtered_scenarios = [s for s in p_state["scenarios"] if s.get("type") == selected_type]
            
        for sc in filtered_scenarios:
            with st.container():
                st.markdown(f"### {sc.get('scenario_id')}: {sc.get('title')}")
                st.markdown(f"**Mapped Req:** `{sc.get('req_id')}` | **Scenario Type:** `{sc.get('type')}`")
                st.write(sc.get("description"))
                st.divider()
    else:
        st.info("Run the pipeline to generate test scenarios.")

# TAB 3: Test Cases
with tab3:
    st.subheader("Detailed Test Cases Grid")
    if p_state.get("test_cases"):
        get_export_buttons(p_state["test_cases"], ["test_case_id", "scenario_id", "req_id", "title", "priority", "test_type"], "test_cases")
        
        # Display grid of test cases
        for tc in p_state["test_cases"]:
            with st.container():
                st.markdown(f"### 📝 {tc.get('test_case_id')}: {tc.get('title')}")
                col_tc1, col_tc2, col_tc3 = st.columns(3)
                col_tc1.markdown(f"**Scenario ID:** `{tc.get('scenario_id')}`")
                col_tc2.markdown(f"**Mapped Req:** `{tc.get('req_id')}`")
                col_tc3.markdown(f"**Priority:** `{tc.get('priority')}` | **Type:** `{tc.get('test_type')}`")
                
                st.markdown(f"**Preconditions:**\n{tc.get('preconditions')}")
                
                # Render steps table
                steps_df = pd.DataFrame(tc.get("steps", []))
                if not steps_df.empty:
                    st.table(steps_df)
                    
                # Wow features data & queries
                col_wow1, col_wow2 = st.columns(2)
                with col_wow1:
                    st.markdown("**💡 Synthesized Test Data:**")
                    st.json(tc.get("test_data", {}))
                with col_wow2:
                    if tc.get("sql_query"):
                        st.markdown("**🛢️ Verification SQL Query:**")
                        st.code(tc.get("sql_query"), language="sql")
                st.divider()
    else:
        st.info("Run the pipeline to expand scenarios into test cases.")

# TAB 4: Coverage
with tab4:
    st.subheader("Requirement Traceability Matrix (RTM)")
    if p_state.get("rtm"):
        get_export_buttons(p_state["test_cases"], ["test_case_id", "req_id"], "rtm")
        
        # Build Heatmap matrix
        rtm_data = []
        for req in p_state.get("requirements", []):
            req_id = req.get("id")
            tc_ids = p_state["rtm"].get(req_id, [])
            rtm_data.append({
                "Requirement ID": req_id,
                "Requirement Text": req.get("text"),
                "Test Cases Count": len(tc_ids),
                "Test Case IDs": ", ".join(tc_ids) if tc_ids else "None",
                "Status": "✅ Covered" if tc_ids else "❌ Uncovered"
            })
            
        df_rtm = pd.DataFrame(rtm_data)
        
        # Apply visual heatmap highlight using streamlit dataframe styling
        def highlight_status(val):
            color = '#f85149' if '❌' in val else '#1f6feb'
            return f'background-color: {color}; color: white; font-weight: bold;'
            
        styled_df = df_rtm.style.map(highlight_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True)
        
        # Display coverage gaps in big red boxes
        if p_state.get("coverage_gaps"):
            st.error("### ⚠️ Coverage Gaps Detected")
            for gap in p_state["coverage_gaps"]:
                st.markdown(f"- Requirement **{gap}** has zero test cases mapping to it.")
        else:
            st.success("✅ 100% Requirement Coverage achieved. No coverage gaps detected.")
            
        # Display duplicate pairs
        st.subheader("Duplicate/Redundant Test Cases Analysis")
        unmapped = p_state["metrics"].get("unmapped_test_cases", [])
        if unmapped:
            st.warning(f"{len(unmapped)} test case(s) reference requirement IDs that were not extracted, so they are excluded from requirement coverage.")
            st.dataframe(pd.DataFrame(unmapped), use_container_width=True)

        semantic_maps = p_state["metrics"].get("semantic_requirement_mappings", [])
        if semantic_maps:
            with st.expander("Requirement ID remapping basis"):
                st.dataframe(pd.DataFrame(semantic_maps), use_container_width=True)

        dups = p_state["metrics"].get("duplicate_test_cases", [])
        if dups:
            st.warning(f"Detected {len(dups)} duplicate or highly redundant test case pairs.")
            for dup in dups:
                st.markdown(f"- **{dup.get('tc1')}** and **{dup.get('tc2')}** share a similarity of **{dup.get('similarity_score')*100}%**.")
        else:
            st.success("No redundant test cases found.")
    else:
        st.info("Run the pipeline to map coverage and build RTM.")

# TAB 5: Automation
with tab5:
    st.subheader("Generated Test Automation Scripts")
    if p_state.get("automation_scripts"):
        get_export_buttons([], [], "automation")
        
        tc_ids_w_scripts = list(p_state["automation_scripts"].keys())
        selected_tc = st.selectbox("Select Test Case for Script View", tc_ids_w_scripts)
        
        if selected_tc:
            script_info = p_state["automation_scripts"][selected_tc]
            framework = script_info.get("framework", "python").lower()
            code_script = script_info.get("script", "")
            
            st.markdown(f"### Automation Script for `{selected_tc}`")
            st.markdown(f"**Target Framework:** `{framework}`")
            
            # Map syntax highlighting
            lang = "python"
            if framework == "karate" or framework == "cucumber":
                lang = "gherkin"
                
            st.code(code_script, language=lang)
    else:
        st.info("No automation scripts generated. Ensure test cases are candidates (pytest, playwright, karate, cucumber).")

# TAB 6: Review
with tab6:
    st.subheader("QA Architect Peer Review Findings")
    if p_state.get("review_findings"):
        get_export_buttons(p_state["review_findings"], ["id", "severity", "category", "description"], "review")
        
        col_sc1, col_sc2 = st.columns([1, 3])
        with col_sc1:
            st.markdown("### Quality Score")
            overall_score = p_state["metrics"].get("overall_quality_score", 0.0)
            st.metric("Design Quality", f"{overall_score}/10")
            
        with col_sc2:
            st.markdown("### Findings & Action Items")
            for find in p_state.get("review_findings", []):
                sev = find.get("severity", "Medium")
                badge_class = "badge-red" if sev == "High" else ("badge-amber" if sev == "Medium" else "badge-green")
                
                st.markdown(f"""
                <div class="card-container">
                    <span class="{badge_class}">{sev} Severity</span>
                    <strong>Category:</strong> {find.get('category')} | <strong>ID:</strong> {find.get('id')}
                    <p style="margin-top:10px;">{find.get('description')}</p>
                </div>
                """, unsafe_allow_html=True)
                
        # Detailed test case scores
        st.subheader("Test Case Quality Scores")
        tcs_scores = []
        for tc_id, score_info in p_state.get("quality_scores", {}).items():
            tcs_scores.append({
                "Test Case ID": tc_id,
                "Score": score_info.get("score"),
                "Reason": score_info.get("reason")
            })
            
        if tcs_scores:
            df_scores = pd.DataFrame(tcs_scores)
            st.dataframe(df_scores, use_container_width=True)
            
            # Bar chart of quality scores
            chart_df = df_scores.set_index("Test Case ID")[["Score"]]
            st.bar_chart(chart_df)
    else:
        st.info("Run the pipeline to trigger QA Architect review.")

# TAB 7: Metrics & Eval
with tab7:
    st.subheader("QA Performance & System Evaluation Dashboard")
    
    # Render KPI Cards
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    m = p_state["metrics"]
    
    covered_count = m.get('covered_requirements', 0)
    total_count = m.get('total_requirements', len(p_state.get('requirements', [])))
    col_m1.metric("Requirements Coverage", f"{m.get('req_coverage_pct', 0.0)}%")
    col_m1.caption(f"{covered_count} / {total_count} requirements covered")
    col_m2.metric("Automation Rate", f"{m.get('auto_coverage_pct', 0.0)}%")
    col_m3.metric("Risk Coverage (High Risk)", f"{m.get('risk_coverage_pct', 0.0)}%")
    col_m4.metric("Avg Quality Score", f"{m.get('test_design_quality_score', 0.0)}/10")
    
    st.divider()
    st.caption(
        f"Requirement coverage basis: {covered_count} of {total_count} extracted requirements have at least one mapped test case "
        f"({covered_count}/{total_count} * 100)."
    )
    coverage_audit = m.get("coverage_audit", [])
    if coverage_audit:
        with st.expander("Requirement coverage audit", expanded=True):
            st.dataframe(pd.DataFrame(coverage_audit), use_container_width=True)
    if m.get("unmapped_test_cases"):
        st.warning(f"{len(m.get('unmapped_test_cases', []))} test case(s) were excluded because their requirement IDs could not be mapped.")
    
    # Injected token and cost tracking
    st.subheader("🪙 Token Usage & Cost Estimator")
    col_cost1, col_cost2 = st.columns(2)
    with col_cost1:
        st.metric("Total Tokens Utilized", f"{m.get('total_input_tokens', 0) + m.get('total_output_tokens', 0):,}")
        st.write(f"- **Prompt (Input) Tokens:** {m.get('total_input_tokens', 0):,}")
        st.write(f"- **Completion (Output) Tokens:** {m.get('total_output_tokens', 0):,}")
    with col_cost2:
        st.metric("Estimated Cost (USD)", f"${m.get('total_cost', 0.0):.5f}")
        st.write("Calculated using default provider pricing assumptions configured in utils/llm.py.")
        
    with st.expander("📋 Model Call Breakdown"):
        calls_df = pd.DataFrame(m.get("model_calls", []))
        if not calls_df.empty:
            st.dataframe(calls_df, use_container_width=True)
            
    # Evaluation Agent Results
    st.divider()
    st.subheader("⚖️ Independent Evaluation Agent (LLM-as-Judge)")
    
    eval_data = m.get("evaluation_scores", {})
    if eval_data:
        col_ev1, col_ev2, col_ev3 = st.columns(3)
        
        # Understanding Score Card
        with col_ev1:
            score_u = eval_data.get("requirement_understanding", {}).get("score", 0)
            reason_u = eval_data.get("requirement_understanding", {}).get("reason", "")
            st.markdown(f"""
            <div class="card-container" style="min-height:220px;">
                <h4>Requirement Understanding</h4>
                <h1 style="color:#58a6ff;margin:5px 0;">{score_u}/10</h1>
                <p style="font-size:0.85rem;color:#8b949e;">{reason_u}</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Accuracy Score Card
        with col_ev2:
            score_a = eval_data.get("test_case_accuracy", {}).get("score", 0)
            reason_a = eval_data.get("test_case_accuracy", {}).get("reason", "")
            st.markdown(f"""
            <div class="card-container" style="min-height:220px;">
                <h4>Test Case Accuracy</h4>
                <h1 style="color:#58a6ff;margin:5px 0;">{score_a}/10</h1>
                <p style="font-size:0.85rem;color:#8b949e;">{reason_a}</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Hallucination Score Card
        with col_ev3:
            hallucination_rate = eval_data.get("hallucination_rate", 0.0)
            st.markdown(f"""
            <div class="card-container" style="min-height:220px;">
                <h4>Hallucination Rate</h4>
                <h1 style="color:#f85149;margin:5px 0;">{hallucination_rate}%</h1>
                <p style="font-size:0.85rem;color:#8b949e;">Percentage of evaluated test cases containing steps not traceable to requirements.</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Script validity scorecard
        st.subheader("Automation Script Validation (AST Syntax & Structure Checks)")
        validations = eval_data.get("automation_script_validity", {})
        
        val_list = []
        for tc_id, info in validations.items():
            val_list.append({
                "Test Case ID": tc_id,
                "Valid": "✅ Passed" if info.get("valid") else "❌ Failed",
                "Validation Explanation": info.get("reason")
            })
            
        if val_list:
            df_val = pd.DataFrame(val_list)
            st.dataframe(df_val, use_container_width=True)
            
        # Hallucination detailed logs
        with st.expander("🔍 Hallucination Evaluation Details"):
            details = eval_data.get("hallucination_details", {})
            for tc_id, info in details.items():
                st.markdown(f"**Test Case `{tc_id}`:**")
                st.markdown(f"- **Hallucinated?** {info.get('has_hallucination')}")
                st.markdown(f"- **Analysis:** {info.get('reason')}")
                st.divider()
    else:
        st.info("Run the pipeline to calculate independent evaluation scores.")
