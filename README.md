# AI Test Architect Agent Platform 🤖🛡️

**Track:** Agents for Business (Kaggle AI Agents Capstone)

An end-to-end agentic pipeline that autonomously converts software requirements (PDF/Word/Text) into a comprehensive QA deliverables package. The platform uses a **7-agent LangGraph pipeline** and an independent **Evaluation Agent (LLM-as-Judge)** post-run grader to orchestrate and evaluate the design.

---

## 🛠️ Tech Stack

- **Orchestration Framework:** LangGraph (stateful workflows)
- **Generative AI Model:** Configurable provider backend: OpenAI via `openai` or Google Gemini via `google-genai`
- **Frontend Dashboard:** Streamlit
- **Vector Database:** ChromaDB (local persistence for semantic duplicate test case checks)
- **Document Parsers:** PyMuPDF (`fitz` for PDFs) & `python-docx` (for MS Word files)
- **Data Exporting:** `openpyxl` (styled Excel sheets), CSV, and Jira-compatible JSON

---

## 📂 Repository Structure

```
ai-test-architect-agent/
├── app.py                    # Streamlit main entry point & dashboard UI
├── requirements.txt          # Package dependencies
├── README.md                 # Setup & usage instructions (this file)
├── .env.example              # Example environment variables
├── agents/
│   ├── __init__.py
│   ├── state.py              # LangGraph AgentState TypedDict definition
│   ├── graph.py              # LangGraph StateGraph pipeline wiring
│   ├── requirement_agent.py  # Agent 1: Requirement Interpreter
│   ├── scenario_agent.py     # Agent 2: Scenario Generator
│   ├── testcase_agent.py     # Agent 3: Test Case Generator
│   ├── coverage_agent.py     # Agent 4: Coverage Agent (RTM & ChromaDB Duplication)
│   ├── automation_agent.py   # Agent 5: Automation Agent (Pytest, Playwright, Karate, Cucumber)
│   ├── review_agent.py       # Agent 6: QA Architect Reviewer (LLM-as-Judge reviewer)
│   ├── metrics_agent.py      # Agent 7: QA Metrics Agent
│   └── evaluation_agent.py   # EvaluationAgent (independent post-run judge)
├── utils/
│   ├── document_parser.py    # PyMuPDF + python-docx parser helper
│   ├── exporter.py           # Styled Excel, CSV, and Jira JSON exporters
│   └── prompts.py            # Custom prompt templates for each agent node
└── examples/
    └── sample_requirements.txt  # Default test requirements demo text
```

---

## 🚀 Getting Started

### 1. Installation

Clone the repository and install the dependencies listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. API Key Configuration

Create a `.env` file in the root directory (using `.env.example` as a reference) and define the key for your selected provider:

```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

*Alternatively, you can paste the API key directly in the Streamlit sidebar during execution.*

This project was initially developed during the Kaggle-Google Vibe Coding Workshop using Antigravity with Gemini models. Due to Gemini API quota limitations during development, the model provider was switched to OpenAI while preserving the same agent architecture, workflows, and functionality. The change is limited to the LLM backend and API configuration.

### 3. Run the Application

Launch the Streamlit dashboard:

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## 🕵️‍♂️ Agent Pipeline & Features

1. **Requirement Interpreter:** Extracts functional requirements, business rules, validations, entities/relationships, assumptions, and ambiguities.
2. **Scenario Generator:** Automatically writes functional, negative, boundary, integration, and security test scenarios.
3. **Test Case Generator:** Expands scenarios into detailed test cases with setup, steps, and expected results.
   - **WOW Feature:** Synthesizes realistic mock test data and generates SQL database verification queries where applicable.
4. **Coverage Agent:** Builds the Requirement Traceability Matrix (RTM) mapping requirements to test cases. Checks for coverage gaps and uses **ChromaDB semantic search** to flag duplicate test case designs.
5. **Automation Agent:** Converts test cases to copy-pasteable Pytest, Playwright, Karate (API), or Cucumber (BDD Gherkin) scripts based on test type tag (uses the selected provider's smaller/faster model for speed-sensitive nodes).
6. **Review Agent (LLM-as-Judge):** Roleplays a senior QA director, flagging weak steps, missing validations, and scoring each test case from 0 to 10.
7. **QA Metrics Agent:** Aggregates dashboard KPIs (requirement coverage %, automation rate %, risk coverage, design quality, cost & token trackers).
8. **Evaluation Agent (Post-Run Judge):** Evaluates the pipeline's own performance. Measures understanding correctness, test case accuracy, hallucination rates, and compiles code/syntax checks (uses AST parsing for Python scripts and structure checks for Karate/Gherkin).
