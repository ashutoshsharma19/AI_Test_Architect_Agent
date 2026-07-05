import os
import fitz  # PyMuPDF
import docx

def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        text = f"Error parsing PDF: {str(e)}"
    return text

def parse_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    text = ""
    try:
        doc = docx.Document(file_path)
        # Extract paragraph text
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        
        # Extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells]
                text += " | ".join(row_text) + "\n"
    except Exception as e:
        text = f"Error parsing DOCX: {str(e)}"
    return text

def parse_document(file_path: str) -> str:
    """Parse PDF, DOCX, or TXT file based on extension."""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
        
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path)
    elif ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading text file: {str(e)}"
    else:
        return f"Unsupported file format: {ext}"
