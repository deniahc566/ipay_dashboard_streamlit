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

st.markdown(
    "<style>[data-testid='stSidebarNav'] { display: none; }</style>",
    unsafe_allow_html=True,
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def _render_login_page() -> None:
    # mdi:password-outline as a URL-encoded inline SVG (used in CSS ::before)
    _LOCK_ICON = (
        "data:image/svg+xml,"
        "%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'"
        " viewBox='0 0 24 24'%3E"
        "%3Cpath d='M12 17C10.89 17 10 16.1 10 15C10 13.89 10.89 13 12 13"
        "C13.1 13 14 13.9 14 15C14 16.1 13.1 17 12 17"
        "M18 20V10H6V20H18"
        "M18 8C19.1 8 20 8.89 20 10V20C20 21.1 19.1 22 18 22"
        "H6C4.89 22 4 21.1 4 20V10C4 8.9 4.89 8 6 8H7V6"
        "C7 3.24 9.24 1 12 1C14.76 1 17 3.24 17 6V8H18"
        "M12 3C10.34 3 9 4.34 9 6V8H15V6C15 4.34 13.66 3 12 3Z'"
        " fill='%23000'%2F%3E%3C%2Fsvg%3E"
    )

    st.markdown(
        f"""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@600&display=swap" rel="stylesheet">
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, [data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stStatusWidget"],
[data-testid="stDecoration"] {{ display: none !important; }}

/* ── Full-page background ── */
body, [data-testid="stAppViewContainer"] {{
    background: linear-gradient(180deg, #83CCF1 0%, #F2F4F8 70.9%) !important;
}}
[data-testid="stAppViewContainer"] > .main {{
    background: transparent !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 100vh !important;
}}

/* ── Login card ── */
.block-container {{
    background: linear-gradient(180deg, #C7F0FE 0%, #FEFEFE 62.78%) !important;
    box-shadow: 0 4px 10px 1px rgba(0, 0, 0, 0.15) !important;
    border-radius: 50px !important;
    max-width: 611px !important;
    width: 611px !important;
    padding: 73px 88px 95px !important;
    position: relative;
    z-index: 10;
}}

/* ── Collapse default element gaps inside card ── */
.block-container .element-container,
.block-container .stMarkdown {{ margin: 0 !important; padding: 0 !important; }}

/* ── Logo box ── */
.login-logo {{
    width: 104px; height: 104px;
    background: #FFFFFF;
    border-radius: 25px;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 36px;
}}

/* ── Title ── */
.login-title {{
    font-family: 'Inter', sans-serif;
    font-weight: 600; font-size: 28px; line-height: 34px;
    color: #000; text-align: center;
    margin: 0 0 43px;
}}

/* ── Subtitle ── */
.login-subtitle {{
    font-family: 'Inter', sans-serif;
    font-weight: 600; font-size: 15px; line-height: 18px;
    color: #999999; text-align: center;
    margin: 0 0 5px;
}}

/* ── Password input: label & spacing ── */
div[data-testid="stTextInput"] label {{ display: none !important; }}
div[data-testid="stTextInput"] {{ margin-bottom: 71px !important; }}

/* ── Input container (BaseWeb) – border, size, icon anchor ── */
div[data-baseweb="input"] {{
    position: relative !important;
    border: 1px solid #83CCF1 !important;
    border-radius: 15px !important;
    background: #FFFFFF !important;
    height: 52px !important;
    padding: 0 !important;
    box-shadow: none !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}}

/* ── Lock icon via ::before ── */
/* Matches login.html: left 20px, icon 23.92px, gap 11px → text at 55px */
div[data-baseweb="input"]::before {{
    content: '';
    position: absolute;
    left: 20px;
    top: 50%;
    transform: translateY(-50%);
    width: 23.92px;
    height: 23.92px;
    background-image: url("{_LOCK_ICON}");
    background-size: contain;
    background-repeat: no-repeat;
    z-index: 2;
    pointer-events: none;
}}

/* ── Input text field ── */
div[data-baseweb="input"] > input {{
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    line-height: 18px !important;
    color: #000000 !important;
    padding-left: 55px !important;
    height: 52px !important;
    border: none !important;
    background: transparent !important;
    caret-color: #5FBFEF !important;
}}

div[data-baseweb="input"] > input::placeholder {{
    color: #000000 !important;
    font-weight: 600 !important;
}}

/* ── Focus ring ── */
div[data-baseweb="input"]:focus-within {{
    border-color: #5FBFEF !important;
    box-shadow: 0 0 0 1px #5FBFEF !important;
}}

/* ── Hide Streamlit's password show/hide eye toggle ── */
div[data-baseweb="input-adjunct"] {{ display: none !important; }}

/* ── Login button ── */
div[data-testid="stButton"] {{ display: flex; justify-content: center; }}
div[data-testid="stButton"] > button {{
    background: linear-gradient(90deg, #98EEFF 0%, #C6F6FF 100%) !important;
    border: none !important;
    border-radius: 15px !important;
    width: 249px !important; height: 55px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important; font-size: 20px !important;
    line-height: 24px !important; color: #000000 !important;
    padding: 0 !important; box-shadow: none !important;
    transition: opacity 0.15s ease;
}}
div[data-testid="stButton"] > button:hover {{
    opacity: 0.82 !important;
    background: linear-gradient(90deg, #98EEFF 0%, #C6F6FF 100%) !important;
    border: none !important;
}}
div[data-testid="stButton"] > button:active {{ opacity: 0.65 !important; }}
</style>

<!-- Fixed background polygons (behind card) -->
<div style="position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;
            background:linear-gradient(180deg,#83CCF1 0%,#F2F4F8 70.9%)">
  <div style="position:absolute;width:1441px;height:1330px;left:-405px;top:-376px;
              background:linear-gradient(90deg,#98EEFF 0%,#F2F4F8 100%);
              border-radius:50px;transform:rotate(90deg)"></div>
  <div style="position:absolute;width:894px;height:821px;left:-298px;top:41px;
              background:linear-gradient(90deg,#5FBFEF 0%,#F2F4F8 100%);
              border-radius:50px;transform:rotate(90deg)"></div>
  <div style="position:absolute;width:987.75px;height:904.32px;left:1231px;top:345px;
              background:linear-gradient(90deg,#98EEFF 0%,#F2F4F8 100%);
              border-radius:50px;transform:matrix(-0.03,1,1,0.03,0,0)"></div>
  <div style="position:absolute;width:612.8px;height:558.23px;left:1507.18px;top:640.05px;
              background:linear-gradient(90deg,#5FBFEF 0%,#F2F4F8 100%);
              border-radius:50px;transform:matrix(-0.03,1,1,0.03,0,0)"></div>
</div>

<!-- Logo icon (material-symbols:login-rounded) -->
<div class="login-logo">
  <svg width="73" height="73" viewBox="0 0 24 24" fill="none"
       xmlns="http://www.w3.org/2000/svg">
    <path d="M11 7L9.6 8.4L12.2 11H2v2h10.2l-2.6 2.6L11 17l5-5-5-5z
             M20 19h-8v2h8c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-8v2h8v14z"
          fill="#000000"/>
  </svg>
</div>

<!-- Title -->
<p class="login-title">Báo cáo Bảo hiểm VBI kênh IPAY</p>

<!-- Subtitle -->
<p class="login-subtitle">Nhập mật khẩu để có thể đăng nhập vào hệ thống</p>
        """,
        unsafe_allow_html=True,
    )

    pwd = st.text_input(
        "password",
        type="password",
        placeholder="Nhập mật khẩu",
        label_visibility="collapsed",
    )

    if st.button("Đăng nhập", use_container_width=False):
        if pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        elif pwd:
            st.error("Mật khẩu không đúng.")


if not st.session_state.authenticated:
    _render_login_page()
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
