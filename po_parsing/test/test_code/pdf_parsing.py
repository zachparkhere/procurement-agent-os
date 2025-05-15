# for LLM

import fitz  # PyMuPDF
import json, re

def extract_text_by_visual_order(filepath):
    doc = fitz.open(filepath)
    full_text = ""

    for page in doc:
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))  # y0, x0 기준 정렬

        for block in blocks:
            text = block[4].strip()
            if text:
                full_text += text + "\n"

    return full_text.strip()


def parse_purchase_order(text):
    # 정규식 기반 간단 파싱
    parsed = {}

    # 기본정보
    parsed["title"] = "PURCHASE ORDER"
    parsed["company_name"] = "CONSTRUCTION MASTERS"

    po_number = re.search(r'PO #:\s*(\d+)', text)
    date = re.search(r'Date:\s*([\d/]+)', text)
    address = re.search(r'([0-9]+ .+PH: .+)', text)
    website = re.search(r'(www\..+)', text)

    parsed["basic_info"] = {
        "po_number": po_number.group(1) if po_number else None,
        "date": date.group(1) if date else None,
        "address": address.group(1) if address else None,
        "website": website.group(1) if website else None
    }

    # 서비스, 자재 항목 수작업 추출
    parsed["services"] = []
    parsed["materials"] = []

    service_block = re.findall(r'(\d+)\s+(\d+)\s+([\d.,]+)\$?\s+([\d.,]+)\$', text)
    for match in service_block:
        parsed["services"].append({
            "no": int(match[0]),
            "time_range_days": int(match[1]),
            "price_per_hour": float(match[2].replace(",", "")),
            "total_price": float(match[3].replace(",", ""))
        })

    material_block = re.findall(r'(\d+)\s+(.+?)\s+(\d+)\s+([\d.,]+)\$?\s+([\d.,]+)\$', text)
    for match in material_block:
        parsed["materials"].append({
            "no": int(match[0]),
            "item_description": match[1].strip(),
            "quantity": int(match[2]),
            "unit_price": float(match[3].replace(",", "")),
            "total_price": float(match[4].replace(",", ""))
        })

    # 합계 및 기타
    job_cost = re.search(r'Total Job Cost\s*([\d.,]+)\$', text)
    tax_rate = re.search(r'TAX\s*(\d+%)', text)
    total_due = re.search(r'TOTAL\s*([\d.,]+)\$', text)
    comments = re.search(r'Comments\s*(.+?)Accepted By:', text, re.DOTALL)

    parsed["services_total"] = sum(s["total_price"] for s in parsed["services"])
    parsed["materials_total"] = sum(m["total_price"] for m in parsed["materials"])
    parsed["job_cost_total"] = float(job_cost.group(1).replace(",", "")) if job_cost else None
    parsed["tax_rate"] = tax_rate.group(1) if tax_rate else None
    parsed["total_amount_due"] = float(total_due.group(1).replace(",", "")) if total_due else None
    parsed["comments"] = comments.group(1).strip().replace("\n", " ") if comments else None

    parsed["approved_by"] = None
    parsed["accepted_by"] = None
    parsed["approval_date"] = None

    return parsed

def pdf_to_json(pdf_path, json_path):
    text = extract_text_by_visual_order(pdf_path)
    parsed_data = parse_purchase_order(text)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON 저장 완료: {json_path}")

# 사용 예시
pdf_path = r"F:\지연\Project\ShiftsAI\parsing\Construction-Purchase-Order-Template-TemplateLab.com_.pdf"
json_output_path = r"F:\지연\Project\ShiftsAI\parsing\json_folder\parsed_purchase_order.json"

pdf_to_json(pdf_path, json_output_path)