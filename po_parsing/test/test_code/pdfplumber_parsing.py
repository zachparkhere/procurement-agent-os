import pdfplumber

# with pdfplumber.open("F:\지연\Project\ShiftsAI\parsing\Purchase-Order-Template-01-TemplateLab.com_.pdf") as pdf:
#     for page in pdf.pages:
#         text = page.extract_text()
#         print(text)

pdf_file = "F:\지연\Project\ShiftsAI\parsing\Construction-Purchase-Order-Template-TemplateLab.com_.pdf"

with pdfplumber.open(pdf_file) as pdf:
    for page_num in range(len(pdf.pages)):
        page = pdf.pages[page_num]

        # 텍스트 추출
        text = page.extract_text()
        print(f"--- 페이지 {page_num + 1} ---")
        print(text)

        # 표 추출
        table = page.extract_table()  
        if table:
            for row in table:
                # 각 행을 텍스트로 출력
                print("\t".join([str(cell) if cell is not None else "" for cell in row]))
        
        print("=" * 50)


