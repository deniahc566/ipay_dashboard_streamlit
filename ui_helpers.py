import streamlit as st

from data_loader import load_ipay_data

# ── Shared product constants ──────────────────────────────────────────────────
NAMED_PRODUCTS: set = {"MIX_01", "VTB_HOMESAVING", "TAPCARE", "ISAFE_CYBER"}

PRODUCT_DISPLAY_NAMES: dict = {
    "ISAFE_CYBER":    "I-Safe",
    "MIX_01":         "Cyber Risk",
    "TAPCARE":        "TapCare",
    "VTB_HOMESAVING": "HomeSaving",
    "CN.4.1IPAY":     "Du lịch quốc tế bán kèm",
    "CN.4.1SA":       "Du lịch quốc tế bán lẻ",
    "CN.4.3IPAY":     "Du lịch trong nước bán kèm",
    "CN.4.3SA":       "Du lịch trong nước bán lẻ",
    "CN.6":           "Bảo hiểm sức khỏe",
    "XC.1.1":         "Bảo hiểm xe máy",
    "XE":             "Bảo hiểm ô tô",
    "UTV":            "Ung thư vú",
    "Sản phẩm khác":  "Sản phẩm khác",
}


# ── Shared formatting helpers ─────────────────────────────────────────────────
def fmt_currency(value: float) -> str:
    billions = value / 1_000_000_000
    if billions >= 1:
        return f"{billions:,.2f} tỷ"
    return f"{value / 1_000_000:,.1f} tr"


def yoy_caption(current_val: float, yoy_val: float, fmt_fn, prev_year: int) -> str:
    if yoy_val == 0:
        return f'<span style="font-size:0.56rem;color:#888">Cùng kỳ {prev_year}: N/A</span>'
    pct   = (current_val - yoy_val) / abs(yoy_val)
    arrow = "▲" if pct > 0 else "▼"
    color = "#2e7d32" if pct > 0 else "#c62828"
    return (
        f'<span style="font-size:0.56rem;color:#888">Cùng kỳ {prev_year}: {fmt_fn(yoy_val)}&nbsp;&nbsp;</span>'
        f'<span style="font-size:0.56rem;font-weight:600;color:{color}">{arrow} {pct:+.1%}</span>'
    )


def kpi_card(
    label, value, delta_str, delta_color,
    accent_color="#2C4C7B", yoy_html="", tooltip="", subtitle="", progress_pct=None,
) -> str:
    _label_html = label
    if tooltip:
        _label_html += (
            f'&nbsp;<abbr title="{tooltip}" '
            f'style="font-size:0.65rem;color:#aaa;cursor:help;text-decoration:none;">ℹ</abbr>'
        )
    if progress_pct is not None:
        fill = f"{progress_pct * 100:.1f}%"
        sidebar = (
            f'<div style="width:4px;border-radius:3px;background:#e8e8e8;flex-shrink:0;'
            f'position:relative;overflow:hidden;">'
            f'<div style="position:absolute;bottom:0;width:100%;height:{fill};'
            f'background:{accent_color};border-radius:3px;"></div></div>'
        )
        pad_left = "10px"
    else:
        sidebar  = f'<div style="width:4px;border-radius:3px;background:{accent_color};flex-shrink:0;"></div>'
        pad_left = "14px"
    parts = [
        f'<div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;'
        f'padding:14px 14px 11px {pad_left};box-shadow:0 2px 8px rgba(0,0,0,0.06);'
        f'display:flex;gap:8px;align-items:stretch;min-height:126px;">',
        sidebar,
        f'<div style="flex:1;min-width:0;">',
        f'<div style="font-size:0.55rem;font-weight:600;color:#555;text-transform:uppercase;'
        f'letter-spacing:0.04em;margin-bottom:4px;">{_label_html}</div>',
        f'<div style="font-size:1.26rem;font-weight:700;color:#1a1a2e;line-height:1.1;">{value}</div>',
    ]
    if subtitle:
        parts.append(f'<div style="font-size:0.56rem;color:#888;margin-top:1px;">{subtitle}</div>')
    parts.append(
        f'<div style="margin-top:3px;font-size:0.57rem;font-weight:600;color:{delta_color};">{delta_str}</div>'
    )
    if yoy_html:
        parts.append(f'<div style="margin-top:3px;">{yoy_html}</div>')
    parts += ['</div>', '</div>']
    return "".join(parts)


# ── Action buttons ────────────────────────────────────────────────────────────
def render_action_buttons() -> None:
    """Render a Làm mới (refresh) button in the top-right area."""
    _, col_refresh = st.columns([8, 1])
    with col_refresh:
        if st.button("⟳ Làm mới", width="stretch",
                     help="Xóa cache và tải lại dữ liệu mới nhất từ MotherDuck"):
            load_ipay_data.clear()
            st.rerun()
