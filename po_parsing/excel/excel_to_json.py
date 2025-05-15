from .excel_parsing import extract_text_and_tables_in_order
from .po_excel_to_llm import build_excel_prompt

def parse_excel_file(file_path):
    full_content = extract_text_and_tables_in_order(file_path)
    return build_excel_prompt(full_content)