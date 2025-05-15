# from .pdf_parsing import extract_text_from_pdf_directory   # 여러 pdf parsing할 때
from .pdf_parsing import extract_text_from_single_pdf
from .po_pdf_to_llm import build_pdf_prompt

def parse_pdf_file(file_path):
    full_content = extract_text_from_single_pdf(file_path)
    return build_pdf_prompt(full_content)
