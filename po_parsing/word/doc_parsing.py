from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    from docx.oxml.ns import qn
    for child in parent.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)

def extract_text_and_tables_in_order(file_path):
    document = Document(file_path)
    full_content = []

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                full_content.append({'type': 'paragraph', 'content': text})
        elif isinstance(block, Table):
            table_content = []
            seen_cells = set()  # 같은 셀 중복 제거용
            for row in block.rows:
                row_data = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text not in seen_cells:
                        row_data.append(cell_text)
                        seen_cells.add(cell_text)
                    else:
                        row_data.append("")  # 중복이면 빈칸
                table_content.append(row_data)
            full_content.append({'type': 'table', 'content': table_content})
    
    return full_content


# # 테스트
# file_path = r"F:\지연\Project\ShiftsAI\parsing\test_doc\Purchase-Order-Template-03-TemplateLab.docx"
# content = extract_text_and_tables_in_order(file_path)

# 한 덩어리 텍스트로 만들기

def convert_content_to_text(content):
    """
    파싱된 paragraph, table들을 하나의 긴 텍스트로 합침
    (테이블은 간단하게 텍스트로 변환)
    """
    lines = []
    for item in content:
        if item['type'] == 'paragraph':
            lines.append(item['content'])
        elif item['type'] == 'table':
            for row in item['content']:
                lines.append(" | ".join(row))
    return "\n".join(lines)