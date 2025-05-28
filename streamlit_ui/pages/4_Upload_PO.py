import sys
import os
import re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import streamlit as st
import datetime
from supabase import create_client

st.set_page_config(layout="wide")

# 환경변수 또는 config에서 가져오기
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase_storage = create_client(SUPABASE_URL, SUPABASE_KEY)

# 여러 파일 업로드 지원
uploaded_files = st.file_uploader(
    "Upload your ERP-exported Excel files",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.success(f"✅ File '{uploaded_file.name}' loaded successfully.")
        # Supabase Storage 업로드 (이메일별 폴더)
        # 예시: user_email = st.session_state.user.email (실제 로그인 세션에서 가져와야 함)
        user_email = getattr(getattr(st.session_state, 'user', None), 'email', 'anonymous')
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
        # 파일명에서 한글, 공백, 특수문자 제거 (영문, 숫자, 언더스코어, 하이픈, 점만 허용)
        safe_file_name = re.sub(r'[^A-Za-z0-9_.-]', '_', file_name)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        storage_path = f"{user_email}/{timestamp}_{safe_file_name}"
        res = supabase_storage.storage.from_("po-uploads").upload(
            storage_path,
            file_bytes,
            {"content-type": uploaded_file.type}
        )
        if getattr(res, "path", None):
            st.success("📦 File uploaded successfully!")
        else:
            st.error(f"Storage upload failed for '{file_name}'.")
