import streamlit as st

from data_loader import load_ipay_data


def render_action_buttons() -> None:
    """Render a Làm mới (refresh) button in the top-right area."""
    _, col_refresh = st.columns([8, 1])
    with col_refresh:
        if st.button("⟳ Làm mới", use_container_width=True,
                     help="Xóa cache và tải lại dữ liệu mới nhất từ MotherDuck"):
            load_ipay_data.clear()
            st.rerun()
