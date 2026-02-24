import sys
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import streamlit as st

from pages.overview import render_overview_page
from pages.isafe import render_isafe_page

st.set_page_config(
    page_title="VBI iPay Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    "<style>[data-testid='stSidebarNav'] { display: none; }</style>",
    unsafe_allow_html=True,
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Báo cáo Bảo hiểm qua VBI qua kênh IPAY")
    pwd = st.text_input("Nhập mật khẩu", type="password")
    if pwd == st.secrets["APP_PASSWORD"]:
        st.session_state.authenticated = True
        st.rerun()
    elif pwd:
        st.error("Mật khẩu không đúng.")
    st.stop()

with st.sidebar:
    page = st.radio(
        "Chọn dashboard",
        options=["Tổng quan hàng ngày", "Vận hành chi tiết"],
        label_visibility="collapsed",
    )

if page == "Tổng quan":
    render_overview_page()
else:
    render_isafe_page()
