import sys
import os
import logging

# 시스템 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# logs 디렉토리 생성
os.makedirs("logs", exist_ok=True)

# 로깅 설정
logging.basicConfig(
    filename="logs/app.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

import streamlit as st

def home():
    st.set_page_config(page_title="Shifts Procurement", layout="wide")
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
    logging.info("Launching Streamlit app.")
    pg.run()
except Exception as e:
    logging.exception("❌ Error running Streamlit app:")
    raise e
