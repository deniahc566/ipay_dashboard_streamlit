import streamlit as st

from data_loader import load_ipay_data

# Injected once; hides sidebar/chrome when the browser prints to PDF
_PRINT_CSS = """
<style>
@media print {
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu, footer { display: none !important; }
    section[data-testid="stMain"] { margin-left: 0 !important; }
}
</style>
"""


def render_action_buttons() -> None:
    """Render a Làm mới (refresh) button and an Xuất PDF button in the top-right area."""
    st.markdown(_PRINT_CSS, unsafe_allow_html=True)

    _, col_refresh, col_pdf = st.columns([7, 1, 1])
    with col_refresh:
        if st.button("🔄 Làm mới", use_container_width=True,
                     help="Xóa cache và tải lại dữ liệu mới nhất từ MotherDuck"):
            load_ipay_data.clear()
            st.rerun()
    with col_pdf:
        st.markdown(
            '<button onclick="window.print()" '
            'style="width:100%;height:38px;padding:0 8px;'
            'border:1px solid rgba(49,51,63,0.2);border-radius:6px;'
            'background:#ffffff;cursor:pointer;font-size:0.875rem;'
            'color:rgb(49,51,63);white-space:nowrap;">'
            '📄 Xuất PDF</button>',
            unsafe_allow_html=True,
        )
