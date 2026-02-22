import sys
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import streamlit as st

from pages.overview import render_overview_page
from pages.operations import render_operations_page

st.set_page_config(
    page_title="VBI iPay Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    page = st.radio(
        "Chọn dashboard",
        options=["Tổng quan hàng ngày", "Vận hành chi tiết"],
        label_visibility="collapsed",
    )

if page == "Tổng quan hàng ngày":
    render_overview_page()
else:
    render_operations_page()
