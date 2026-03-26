import sys
import base64
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
from pages.other_products import render_other_products_page
from pages.complaints import render_complaints_page

st.set_page_config(
    page_title="VBI iPay Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Always-on: only hide chrome shared across all pages
st.markdown("""
    <style>
    [data-testid='stSidebarNav'] { display: none; }
    #MainMenu, footer { visibility: hidden; }

    /* ── Sidebar shell ── */
    [data-testid="stSidebar"] {
        background-color: #005992 !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 0 !important;
    }

    /* ── All nav buttons ── */
    [data-testid="stSidebar"] button {
        background: transparent !important;
        border: none !important;
        color: rgba(255,255,255,0.8) !important;
        text-align: left !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        padding: 12px 20px !important;
        border-radius: 0 !important;
        letter-spacing: 0.02em !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] button:hover {
        background: rgba(255,255,255,0.1) !important;
        color: #fff !important;
        border-radius: 6px !important;
    }

    /* ── Sub-item indentation ── */
    [data-testid="stSidebar"] [data-testid="stButton"]:nth-child(n+3) button {
        padding-left: 40px !important;
        font-size: 13px !important;
        color: rgba(255,255,255,0.65) !important;
    }
    [data-testid="stSidebar"] [data-testid="stButton"]:nth-child(n+3) button:hover {
        color: #fff !important;
    }
    </style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "Tổng quan"
if "vhct_open" not in st.session_state:
    st.session_state.vhct_open = True

if not st.session_state.authenticated:
    # Base64-encode the lock SVG so it embeds cleanly in CSS without encoding issues
    _lock_svg = (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 17C10.89 17 10 16.1 10 15C10 13.89 10.89 13 12 13'
        'C13.1 13 14 13.9 14 15C14 16.1 13.1 17 12 17M18 20V10H6V20H18'
        'M18 8C19.1 8 20 8.89 20 10V20C20 21.1 19.1 22 18 22H6'
        'C4.89 22 4 21.1 4 20V10C4 8.9 4.89 8 6 8H7V6'
        'C7 3.24 9.24 1 12 1C14.76 1 17 3.24 17 6V8H18'
        'M12 3C10.34 3 9 4.34 9 6V8H15V6C15 4.34 13.66 3 12 3Z" '
        'fill="#000000"/></svg>'
    )
    _lock_icon = "data:image/svg+xml;base64," + base64.b64encode(_lock_svg.encode()).decode()

    st.markdown(f"""
        <style>
        /* ── Hide sidebar and its toggle on login page ── */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}

        /* ── Page background ── */
        .stApp {{
            background: linear-gradient(180deg, #83CCF1 0%, #F2F4F8 70.9%);
        }}
        .main .block-container {{
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
        }}

        /* ── Login card ── */
        [data-testid="stForm"] {{
            position: relative !important;
            z-index: 10 !important;
            width: 611px !important;
            background: linear-gradient(180deg, #C7F0FE 0%, #FEFEFE 62.78%) !important;
            box-shadow: 0 4px 10px 1px rgba(0, 0, 0, 0.15) !important;
            border-radius: 50px !important;
            padding: 73px 88px 95px !important;
            border: none !important;
            margin: 60px auto 0 !important;
        }}
        /* Remove Streamlit's default gap between form children */
        [data-testid="stForm"] [data-testid="stVerticalBlock"] {{
            gap: 0 !important;
        }}

        /* ── Password input ── */
        [data-baseweb="input"] {{
            position: relative !important;
            background: #ffffff !important;
            border: 1px solid #83CCF1 !important;
            border-radius: 15px !important;
            height: 52px !important;
        }}
        /* Lock icon injected as a CSS pseudo-element */
        [data-baseweb="input"]::before {{
            content: "" !important;
            position: absolute !important;
            left: 14px !important;
            top: 50% !important;
            transform: translateY(-50%) !important;
            width: 22px !important;
            height: 22px !important;
            background-image: url("{_lock_icon}") !important;
            background-size: contain !important;
            background-repeat: no-repeat !important;
            pointer-events: none !important;
            z-index: 1 !important;
        }}
        [data-baseweb="input"] input {{
            padding-left: 44px !important;
            background: transparent !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            color: #000 !important;
        }}

        /* ── Login button ── */
        [data-testid="stFormSubmitButton"] {{
            margin-top: 71px !important;
        }}
        [data-testid="stFormSubmitButton"] > button {{
            width: auto !important;
            padding: 0 32px !important;
            height: 48px !important;
            background: linear-gradient(90deg, #98EEFF 0%, #C6F6FF 100%) !important;
            color: #000000 !important;
            border: none !important;
            border-radius: 15px !important;
            font-size: 20px !important;
            font-weight: 600 !important;
            transition: opacity 0.15s ease !important;
        }}
        [data-testid="stFormSubmitButton"] > button:hover {{ opacity: 0.82 !important; }}
        </style>

        <!-- Background polygon layer (matches login.html) -->
        <div style="position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;">
            <div style="position:absolute;width:1441px;height:1330px;left:-405px;top:-376px;
                background:linear-gradient(90deg,#98EEFF 0%,#F2F4F8 100%);
                border-radius:50px;transform:rotate(90deg);"></div>
            <div style="position:absolute;width:894px;height:821px;left:-298px;top:41px;
                background:linear-gradient(90deg,#5FBFEF 0%,#F2F4F8 100%);
                border-radius:50px;transform:rotate(90deg);"></div>
            <div style="position:absolute;width:987.75px;height:904.32px;left:1231px;top:345px;
                background:linear-gradient(90deg,#98EEFF 0%,#F2F4F8 100%);
                border-radius:50px;transform:matrix(-0.03,1,1,0.03,0,0);"></div>
            <div style="position:absolute;width:612.8px;height:558.23px;left:1507.18px;top:640.05px;
                background:linear-gradient(90deg,#5FBFEF 0%,#F2F4F8 100%);
                border-radius:50px;transform:matrix(-0.03,1,1,0.03,0,0);"></div>
        </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        # Icon + title + subtitle rendered inside the card
        st.markdown("""
            <div style="text-align:center;">
                <div style="display:inline-flex;align-items:center;justify-content:center;
                    background:#ffffff;border-radius:25px;width:104px;height:104px;
                    margin-bottom:36px;">
                    <svg width="73" height="73" viewBox="0 0 24 24" fill="none"
                         xmlns="http://www.w3.org/2000/svg">
                        <path d="M11 7L9.6 8.4L12.2 11H2v2h10.2l-2.6 2.6L11 17l5-5-5-5z
                                 M20 19h-8v2h8c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-8v2h8v14z"
                              fill="#000000"/>
                    </svg>
                </div>
                <p style="font-size:28px;font-weight:600;color:#000;margin:0 0 43px;line-height:1.2;">
                    Báo cáo Bảo hiểm VBI kênh IPAY
                </p>
                <p style="font-size:15px;font-weight:600;color:#999;margin:0 0 20px;">
                    Nhập mật khẩu để có thể đăng nhập vào hệ thống
                </p>
            </div>
        """, unsafe_allow_html=True)

        pwd = st.text_input("", placeholder="Nhập mật khẩu", type="password",
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
    # ── Icon-only header ──────────────────────────────────────────────────────
    st.markdown("""
        <div style="padding:24px 20px 16px;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:8px;">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                 xmlns="http://www.w3.org/2000/svg">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                    stroke="white" stroke-width="2" stroke-linecap="round"
                    stroke-linejoin="round"/>
              <polyline points="9 22 9 12 15 12 15 22"
                        stroke="white" stroke-width="2" stroke-linecap="round"
                        stroke-linejoin="round"/>
            </svg>
        </div>
    """, unsafe_allow_html=True)

    # ── Top-level nav item ────────────────────────────────────────────────────
    if st.button("Tổng quan hàng ngày", key="nav_overview",
                 use_container_width=True):
        st.session_state.page = "Tổng quan"
        st.rerun()

    # ── Collapsible section header ────────────────────────────────────────────
    arrow = "▾" if st.session_state.vhct_open else "▸"
    if st.button(f"Báo cáo chi tiết {arrow}", key="nav_vhct",
                 use_container_width=True):
        st.session_state.vhct_open = not st.session_state.vhct_open
        st.rerun()

    # ── Sub-items (shown when section is expanded) ────────────────────────────
    if st.session_state.vhct_open:
        if st.button("Cyber Risk", key="nav_cyber", use_container_width=True):
            st.session_state.page = "Cyber Risk"
            st.rerun()
        if st.button("I-Safe", key="nav_isafe", use_container_width=True):
            st.session_state.page = "I-Safe"
            st.rerun()
        if st.button("TapCare", key="nav_tapcare", use_container_width=True):
            st.session_state.page = "TapCare"
            st.rerun()
        if st.button("Nhà và bạn", key="nav_homesaving", use_container_width=True):
            st.session_state.page = "Nhà và bạn"
            st.rerun()
        if st.button("Sản phẩm khác", key="nav_other", use_container_width=True):
            st.session_state.page = "Sản phẩm khác"
            st.rerun()

    if st.button("Báo cáo CSKH", key="nav_complaints", use_container_width=True):
        st.session_state.page = "Khiếu nại"
        st.rerun()

page = st.session_state.page

if page == "Tổng quan":
    render_overview_page()
elif page == "Cyber Risk":
    render_cyber_risk_page()
elif page == "I-Safe":
    render_isafe_page()
elif page == "TapCare":
    render_tapcare_page()
elif page == "Nhà và bạn":
    render_homesaving_page()
elif page == "Sản phẩm khác":
    render_other_products_page()
elif page == "Khiếu nại":
    render_complaints_page()
else:
    render_homesaving_page()
