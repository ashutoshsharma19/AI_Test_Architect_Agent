# YouTube Demo Storyboard - AI Test Architect Agent Platform

## Target Video

- Duration: 5 minutes
- Format: Screen recording with voiceover
- Resolution: 1920x1080
- Style: Clean project walkthrough, focused on dashboard output and agent workflow

## Recording Setup

1. Open a terminal in the project folder.
2. Run:

```powershell
streamlit run app.py
```

3. Open the Streamlit URL in the browser, usually:

```text
http://localhost:8501
```

4. Use the built-in "Load Pre-run Demo Data" button for a smooth video. This avoids waiting for live LLM calls during recording.
5. Hide or blur API keys before recording.
6. Keep browser zoom around 90% to 100%.
7. Record the screen first, then add the voiceover from `YouTube_Voiceover_5min.md`.

## Shot-by-Shot Plan

### 0:00 - 0:25 | Project Opening

**Screen:** Show the Streamlit dashboard title: "AI Test Architect Agent Platform".

**Action:** Slowly move the cursor over the main heading and sidebar.

**Voiceover:** Introduce the project and explain that it converts raw requirements into QA deliverables.

**Editing note:** Add a simple title overlay:

```text
AI Test Architect Agent Platform
Requirements to QA Deliverables
```

### 0:25 - 0:55 | Problem Statement

**Screen:** Show a requirement document or the sidebar text input area.

**Action:** Highlight the idea that requirements start as plain, unstructured text.

**Voiceover:** Explain the manual QA design problem: reading requirements, creating scenarios, mapping coverage, avoiding duplicates, and preparing automation.

**Editing note:** Use a light zoom-in on the input requirements.

### 0:55 - 1:25 | Input and Dashboard

**Screen:** Show the sidebar.

**Action:** Point to:

- Model provider
- API key field
- Upload requirement document
- Requirement preview
- Run full pipeline
- Step-by-step mode
- Human-in-the-loop interrupt
- Load pre-run demo data

**Voiceover:** Explain supported inputs and dashboard controls.

**Editing note:** Do not show a real API key.

### 1:25 - 2:15 | Multi-Agent Architecture

**Screen:** Show the generated tabs in order:

- Parsed Requirements
- Test Scenarios
- Detailed Test Cases

**Action:** Scroll through requirements, scenarios, and one detailed test case.

**Voiceover:** Explain the Requirement Interpreter, Scenario Generator, and Test Case Generator.

**Important visual:** In the test case tab, show:

- Preconditions
- Steps
- Expected results
- Test data
- SQL verification query

### 2:15 - 3:05 | Coverage, Duplicates, and Automation

**Screen:** Open the RTM tab.

**Action:** Show requirement-to-test-case mapping, coverage gaps, and duplicate analysis.

**Then:** Open the Automation tab.

**Action:** Select one generated script, ideally Playwright or Pytest.

**Voiceover:** Explain traceability, ChromaDB semantic duplicate checks, and automation script drafting.

**Editing note:** Add a brief callout:

```text
RTM + Duplicate Detection + Automation Drafts
```

### 3:05 - 3:45 | Review and Independent Evaluation

**Screen:** Open the QA Review tab.

**Action:** Show quality score and findings.

**Then:** Open the Metrics / Evaluation tab.

**Action:** Show independent evaluation scores and script validation table.

**Voiceover:** Explain the Review Agent and post-run Evaluation Agent.

**Important visual:** Show hallucination rate, script validity, or requirement understanding score if visible.

### 3:45 - 4:25 | Outputs and Exports

**Screen:** Show download buttons and dashboard tabs.

**Action:** Hover over Excel, CSV, or Jira JSON export buttons.

**Voiceover:** Explain that outputs can move into downstream QA workflows.

**Editing note:** This is a good place for a quick montage across tabs.

### 4:25 - 4:50 | Tech Stack

**Screen:** Show the repository structure in VS Code or terminal.

**Action:** Briefly show:

- `app.py`
- `agents/`
- `agents/graph.py`
- `agents/state.py`
- `utils/`

**Voiceover:** Mention Python, LangGraph, Streamlit, OpenAI/Gemini, ChromaDB, PyMuPDF, python-docx, and openpyxl.

### 4:50 - 5:10 | Closing

**Screen:** Return to the metrics dashboard or project title.

**Action:** Keep the view stable.

**Voiceover:** Summarize the value: faster QA design, better traceability, review, and confidence.

**Editing note:** End with a simple closing overlay:

```text
AI Test Architect Agent Platform
Faster QA Design. Better Traceability. Reviewable Outputs.
```

## Suggested Editing Timeline

| Time | Visual | Audio |
|---|---|---|
| 0:00 | Dashboard title | Opening |
| 0:25 | Requirement input | Problem statement |
| 0:55 | Sidebar controls | Input workflow |
| 1:25 | Requirements, scenarios, test cases | Agent architecture |
| 2:15 | RTM and automation | Coverage and scripts |
| 3:05 | Review and evaluation | Quality checks |
| 3:45 | Exports and metrics | Outputs |
| 4:25 | Code/repo structure | Tech stack |
| 4:50 | Final dashboard | Conclusion |

## Quick Recording Checklist

- App launches successfully.
- Demo data is loaded.
- API key is hidden.
- Browser notifications are disabled.
- Screen resolution is 1080p.
- Audio is recorded in a quiet room.
- Cursor movement is slow and intentional.
- No long pauses while switching tabs.
- Final export is MP4.
