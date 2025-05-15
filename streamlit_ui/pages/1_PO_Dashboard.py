import streamlit as st
st.set_page_config(page_title="PO Dashboard", layout="wide")

from datetime import datetime
from api.fetch_po import get_po_list
from api.fetch_po_items import fetch_po_items
from api.fetch_latest_email_summary import fetch_latest_email_summary
from utils.auth import cookies

if not cookies.ready():
    st.info("Cookies are not ready yet. Please wait a moment and try again.")
    st.stop()

if cookies.ready():
    from utils.session_guard import require_login   
    require_login()

    st.title("📦 Purchase Orders Dashboard")

    # ✅ 로그인 유저 체크
    if "user" not in st.session_state or st.session_state.user is None:
        st.warning("Please log in to view your purchase orders.")
        st.stop()

    # ✅ 로그인된 유저 기준으로 PO 리스트 가져오기
    user_id = st.session_state.user["id"]
    po_list = get_po_list(user_id=user_id)

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
                    with st.container():
                        po_id = po.get("id")
                        po_number = po.get("po_number", "Unknown")
                        vendor_name = (po.get("vendors") or {}).get("name", "Unknown")
                        expected_str = po.get("expected_delivery_date")
                        eta_str = po.get("eta")
                        ai_status = po.get("ai_status", "None")
                        status_text = str(po.get("status") or "None")
                        status_text_lower = status_text.lower()

                        detail_key = f"detail-{po_id}"
                        edit_key = f"edit-{po_id}"
                        save_key = f"save-{po_id}"

                        border_color = "red" if status_text_lower in ["delayed", "cancelled"] else "#ddd"
                        card_style = f"border: 2px solid {border_color}; border-radius: 10px; padding: 20px; margin-bottom: 10px"

                        st.markdown(f"<div style='{card_style}'>", unsafe_allow_html=True)

                        top_cols = st.columns([0.85, 0.15])
                        with top_cols[0]:
                            st.markdown(f"### 🆔 {po_number}")
                        with top_cols[1]:
                            st.toggle("", key=edit_key)
                            st.caption("✏️ Edit")

                        edit_mode = st.session_state.get(edit_key, False)

                        st.write(f"**Vendor**: {vendor_name}")
                        st.write(f"**Expected Delivery Date**: {expected_str or 'None'}")
                        st.write(f"📦 **ETA**: {eta_str or 'Not set'}")

                        if not edit_mode:
                            color = (
                                "red" if status_text_lower in ["delayed", "cancelled"]
                                else "green" if status_text_lower == "done"
                                else "black"
                            )
                            st.markdown(f"**Status**: <span style='color:{color}'>{status_text}</span>", unsafe_allow_html=True)
                        else:
                            status_options = ["None", "In Progress", "Delayed", "Cancelled", "Done"]
                            safe_status = status_text if status_text in status_options else "None"
                            new_status = st.selectbox("📌 Status", status_options,
                                                      index=status_options.index(safe_status),
                                                      key=f"status-{po_id}")
                            new_eta = st.text_input("📦 ETA", eta_str or "", key=f"eta-{po_id}")
                            new_expected = st.text_input("📅 Expected Delivery Date", expected_str or "", key=f"expdate-{po_id}")
                            if st.button("💾 Save Changes", key=save_key):
                                po["status"] = new_status
                                po["eta"] = new_eta
                                po["expected_delivery_date"] = new_expected
                                st.rerun()

                        st.write(f"**AI Status**: {ai_status}")

                        summary, summary_date = fetch_latest_email_summary(po_number)
                        if summary:
                            st.markdown(f"📄 **Last Email Summary** ({summary_date[:10]}):")
                            st.markdown(f"> {summary[:200]}{'...' if len(summary) > 200 else ''}")
                        else:
                            st.markdown("📄 _No email summary available._")

                        st.write(f"**Item Categories**: {', '.join(po.get('item_categories', [])) if po.get('item_categories') else '(TBD)'}")

                        btn_cols = st.columns([0.5, 0.5])
                        with btn_cols[0]:
                            st.button("�� Generate Follow-up", key=f"followup-{po_id}")
                        with btn_cols[1]:
                            st.toggle("🔍 View Details", key=detail_key)

                        if st.session_state.get(detail_key, False):
                            st.markdown("---")
                            st.markdown("### 📑 PO Details")
                            st.write(f"**PO Number**: {po_number}")
                            st.write(f"**Vendor**: {vendor_name}")
                            st.write(f"**Expected Delivery Date**: {expected_str or 'None'}")

                            items = fetch_po_items(po_number)
                            if items:
                                import pandas as pd
                                df = pd.DataFrame(items)
                                df = df[["item_no", "description", "quantity", "unit", "unit_price", "subtotal", "tax", "total", "category"]]
                                df.columns = ["Item No", "Description", "Qty", "Unit", "Unit Price", "Subtotal", "Tax", "Total", "Category"]
                                st.dataframe(df, use_container_width=True)
                                st.markdown(f"**📦 Total Sum**: {df['Total'].sum():,.0f}")
                            else:
                                st.write("No item data found.")

                        st.markdown("</div>", unsafe_allow_html=True)
