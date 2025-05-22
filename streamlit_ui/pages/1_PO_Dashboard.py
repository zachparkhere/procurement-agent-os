import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import datetime
from po_agent_os.supabase_client_anon import supabase
from streamlit_ui.api.fetch_po import fetch_user_pos
from streamlit_ui.api.fetch_po_items import fetch_po_items
from streamlit_ui.api.fetch_latest_email_summary import fetch_latest_email_summary
from streamlit_ui.utils.session_guard import require_login
import pandas as pd

# 🔐 Login check
if "user" not in st.session_state:
    st.warning("Please log in to continue.")
    st.stop()

# 디버깅: 세션 상태, user 객체 정보만 출력
# st.write("[DEBUG] session_state:", dict(st.session_state))
# st.write("[DEBUG] user:", st.session_state.get("user"))

# 토큰을 session_state에서 직접 꺼내서 사용
access_token = st.session_state.get("access_token")
refresh_token = st.session_state.get("refresh_token")
if not access_token or not refresh_token:
    st.error("Missing tokens. Please log in again.")
    st.stop()

# ✅ Set Supabase auth session
try:
    supabase.auth.set_session(
        access_token,
        refresh_token
    )
except Exception as e:
    st.error("Authentication failed. Please log in again.")
    st.exception(e)
    st.stop()
st.sidebar.markdown(f"**Logged in as:** {st.session_state.user.email}")

# Supabase user ID
user_email = st.session_state.user.email
user_row = supabase.table("users").select("id").eq("email", user_email).single().execute().data
user_id = user_row["id"]

# Debugging output
# st.write("[DEBUG] user:", st.session_state.get("user"))
# st.write("[DEBUG] access_token:", getattr(st.session_state.user, "access_token", None))
# st.write("[DEBUG] refresh_token:", getattr(st.session_state.user, "refresh_token", None))

po_list = fetch_user_pos(user_id=user_id)

if not po_list:
    st.info("No purchase orders found.")
else:
    cols_per_row = 3

    def sort_key(po):
        status = (po.get("status") or "").lower()
        return 0 if status in ["delayed", "cancelled"] else 1

    visible_pos = sorted(po_list, key=sort_key)

    for i in range(0, len(visible_pos), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, po in enumerate(visible_pos[i:i + cols_per_row]):
            with cols[j]:
                po_id = po.get("po_id")
                po_number = po.get("po_number", "Unknown")
                vendor_name = po.get("vendor_name", "Unknown")
                expected_str = po.get("expected_delivery_date")
                eta_str = po.get("eta")
                status_text = str(po.get("status") or "None")
                status_text_lower = status_text.lower()

                detail_key = f"detail-{po_id}"
                edit_key = f"edit-{po_id}"
                save_key = f"save-{po_id}"

                border_color = (
                    "red" if status_text_lower in ["delayed", "cancelled"]
                    else "#ccc"
                )

                card_style = f"""
                    background-color: #fff;
                    border: 2px solid {border_color};
                    border-radius: 16px;
                    padding: 20px;
                    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
                    margin-bottom: 24px;
                """

                st.markdown(f"<div style='{card_style}'>", unsafe_allow_html=True)

                st.markdown(f"<div style='font-size:1.1em; font-weight:bold;'>🆔 {po_number}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='color:gray; margin-bottom:12px;'>Vendor: {vendor_name}</div>", unsafe_allow_html=True)

                st.markdown(f"**📅 Expected Delivery Date**: {expected_str or 'None'}")
                st.markdown(f"**📦 ETA**: {eta_str or 'Not set'}")

                if not st.toggle("✏️ Edit", key=edit_key):
                    color = (
                        "red" if status_text_lower in ["delayed", "cancelled"]
                        else "green" if status_text_lower == "done"
                        else "black"
                    )
                    st.markdown(f"**📌 Status**: <span style='color:{color}'>{status_text}</span>", unsafe_allow_html=True)
                else:
                    status_options = ["None", "In Progress", "Delayed", "Cancelled", "Done"]
                    safe_status = status_text if status_text in status_options else "None"
                    new_status = st.selectbox("📌 Status", status_options,
                                              index=status_options.index(safe_status),
                                              key=f"status-{po_id}")
                    new_eta = st.text_input("📦 ETA", eta_str or "", key=f"eta-{po_id}")
                    new_expected = st.text_input("📅 Expected Delivery Date", expected_str or "", key=f"expdate-{po_id}")
                    if st.button("💾 Save Changes", key=save_key):
                        if not po_id:
                            st.error("po_id가 None입니다. DB 업데이트를 건너뜁니다.")
                        else:
                            supabase.table("purchase_orders").update({
                                "status": new_status,
                                "eta": new_eta,
                                "expected_delivery_date": new_expected
                            }).eq("po_id", po_id).execute()
                            st.rerun()

                summary, summary_date = fetch_latest_email_summary(po_number)
                if summary:
                    st.markdown(f"📄 **Last Email Summary** ({summary_date[:10]}):")
                    st.markdown(f"> {summary[:200]}{'...' if len(summary) > 200 else ''}")
                else:
                    st.markdown("📄 _No email summary available._")

                items = fetch_po_items(po_number)
                categories = list(set(item.get('category', '') for item in items if item.get('category')))
                st.markdown(f"**📂 Item Categories**: {', '.join(categories) if categories else '(TBD)'}")

                btn_cols = st.columns([0.5, 0.5])
                with btn_cols[0]:
                    st.button("📨 Generate Follow-up", key=f"followup-{po_id}")
                with btn_cols[1]:
                    st.toggle("🔍 View Details", key=detail_key)

                if st.session_state.get(detail_key, False):
                    st.markdown("---")
                    st.markdown("### 📑 PO Details")
                    st.markdown(f"**PO Number**: {po_number}")
                    st.markdown(f"**Vendor**: {vendor_name}")
                    st.markdown(f"**Expected Delivery Date**: {expected_str or 'None'}")

                    if items:
                        df = pd.DataFrame(items)
                        df = df[["item_no", "description", "quantity", "unit", "unit_price", "subtotal", "tax", "total", "category"]]
                        df.columns = ["Item No", "Description", "Qty", "Unit", "Unit Price", "Subtotal", "Tax", "Total", "Category"]
                        st.dataframe(df.reset_index(drop=True), use_container_width=True)
                        st.markdown(f"**📦 Total Sum**: {df['Total'].sum():,.0f}")
                    else:
                        st.write("No item data found.")

                st.markdown("</div>", unsafe_allow_html=True)
