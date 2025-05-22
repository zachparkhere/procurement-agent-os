import os
from po_agent_os.supabase_client import supabase
from dotenv import load_dotenv

# Load env vars
load_dotenv()
supabase = supabase

def fetch_request_data(request_form_id: int):
    # 1. Fetch the request_form
    req_form_resp = supabase.table("request_form").select("*").eq("id", request_form_id).single().execute()
    request_form = req_form_resp.data

    if not request_form:
        print("❌ request_form not found.")
        return None

    # 2. Fetch the vendor info
    vendor_resp = supabase.table("vendors").select("*").eq("id", request_form["vendor_id"]).single().execute()
    vendor = vendor_resp.data

    # 3. Fetch the requester info
    requester_resp = supabase.table("users").select("*").eq("id", request_form["requester_id"]).single().execute()
    requester = requester_resp.data

    # 4. Fetch the items
    items_resp = supabase.table("request_items").select("*").eq("request_form_id", request_form_id).execute()
    items = items_resp.data

    return {
        "form": request_form,
        "vendor": vendor,
        "requester": requester,
        "items": items
    }

if __name__ == "__main__":
    data = fetch_request_data(1)  # test with request_form_id = 1
    if data:
        print("✅ Data fetched successfully")
        print(data) 