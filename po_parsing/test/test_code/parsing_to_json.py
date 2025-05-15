import re, os, json
import fitz # pdf file parsing: pymupdf
import uuid
from datetime import datetime

def extract_text_by_visual_order(filepath):
    doc = fitz.open(filepath)
    full_text = ""

    for page in doc:
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))

        for block in blocks:
            text = block[4].strip()
            if text:
                full_text += text + "\n"

    return full_text.strip()

def detect_document_type(text):
    if "purchase order" in text.lower():
        return "purchase_order"
    else:
        return "unknown"

def parse_purchase_order(text):
    data = {}
    data["document_type"] = "purchase_order"

    # 기본정보
    po_number = re.search(r'PO\s*#:\s*(\d+)', text)
    date = re.search(r'Date\s*:\s*([\d/]+)', text)
    company = re.search(r'(CONSTRUCTION MASTERS|[A-Z\s]{5,})', text)

    data["po_number"] = po_number.group(1) if po_number else None
    data["date"] = date.group(1) if date else None
    data["company_name"] = company.group(1).strip() if company else None

    # 서비스 항목
    services = []
    service_block = re.findall(r'(\d+)\s+(\d+)\s+([\d.,]+)\$?\s+([\d.,]+)\$', text)
    for match in service_block:
        services.append({
            "no": int(match[0]),
            "time_range_days": int(match[1]),
            "price_per_hour": float(match[2].replace(",", "")),
            "total_price": float(match[3].replace(",", ""))
        })
    data["services"] = services

    # 자재 항목
    materials = []
    material_block = re.findall(r'(\d+)\s+(.+?)\s+(\d+)\s+([\d.,]+)\$?\s+([\d.,]+)\$', text)
    for match in material_block:
        materials.append({
            "no": int(match[0]),
            "item_description": match[1].strip(),
            "quantity": int(match[2]),
            "unit_price": float(match[3].replace(",", "")),
            "total_price": float(match[4].replace(",", ""))
        })
    data["materials"] = materials

    # 합계
    job_cost = re.search(r'Total Job Cost\s*([\d.,]+)\$', text)
    tax_rate = re.search(r'TAX\s*([\d%]+)', text)
    total_due = re.search(r'TOTAL\s*([\d.,]+)\$', text)

    data["job_cost_total"] = float(job_cost.group(1).replace(",", "")) if job_cost else None
    data["tax_rate"] = tax_rate.group(1) if tax_rate else None
    data["total_amount_due"] = float(total_due.group(1).replace(",", "")) if total_due else None

    return data

def parse_single_pdf(pdf_path):
    text = extract_text_by_visual_order(pdf_path)
    doc_type = detect_document_type(text)

    if doc_type == "purchase_order":
        parsed = parse_purchase_order(text)
    else:
        parsed = {"document_type": "unknown", "content": text}

    return parsed

def batch_parse_pdfs(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_dir, pdf_file)
        parsed_data = parse_single_pdf(pdf_path)

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_id = str(uuid.uuid4())[:8]
        filename = f"{parsed_data['document_type']}_{now}_{random_id}.json"
        output_path = os.path.join(output_dir, filename)

        # with open(output_path, "w", encoding="utf-8") as f:
        #     json.dump(parsed_data, f, indent=2, ensure_ascii=False)

        print(f"✅ 변환 완료: {pdf_file} → {filename}")

# 여러 PDF가 들어있는 폴더
input_dir = r"F:\지연\Project\ShiftsAI\parsing\test_pdf" 

# JSON 저장할 폴더
output_dir = r"F:\지연\Project\ShiftsAI\parsing\json_folder"  

batch_parse_pdfs(input_dir, output_dir)
