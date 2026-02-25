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

st.set_page_config(
    page_title="VBI iPay Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Always-on: only hide chrome shared across all pages
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}"
    "#MainMenu,header,footer{visibility:hidden;}</style>",
    unsafe_allow_html=True,
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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

        /* ── Login button – 249 px, centered ── */
        [data-testid="stFormSubmitButton"] {{
            margin-top: 71px !important;
        }}
        [data-testid="stFormSubmitButton"] > button {{
            display: block !important;
            margin: 0 auto !important;
            width: 249px !important;
            height: 55px !important;
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
