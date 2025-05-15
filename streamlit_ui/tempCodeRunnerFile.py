import streamlit as st
from pages import PO_List, Email_Log, Settings

st.set_page_config(page_title="Shifts Procurement", layout="wide")

# Streamlit이 자동으로 pages 디렉토리의 파일을 탭으로 인식
st.title("📦 Shifts Procurement Agent")
st.markdown("Select a page from the left sidebar.")
