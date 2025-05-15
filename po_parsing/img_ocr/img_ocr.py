# pip install opencv-python 
# pip install pytesseract pillow

# install Tesseract OCR
#  공식 Windows 설치 파일 링크 (GitHub)
# "tesseract-ocr-w64-setup-xxx.exe" (예: 5.3.1) 파일을 다운로드 후 설치
# 설치 경로 기억 (예: C:\Program Files\Tesseract-OCR)

import os
import cv2
import pytesseract
from PIL import Image
import numpy as np


receipt_image = r"F:\Jiyeon\Project\ShiftsAI\parsing\test_img\receipt_1.jpg"

# PIL로 이미지 열기
image = Image.open(receipt_image)
image = np.array(image)

# 흑백(grayscale) 변환
image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# 노이즈 제거, 이진화
image = cv2.GaussianBlur(image, (3, 3), 0)
thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

# 이미지 확대 (텍스트 인식 향상)
resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

# Tesseract 설정
custom_config = r'--oem 3 --psm 6'
lang_config = 'eng'
# lang_config = 'eng+kor'  # 필요 시 'kor' 제거 가능

# OCR 실행
text = pytesseract.image_to_string(resized, config=custom_config, lang=lang_config)

print("🔍 추출된 텍스트:\n")
print(text)


