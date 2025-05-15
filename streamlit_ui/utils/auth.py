import streamlit as st
import base64
import json
from streamlit_cookies_manager import EncryptedCookieManager

# 쿠키 매니저 초기화 (각 페이지에서 한 번만)
cookies = EncryptedCookieManager(
    prefix="myapp_",  # 원하는 prefix
    password="your-very-secret-password"  # 환경변수로 관리 권장
)

def store_user_session(user_dict):
    if not cookies.ready():
        return
    user_json = json.dumps(user_dict)
    encoded = base64.b64encode(user_json.encode()).decode()
    st.session_state.user = user_dict
    cookies["auth"] = encoded
    cookies.save()

def restore_user_session():
    if not cookies.ready():
        return None
    if "auth" in cookies and cookies["auth"]:
        try:
            decoded = base64.b64decode(cookies["auth"]).decode()
            user_dict = json.loads(decoded)
            st.session_state.user = user_dict
            return user_dict
        except Exception as e:
            st.warning(f"⚠️ 세션 복원 실패: {e}")
            return None
    return None

def clear_user_session():
    if not cookies.ready():
        return
    st.session_state.user = None
    cookies["auth"] = ""
    cookies.save()
