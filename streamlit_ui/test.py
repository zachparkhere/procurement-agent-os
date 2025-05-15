import streamlit as st
from api.fetch_po import get_po_list

st.set_page_config(page_title="PO Test", layout="wide")
st.title("📦 PO List")

po_list = get_po_list()

if not po_list:
    st.warning("No purchase orders found.")
else:
    for po in po_list:
        vendor_name = (po.get("vendors") or {}).get("name", "Unknown")
        st.write({
            "PO Number": po.get("po_number"),
            "Vendor": vendor_name,
            "Status": po.get("ai_status", "N/A"),
            "Flag": po.get("flag", "N/A"),
            "Created At": po.get("created_at", "N/A"),
            "Submitted At": po.get("submitted_at", "N/A"),
        })
