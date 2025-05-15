import sys, os, re
from excel import excel_to_json
from pdf import pdf_to_json
from word import doc_to_json
from save_json_to_file import save_json_to_file
from save_po_to_db import save_po_to_supabase

def parse_file_ext(file_path):
    # descriminate file extension
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext in ['.xlsx', '.xls', '.xlsm', '.xlsb', '.xltx', '.xltm', '.csv']:
        return excel_to_json.parse_excel_file(file_path)
    elif file_ext == '.pdf':
        return pdf_to_json.parse_pdf_file(file_path)
    elif file_ext in ['.docx', '.doc']:
        return doc_to_json.parse_word_file(file_path)
    else:
        print(f"❗ Unsupported file format: {file_ext}")

# Converting PO Number to a Secure File Name
def get_safe_po_number(po_number):
    return re.sub(r'[\\/*?:"<>|]', "-", po_number)

def save_json(parsed_data, po_number):
    # convert file name safely
    po_number = get_safe_po_number(po_number)
    json_filename = f"{po_number}.json"

    # Create json_folder from the current file reference directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "json_folder")

    # if there is no folder to save json file, make a new folder
    os.makedirs(output_dir, exist_ok=True)

    # create a path to save a json file
    json_save_path = os.path.join(output_dir, json_filename)

    # json save as json
    save_json_to_file(parsed_data, json_save_path)
    print(f"✅Json saved to {json_save_path}.")


def main():
    if len(sys.argv) != 2:
        print(f"❗Usage: python main.py [file_path]")
        return
    
    file_path = sys.argv[1]

    if not os.path.isfile(file_path):
        print(f"❗File not found: {file_path}")
        return
    
    try:
        parsed_data = parse_file_ext(file_path)
    except ValueError as e:
        print(e)
        return
    
    # if there is no "po_number"
    if not parsed_data or 'po_number' not in parsed_data:
        print(f"❗Parsing failed or 'po_number not found in result.")
        return
    
    po_number = parsed_data.get("po_number")
    
    # save_json
    save_json(parsed_data, po_number)
    
    # save to db
    save_po_to_supabase(parsed_data)

if __name__ == "__main__":
    main()