# import os
import fitz  # PyMuPDF

# 하나의 pdf 파싱
def extract_text_from_single_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""

    for page in doc:
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))
    for block in blocks:
        text = block[4].strip() # 텍스트 추출
        if text:
            full_text += text + "\n"

    print("Extracted Text: ", full_text)

    return full_text.strip()

"""
# 폴더 내에 있는 모든 pdf 파싱
def extract_text_from_pdf_directory(directory_path):
    pdf_files = [f for f in os.listdir(directory_path) if f.lower().endswith(".pdf")]

    for pdf_file in pdf_files:
        pdf_path = os.path.join(directory_path, pdf_file)
        doc = fitz.open(pdf_path) # pdf 파일 열기기
        full_text = ""

        for page in doc:
            
            blocks = page.get_text("blocks")  # (x0, y0, x1, y1, "text", block_no, block_type)
            blocks = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))  # y0, x0 기준 정렬

            for block in blocks:
                text = block[4].strip() # 텍스트 추출출
                if text:
                    full_text += text + "\n"
        print(f"---{pdf_file}---")
        print(full_text.strip())
        print("\n" + "="*50 + "\n")

    return full_text.strip()
"""