import streamlit as st
import base64
import json

# 세션에 사용자 정보 저장

def store_user_session(user_dict):
    user_json = json.dumps(user_dict)
    encoded = base64.b64encode(user_json.encode()).decode()
    st.session_state.user = user_dict
    st.session_state.auth = encoded


def restore_user_session():
    if "auth" in st.session_state and st.session_state.auth:
        try:
            decoded = base64.b64decode(st.session_state.auth).decode()
            user_dict = json.loads(decoded)
            st.session_state.user = user_dict
            return user_dict
        except Exception as e:
            st.warning(f"⚠️ 세션 복원 실패: {e}")
            return None
    return None


def clear_user_session():
    st.session_state.user = None
    st.session_state.auth = ""
