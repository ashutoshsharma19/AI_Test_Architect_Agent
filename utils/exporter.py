import json
import csv
import io
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from utils.normalizer import normalize_state

def export_to_excel(state: Dict[str, Any]) -> io.BytesIO:
    """Create a styled Excel workbook containing all pipeline outputs."""
    state = normalize_state(state)
    wb = Workbook()
    
    # 1. Sheet: Requirements
    ws_req = wb.active
    ws_req.title = "Requirements"
    req_headers = ["Requirement ID", "Text", "Type"]
    ws_req.append(req_headers)
    for req in state.get("requirements", []):
        ws_req.append([req.get("id", ""), req.get("text", ""), req.get("type", "")])
        
    # 2. Sheet: Scenarios
    ws_sc = wb.create_sheet(title="Scenarios")
    sc_headers = ["Scenario ID", "Requirement ID", "Type", "Title", "Description"]
    ws_sc.append(sc_headers)
    for sc in state.get("scenarios", []):
        ws_sc.append([sc.get("scenario_id", ""), sc.get("req_id", ""), sc.get("type", ""), sc.get("title", ""), sc.get("description", "")])
        
    # 3. Sheet: Test Cases
    ws_tc = wb.create_sheet(title="Test Cases")
    tc_headers = ["Test Case ID", "Scenario ID", "Req ID", "Title", "Priority", "Preconditions", "Test Type", "Steps", "Test Data", "SQL Query"]
    ws_tc.append(tc_headers)
    for tc in state.get("test_cases", []):
        # Format steps as a readable list
        steps_text = ""
        for step in tc.get("steps", []):
            steps_text += f"{step.get('step_number')}. {step.get('action')} -> {step.get('expected_result')}\n"
        steps_text = steps_text.strip()
        
        # Test data as string
        data_text = json.dumps(tc.get("test_data", {}), indent=2)
        
        ws_tc.append([
            tc.get("test_case_id", ""),
            tc.get("scenario_id", ""),
            tc.get("req_id", ""),
            tc.get("title", ""),
            tc.get("priority", ""),
            tc.get("preconditions", ""),
            tc.get("test_type", ""),
            steps_text,
            data_text,
            tc.get("sql_query", "")
        ])

    # 4. Sheet: RTM (Requirement Traceability Matrix)
    ws_rtm = wb.create_sheet(title="RTM")
    rtm_headers = ["Requirement ID", "Requirement Text", "Test Case IDs", "Coverage Status"]
    ws_rtm.append(rtm_headers)
    rtm_map = state.get("rtm", {})
    req_dict = {r["id"]: r["text"] for r in state.get("requirements", [])}
    for req_id, text in req_dict.items():
        tc_ids = rtm_map.get(req_id, [])
        status = "Covered" if tc_ids else "Not Covered"
        ws_rtm.append([req_id, text, ", ".join(tc_ids), status])

    # 5. Sheet: QA Review & Metrics
    ws_rev = wb.create_sheet(title="QA Review & Metrics")
    ws_rev.append(["QA Metrics Summary"])
    ws_rev.append([])
    metrics = state.get("metrics", {})
    for k, v in metrics.items():
        if isinstance(v, dict):
            ws_rev.append([k.capitalize()])
            for sk, sv in v.items():
                ws_rev.append([f"  {sk}", str(sv)])
        else:
            ws_rev.append([k.capitalize(), str(v)])
            
    ws_rev.append([])
    ws_rev.append(["Review Findings"])
    ws_rev.append(["Finding ID", "Severity", "Category", "Description"])
    for finding in state.get("review_findings", []):
        ws_rev.append([finding.get("id", ""), finding.get("severity", ""), finding.get("category", ""), finding.get("description", "")])

    # Styling all sheets
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=11, bold=False)
    thin_border = Border(
        left=Side(style='thin', color='D3D3D3'),
        right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'),
        bottom=Side(style='thin', color='D3D3D3')
    )
    
    for sheet in wb.worksheets:
        # Style headers
        if sheet.title in ["Requirements", "Scenarios", "Test Cases", "RTM"]:
            max_cols = sheet.max_column
            for col in range(1, max_cols + 1):
                cell = sheet.cell(row=1, column=col)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                
            # Style data cells & auto-width
            for row in range(2, sheet.max_row + 1):
                for col in range(1, max_cols + 1):
                    cell = sheet.cell(row=row, column=col)
                    cell.font = data_font
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
            
            # Auto column width adjustment
            for col in sheet.columns:
                max_len = 0
                for cell in col:
                    val = str(cell.value or '')
                    # handle multiline text length check
                    lines = val.split('\n')
                    max_len = max(max_len, max(len(l) for l in lines) if lines else 0)
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)
                
        elif sheet.title == "QA Review & Metrics":
            # Simple custom formatting for metrics sheet
            sheet.column_dimensions['A'].width = 30
            sheet.column_dimensions['B'].width = 50

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def export_to_csv(data_list: List[Dict[str, Any]], fields: List[str]) -> str:
    """Export a list of dicts to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for row in data_list:
        row = row if isinstance(row, dict) else {"text": str(row)}
        # Flatten dictionary values (e.g. lists/dicts) into string representation for CSV readability
        flat_row = {}
        for key in fields:
            val = row.get(key, "")
            if isinstance(val, (list, dict)):
                flat_row[key] = json.dumps(val)
            else:
                flat_row[key] = val
        writer.writerow(flat_row)
    return output.getvalue()

def export_to_jira_format(state: Dict[str, Any]) -> str:
    """Generate Jira-importable JSON payload representing the QA deliverables."""
    state = normalize_state(state)
    jira_issues = []
    
    # Export requirements as Jira Stories
    for req in state.get("requirements", []):
        story = {
            "fields": {
                "project": {"key": "QA"},
                "summary": f"[{req.get('id')}] {req.get('text')[:60]}...",
                "description": f"Requirement ID: {req.get('id')}\n\nFull Requirement Details:\n{req.get('text')}\n\nType: {req.get('type')}",
                "issuetype": {"name": "Story"}
            }
        }
        jira_issues.append(story)
        
    # Export test cases as Jira Tests (often used with Xray or Zephyr plugins)
    for tc in state.get("test_cases", []):
        steps_desc = "Preconditions:\n" + tc.get("preconditions", "") + "\n\nSteps:\n"
        for step in tc.get("steps", []):
            steps_desc += f"- Action: {step.get('action')}\n  Expected Result: {step.get('expected_result')}\n"
            
        test_issue = {
            "fields": {
                "project": {"key": "QA"},
                "summary": f"[{tc.get('test_case_id')}] {tc.get('title')}",
                "description": steps_desc + f"\nPriority: {tc.get('priority')}\nTest Framework Candidate: {tc.get('test_type')}",
                "issuetype": {"name": "Test"},
                "labels": [tc.get("test_type", "manual")]
            }
        }
        jira_issues.append(test_issue)
        
    return json.dumps(jira_issues, indent=2)
