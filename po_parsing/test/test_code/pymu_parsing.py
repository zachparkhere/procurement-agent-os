import fitz # pymupdf

pdf_file = "F:\지연\Project\ShiftsAI\parsing\Construction-Purchase-Order-Template-TemplateLab.com_.pdf"

# PDF 파일 열기
with fitz.open(pdf_file) as doc:
        for page_num in range(doc.page_count):
        page = doc.load_page(page_num)  # 페이지 불러오기
        print(f"페이지 {page_num + 1}")

        # 페이지에서 텍스트 추출 (원본 텍스트 형식 유지)
        text = page.get_text("text")  # "text" 옵션으로 텍스트 추출
        print("텍스트 내용:")
        print(text)
        
        # 폼 필드(위젯) 추출
        widgets = page.widgets()  # 페이지의 모든 폼 필드(위젯) 가져오기
        
        if widgets:
            print("폼 필드 내용:")
            for widget in widgets:
                field_name = widget.field_name  # 폼 필드 이름
                field_value = widget.text  # 폼 필드 값
                print(f"{field_name}: {field_value}")
         
        else:
            print("폼 필드가 없습니다.")
        
        # 페이지에서 이미지 추출 (선택 사항)
        images = page.get_images(full=True)
        if images:
            print(f"이 페이지에서 {len(images)}개의 이미지가 포함되어 있습니다.")
            for img_index, img in enumerate(images):
                xref = img[0]
                image = doc.extract_image(xref)
                image_bytes = image["image"]  # 이미지 바이트
                # 이미지를 파일로 저장 (예: "image_1.png")
                with open(f"image_{page_num+1}_{img_index+1}.png", "wb") as img_file:
                    img_file.write(image_bytes)
        else:
            print("이미지가 없습니다.")

        print("=" * 50)  # 구분선