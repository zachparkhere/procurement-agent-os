import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import pandas as pd
from po_agent_os.supabase_client_anon import supabase
from openai import OpenAI

uploaded_file = st.file_uploader("Upload your ERP-exported Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("✅ File loaded successfully.")
    st.dataframe(df.head(10), use_container_width=True)

    # --- Step 1: Extract headers ---
    columns = df.columns.tolist()

    # --- Step 2: Ask GPT to map columns ---
    with st.spinner("🔍 Letting AI analyze your columns..."):
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")

        system_prompt = """You are a helpful assistant for data onboarding.
Given a list of Excel column headers from an ERP system, your job is to map which column represents each of the following:

- PO Number
- Vendor Code
- Vendor Name
- Delivery Date
- Item Description
- Quantity
- Unit Price
- Vendor Email

Return a JSON object with keys as the above items and values as the matched column names from the list.
Only use column names from the input. If no suitable match, return null for that key."""

        user_prompt = f"Excel columns: {columns}"

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        import json
        suggestions = json.loads(response["choices"][0]["message"]["content"])

    st.subheader("🧠 Suggested Column Mapping (editable)")
    final_mapping = {}
    for key, suggestion in suggestions.items():
        default_index = columns.index(suggestion) if suggestion in columns else 0
        final_mapping[key] = st.selectbox(f"{key}", options=columns, index=default_index)

    # --- Step 3: Vendor Email Check ---
    missing_emails = df[final_mapping["Vendor Email"]].isna().sum()
    if missing_emails > 0:
        st.warning(f"⚠️ {missing_emails} rows are missing vendor emails. Please fix them before continuing.")

    # --- Step 4: Insert into Supabase ---
    if st.button("💾 Insert into Database"):
        user_id = st.session_state.user.id
        inserted = 0

        for _, row in df.iterrows():
            try:
                po_data = {
                    "po_number": str(row[final_mapping["PO Number"]]),
                    "vendor_code": str(row[final_mapping["Vendor Code"]]),
                    "vendor_name": str(row[final_mapping["Vendor Name"]]),
                    "expected_delivery_date": str(row[final_mapping["Delivery Date"]]),
                    "vendor_email": str(row[final_mapping["Vendor Email"]]),
                    "user_id": user_id
                }
                supabase.table("purchase_orders").insert(po_data).execute()
                inserted += 1
            except Exception as e:
                st.error(f"❌ Row insert failed: {e}")

        st.success(f"✅ {inserted} purchase orders inserted.")
