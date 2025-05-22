import streamlit as st

def render():
    st.set_page_config(page_title="Shifts Procurement", layout="wide")
    st.title("📦 Shifts Procurement Agent")
    st.markdown("Select a page from the left sidebar.")

if __name__ == "__main__":
    try:
        render()
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
