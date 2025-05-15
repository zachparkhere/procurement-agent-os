import json

# 구조화된 JSON을 파일로 저장
def save_json_to_file(structured_json, output_path):  
    try:
        with open(output_path, 'w', encoding='utf-8') as json_file:
            json.dump(structured_json, json_file, ensure_ascii=False, indent=4)
            print(f"✅ json file saved!: {output_path}")
    except Exception as e:
        print(f"❌ [Error] saving json: {e}")