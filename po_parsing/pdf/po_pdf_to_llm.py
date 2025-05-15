#pip install openai==0.28

import openai
import os, json
from dotenv import load_dotenv
from openai import OpenAI

# .env 파일에서 환경변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def build_pdf_prompt(text):
    prompt = f"""
You are an procurement specialist.

Given the text extracted from a purchase order document, your task is to analyze and extract the main components of the purchase order, including metadata and item details, and structure the information in a valid JSON format.
please extract and structure it into a clean, consistent JSON format.

Please extract and organize the data using the following instructions:

1. **Extract metadata** such as PO number, date, buyer information (company name, address, phone), supplier/client/vendor information:
   - vendor_company
   - vendor_name (contact person)
   - vendor_address
   - vendor_phone
   - vendor_email (look for fields like 'email', 'e-mail', 'contact email', 'vendor email', etc.)
2. **Extract product line items** into a list. For each item, include:
   - item_name  
   - item_number  
   - unit_price  
   - quantity  
   - size (if present)  
   - color (if present)  
   - amount = unit_price * quantity (calculate if not explicitly given)
   - category: Based on the item name and description, infer the product category such as "clothes", "electronics", "furniture", "stationery", "food", etc. Do **not** leave this blank.
3. **Extract financial summary fields** such as:
   - subtotal (sum of all amount)
   - discount_rate
   - tax_rate
   - shipping_fee
   - toual_amount: output the numeric result
4. **Extract shipping information**:
   - method
   - shipping_company
   - tracking_number
   - arrival_date
5. **Extract payment_type and any additional notes** if present.
6. **Currency Handling**:
   - Place `"currency": "$"` (or other symbol if specified) at the top level.
   - Remove any thousand separators like commas in numbers.
   - If prices contain currency symbols, separate them into numeric values + currency field.
7. **Field Formatting Rules**:
   - Use lower_snake_case for all field names.
   - Use standard ISO date format: YYYY-MM-DD
   - Omit any missing fields — do not invent or guess values.
   - Do not copy Excel formulas — only output meaningful values.
8. **Return only a clean JSON object. Do not include comments, code blocks, or explanations.**

Here is the text extracted from the document:

---
{text}
---

Return only the structured JSON output.

It is a rule to follow the json file format below, but if there is anything that does not fit this json file format, add it to the correct place autonomously.


Format like:

{{
  "po_number": "PO-20250501-001",
  "date": "2025-05-01",
  "currency": "$",
  "shipping_method": "courier",
  "shipping_company": "UPS",
  "tracking_number": "12345678",
  "arrival_date": "2024-04-30",
  "buyer": {{
      "buyer_name": "Jessica",
      "buyer_contact": "123-456-7891",
      "buyer_address": "211 Arrow Bay, Westminster, 21656 Los Angeles"
  }},
  "vendor": {{
      "vendor_company": "Shiftsai",
      "vendor_name": "Zach",
      "vendor_contact": "987-654-321",
      "vendor_address": "108 Walford st, Conventry, 254488, IL",
      "vendor_email": "zach@test.com"
  }},
  "items": [
      {{
          "item_no": "1",
          "item_name": "Blue Flower Dress",
          "quantity": 2,
          "description": "Size: M, Colour: Black",
          "category": "Clothes",
          "unit_price": 130.0,
          "amount": 260.0
      }},
      {{
          "item_no": "",
          "item_name": "",
          "quantity": "",
          "description": "",
          "category": "",
          "unit_price": "",
          "amount": ""
      }}
  ],
  "subtotal": 260.0,
  "tax": 10,
  "shipping_fee": 3.0,
  "other_fee": 0.0,
  "total_amount": 289.0,
  "notes": "The amount of the Purchase Order is the agreed fixed price and shall not be exceeded without advanced written consent."
}}

- Do not include comments (like `//`) or unnecessary JSON formatting such as ```json. Only return the raw data in JSON format.
- Do not use `...` (ellipsis) for item lists; please list all actual items.

"""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a procurement specialist."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.0
    )
    
    structured_json = response.choices[0].message.content.strip()
    # print("LLM response:", json_response)  # 디버깅용 출력
    
    # 주석 제거. 정규식 패턴으로 실제 JSON 부분만 추출
    structured_json = structured_json.strip('```json').strip('```').strip()

    try:
        # LLM이 반환한 텍스트를 JSON으로 변환
        structured_json = json.loads(structured_json) 
        return structured_json
    except json.JSONDecodeError as e:
        print(f"JSON 변환 오류 발생!: {e} , response: {structured_json}")
        return None