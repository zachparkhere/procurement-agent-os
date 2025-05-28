import sys
import os

# 시스템 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 공통 로깅 설정 불러오기
from streamlit_ui.utils.logging_config import logging
logger = logging.getLogger(__name__)

import streamlit as st
st.set_page_config(page_title="Shifts Procurement", layout="wide")

def home():
    st.title("📦 Shifts Procurement Agent")
    st.markdown("Select a page from the left sidebar.")

pg = st.navigation([
    st.Page(home, title="Home", icon="🏠"),
    st.Page("pages/0_Login.py", title="Login", icon="🔐"),
    st.Page("pages/1_PO_Dashboard.py", title="PO Dashboard", icon="📦"),
    st.Page("pages/2_Email_Log.py", title="Email Log", icon="✉️"),
    st.Page("pages/3_settings.py", title="Settings", icon="⚙️"),
    st.Page("pages/4_Upload_PO.py", title="Upload PO", icon="📤"),
])

try:
    logger.info("🚀 Launching Streamlit app.")
    pg.run()
except Exception as e:
    logger.exception("❌ Error running Streamlit app:")
    raise e
