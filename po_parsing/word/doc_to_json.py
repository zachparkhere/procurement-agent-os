from .doc_parsing import extract_text_and_tables_in_order, convert_content_to_text
from .po_doc_to_llm import build_word_prompt

def parse_word_file(file_path):
    content = extract_text_and_tables_in_order(file_path)
    full_content = convert_content_to_text(content)
    return build_word_prompt(full_content)