import sys
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import streamlit as st

from pages.overview import render_overview_page
from pages.cyber_risk import render_cyber_risk_page
from pages.isafe import render_isafe_page
from pages.tapcare import render_tapcare_page
from pages.homesaving import render_homesaving_page

st.set_page_config(
    page_title="VBI iPay Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    [data-testid='stSidebarNav'] { display: none; }
    #MainMenu, header, footer { visibility: hidden; }

    .stApp {
        background: linear-gradient(150deg, #b8d9f0 0%, #d4edf8 40%, #e8f4fb 70%, #9fcce8 100%);
        min-height: 100vh;
    }

    .main .block-container {
        max-width: 480px !important;
        padding: 0 !important;
        margin: 0 auto !important;
        display: flex;
        align-items: center;
        min-height: 100vh;
    }

    [data-testid="stForm"] {
        background: white;
        border-radius: 24px;
        padding: 48px 40px 40px;
        box-shadow: 0 8px 40px rgba(100,160,210,0.18);
        margin-top: 80px;
    }

    [data-testid="stTextInput"] > div > div > input {
        border: 1.5px solid #e0e8f0 !important;
        border-radius: 10px !important;
        font-size: 15px !important;
    }

    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(90deg, #5bbfd6, #3fa8c0) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        width: 100% !important;
        padding: 14px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        transition: opacity 0.2s !important;
    }
    [data-testid="stFormSubmitButton"] > button:hover { opacity: 0.88 !important; }
    </style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
        <div style="text-align:center; margin-bottom:8px;">
            <div style="display:inline-flex; align-items:center; justify-content:center;
                        background:#f0f7fc; border-radius:18px; width:72px; height:72px;
                        margin-bottom:20px;">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none"
                     xmlns="http://www.w3.org/2000/svg">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" stroke="#222"
                        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <polyline points="10 17 15 12 10 7" stroke="#222" stroke-width="2"
                            stroke-linecap="round" stroke-linejoin="round"/>
                  <line x1="15" y1="12" x2="3" y2="12" stroke="#222" stroke-width="2"
                        stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>
            <h2 style="font-size:22px; font-weight:700; color:#1a1a2e; margin:0 0 10px;">
                Báo cáo Bảo hiểm VBI kênh IPAY
            </h2>
            <p style="color:#8a9bb5; font-size:14px; margin:0 0 24px;">
                Nhập mật khẩu để có thể đăng nhập vào hệ thống
            </p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        pwd = st.text_input("", placeholder="🔒  Nhập mật khẩu", type="password",
                            label_visibility="collapsed")
        submitted = st.form_submit_button("Đăng nhập")
        if submitted:
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Mật khẩu không đúng.")
    st.stop()

with st.sidebar:
    page = st.radio(
        "Chọn dashboard",
        options=["Tổng quan", "Cyber Risk", "I-Safe", "TapCare", "Nhà và bạn"],
        label_visibility="collapsed",
    )

if page == "Tổng quan":
    render_overview_page()
elif page == "Cyber Risk":
    render_cyber_risk_page()
elif page == "I-Safe":
    render_isafe_page()
elif page == "TapCare":
    render_tapcare_page()
else:
    render_homesaving_page()
