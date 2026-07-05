# AI Test Architect Agent Platform

## Project Description

The **AI Test Architect Agent Platform** is an end-to-end multi-agent QA design system that turns raw software requirements into a complete, reviewable testing package. It accepts requirement documents in **PDF, Word, or plain text** format and produces structured requirements, test scenarios, detailed test cases, traceability reports, automation script drafts, QA review findings, quality metrics, and independent evaluation scores.

This project was built for the **Agents for Business** track because it solves a practical business workflow: helping software and QA teams move from unclear requirements to organized, auditable test design artifacts faster.

Traditional test planning often requires a QA engineer to manually read long requirement documents, identify business rules, design positive and negative scenarios, create detailed test cases, map coverage, remove duplicate cases, and decide which tests are suitable for automation. That process is valuable, but it is also slow, repetitive, and easy to make inconsistent under delivery pressure.

This platform treats test design as a collaborative agent workflow instead of a single prompt. Each agent has a focused QA responsibility, and each stage enriches a shared project state. The result is not just generated text, but a structured QA deliverables package that can be inspected, exported, reviewed, and improved.

## What I Built

I built a **Streamlit-based dashboard** backed by a **LangGraph multi-agent pipeline**. A user can upload a requirements document, choose an LLM provider, run the pipeline end to end or step by step, and review all generated QA artifacts inside the app.

The system supports both **OpenAI** and **Google Gemini** as configurable model providers. It also uses **ChromaDB** for semantic duplicate detection, **PyMuPDF** and **python-docx** for document parsing, and export utilities for Excel, CSV, and Jira-compatible JSON.

The application is designed to behave like a junior-to-mid QA architecture assistant that can draft, organize, and evaluate testing assets while leaving final judgment to the human QA owner.

## Why This Matters

Good test design is more than writing test cases. A QA architect must understand the requirement, identify missing details, cover business rules, design edge cases, avoid redundant testing, connect tests back to requirements, and evaluate whether the final test suite is strong enough.

LLMs can help with this work, but a single generation step is not enough. Without structure, generated test cases can be incomplete, duplicated, weakly mapped, or disconnected from the original requirement.

This project addresses that by combining:

- Agent specialization
- Stateful orchestration
- Requirement traceability
- Semantic duplicate detection
- Automation script generation
- LLM-as-Judge review
- Post-run evaluation metrics

Together, these pieces make the system more transparent and useful for real QA planning.

## Multi-Agent Architecture

The core workflow is implemented as a **LangGraph StateGraph**. A shared `AgentState` object carries the raw input and all generated artifacts between agents. Each agent reads the current state, performs its role, and writes new structured output back into the state.

The pipeline includes:

1. **Requirement Interpreter**
2. **Scenario Generator**
3. **Test Case Generator**
4. **Coverage Agent**
5. **Automation Agent**
6. **Review Agent**
7. **Metrics Agent**
8. **Independent Evaluation Agent**

The first seven agents form the main generation and review workflow. The Evaluation Agent runs after the main pipeline to grade the output independently.

## Agent Responsibilities

### 1. Requirement Interpreter

The Requirement Interpreter reads the uploaded requirement text and extracts structured information such as functional requirements, business rules, entities, validations, assumptions, and ambiguities.

This step is important because it converts an unstructured document into a format that later agents can reason over. It also highlights incomplete or unclear requirement areas that may need human clarification.

### 2. Scenario Generator

The Scenario Generator converts extracted requirements into test scenarios. It creates coverage across several testing angles, including:

- Functional scenarios
- Negative scenarios
- Boundary scenarios
- Integration scenarios
- Security-related scenarios

This helps the system avoid producing only happy-path tests.

### 3. Test Case Generator

The Test Case Generator expands scenarios into detailed QA test cases. Each test case can include:

- Test case ID
- Scenario mapping
- Requirement mapping
- Priority
- Preconditions
- Step-by-step actions
- Expected results
- Test data
- SQL verification queries where applicable
- Automation suitability tags

This stage turns high-level scenario ideas into practical test assets that a QA team can review or refine.

### 4. Coverage Agent

The Coverage Agent builds the **Requirement Traceability Matrix (RTM)**. It maps test cases back to the extracted requirements, calculates requirement coverage, identifies coverage gaps, and reports unmapped test cases.

It also uses **ChromaDB semantic search** to detect duplicate or highly similar test cases. This is useful because redundant tests may not have identical wording but can still test the same behavior.

### 5. Automation Agent

The Automation Agent generates draft automation scripts for eligible test cases. Depending on the test type, it can produce scripts in formats such as:

- Pytest
- Playwright
- Karate
- Cucumber / Gherkin

Manual-only cases are skipped so the automation output remains focused on realistic candidates.

### 6. Review Agent

The Review Agent acts like a senior QA architect reviewing the generated test design. It identifies weak steps, missing validations, risky assumptions, and potential quality issues.

It also assigns quality scores so the user can quickly identify where test cases need improvement before use.

### 7. Metrics Agent

The Metrics Agent aggregates the dashboard indicators. It calculates and displays values such as coverage percentage, automation rate, quality score, duplicate counts, token usage, model call details, latency, and estimated cost.

These metrics make the system more practical because users can inspect both the quality and the cost of a run.

### 8. Independent Evaluation Agent

The Evaluation Agent is intentionally separate from the main pipeline. It performs a post-run assessment of the generated output, including:

- Requirement understanding score
- Test case accuracy score
- Coverage completeness
- Automation script validity
- Hallucination checks

For Python-based scripts, it uses AST parsing to check syntax validity. For Karate and Cucumber outputs, it checks for expected feature, scenario, and Given/When/Then structure.

## User Experience

The user interacts with the system through a Streamlit dashboard. The sidebar allows the user to:

- Upload a PDF, DOCX, or TXT requirement document
- Paste requirement text directly
- Select OpenAI or Gemini as the model provider
- Choose reasoning and speed-oriented models
- Run the full pipeline
- Run the system step by step
- Enable a human-in-the-loop interrupt before review
- Load pre-run demo data
- Reset the session

The main dashboard displays the results in organized tabs:

- Parsed requirements and entities
- Generated scenarios
- Detailed test cases
- Requirement traceability matrix
- Automation scripts
- QA review findings
- Metrics and evaluation dashboard

The system also provides export options so generated artifacts can be moved into other QA workflows.

## Outputs Generated

The platform produces a full QA design package:

- Parsed functional requirements
- Business rules
- System entities and relationships
- Assumptions and ambiguities
- Test scenarios
- Detailed test cases
- Mock test data
- SQL verification queries
- Requirement Traceability Matrix
- Coverage gap report
- Duplicate test case analysis
- Automation script drafts
- QA review findings
- Test case quality scores
- Token and cost metrics
- Independent evaluation results

## Key Features

### Requirement-to-Test Traceability

Every test case is mapped back to requirements wherever possible. This helps users see whether all requirements have test coverage and where gaps remain.

### Semantic Duplicate Detection

The system uses vector similarity to identify redundant test cases that may not look identical but cover the same intent. This helps keep the test suite lean and meaningful.

### Automation Drafting

Automation-ready test cases can be converted into script drafts for common testing frameworks. These scripts are intended as a starting point for QA automation engineers.

### Built-In Review

The Review Agent adds a quality-control layer by analyzing generated test cases and flagging weaknesses. This makes the output more audit-friendly than direct generation alone.

### Independent Evaluation

The post-run Evaluation Agent scores the pipeline's own output. This gives users a clearer view of how well the system understood the requirements and whether the generated tests are accurate and grounded.

## Technical Implementation

The repository is organized around clear responsibilities:

- `app.py` contains the Streamlit dashboard and execution flow.
- `agents/graph.py` defines the LangGraph workflow.
- `agents/state.py` defines the shared state structure.
- `agents/` contains the individual agent implementations.
- `utils/document_parser.py` parses PDF, DOCX, and text inputs.
- `utils/prompts.py` stores prompt templates.
- `utils/llm.py` handles provider-specific LLM calls and token/cost tracking.
- `utils/vector_store.py` supports semantic duplicate checks.
- `utils/exporter.py` creates Excel, CSV, and Jira-compatible exports.
- `test_pipeline.py` validates important pipeline behavior.

## Strengths

The main strength of this project is its structured workflow. Instead of asking one model to produce everything at once, the platform decomposes QA architecture into smaller expert tasks. This makes the system easier to inspect, debug, and improve.

Another strength is auditability. The generated output includes traceability, duplicate analysis, review findings, metrics, and evaluation scores. These make the results more useful for real-world QA teams, where generated content must be explainable and reviewable.

The dashboard also makes the system accessible. A user does not need to understand LangGraph internals to upload requirements, run the pipeline, and inspect the QA deliverables.

## Limitations

The system still depends on the quality of the input requirements and the selected LLM model. If requirements are vague or incomplete, the output may require more human review.

Generated automation scripts should be treated as drafts, not production-ready code. They need environment-specific updates, locators, fixtures, credentials, and execution validation before use in a real test suite.

The hallucination check samples only a subset of test cases when the generated set is large to control cost and latency. Semantic duplicate detection also depends on embedding quality and threshold choices.

## Future Enhancements

Future improvements could include:

- Direct integration with Jira, Azure DevOps, or test management tools
- Live execution of generated automation scripts
- Configurable quality gates before export
- More domain-specific prompt profiles
- Stronger validation for API and BDD script outputs
- Persistent project history across requirement versions
- Human approval checkpoints between more pipeline stages
- Side-by-side comparison of multiple pipeline runs

## Conclusion

The **AI Test Architect Agent Platform** demonstrates how agentic systems can support a real business workflow in software quality assurance. It transforms raw requirements into structured QA artifacts, checks coverage, drafts automation, reviews quality, and evaluates its own output.

The goal is not to replace QA engineers. The goal is to give QA teams a faster, more organized starting point so they can focus their judgment on the highest-value decisions: risk, coverage, correctness, and release confidence.
