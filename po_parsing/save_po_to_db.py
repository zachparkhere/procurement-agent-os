import os
from po_agent_os.supabase_client import supabase
from supabase import Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = supabase

def save_po_to_supabase(json_data):
    # insert to purchase_orders table
    try:
        po_data = {
            "po_number": json_data.get("po_number"),
            "issue_date": json_data.get("date"),
            "expected_delivery_date": json_data.get("arrival_date") or None,
            "eta": json_data.get("arrival_date") or None,
            "currency": json_data.get("currency", ""),
            "notes": json_data.get("notes"),
            "payment_terms": json_data.get("payment_terms", ""),
            "shipping_company": json_data.get("shipping_company", ""),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "vendor_email": json_data.get("vendor", {}).get("vendor_email", ""),
            "vendor_name": json_data.get("vendor",{}).get("vendor_name", ""),
            "tracking_number": json_data.get("tracking_number", ""),
            "ship_to_name": json_data.get("buyer", {}).get("buyer_name", ""),
            "ship_to_address": json_data.get("buyer", {}).get("buyer_address", "")
        }
        
        # supabase.tabe("purchase_orders").insert(po_data).execute()
        supabase.table("purchase_orders").upsert(po_data, on_conflict="po_number").execute()
        print(f"✅ Saved to on purchase_orders table!")

    except Exception as e:
        print(f"❌[Error] Failed to insert PO on purchase_orders: {e}")
        return
    
    # insert items to po_items table
    for item in json_data.get("items", []):
        try:
            item_data = {
                "item_no": item.get("item_no") or "",
                "description": item.get("item_name") or "",
                "quantity": item.get("quantity") or 0,
                "unit_price": item.get("unit_price") or 0,
                "amount": item.get("amount") or 0,
                "subtotal": json_data.get("subtotal") or 0,
                "tax": json_data.get("tax") or 0,
                "shipping_fee": json_data.get("shipping_fee") or 0,
                "other_fee": json_data.get("other_fee") or 0,
                "total": json_data.get("total_amount") or 0,
                "category": item.get("category") or "",
                "po_number": json_data.get("po_number") or "",
            }

            supabase.table("po_items").upsert(item_data).execute()
            print(f"✅ Saved on po_items table!")
        except Exception as e:
            print(f"❌[Error] Failed to insert PO item: {e}")

    print("✅PO data saved to database.")
