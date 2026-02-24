import os
import streamlit as st
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_NUMERIC_COLS = [
    "Tiền thực thu",
    "Số đơn cấp mới",
    "Số đơn cấp tái tục",
    "Số đơn tái tục dự kiến",
    "Số đơn có hiệu lực",
    "Số đơn tạm ngưng",
    "Số đơn hủy webview",
]

_ISAFE_PROD_CODE = "ISAFE_CYBER"


@st.cache_data(ttl=300)
def _load_data() -> pd.DataFrame:
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")
    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    df = con.execute("SELECT * FROM gold.ipay_quantity_rev_data").df()
    con.close()
    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _fmt_currency(value: float) -> str:
    billions = value / 1_000_000_000
    if billions >= 1:
        return f"{billions:,.2f} tỷ"
    millions = value / 1_000_000
    return f"{millions:,.1f} tr"


def _kpi_card(
    label, value, delta_str, delta_color,
    accent_color="#2C4C7B", yoy_html="",
):
    parts = [
        f'<div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;'
        f'padding:14px 14px 11px 10px;box-shadow:0 2px 8px rgba(0,0,0,0.06);'
        f'display:flex;gap:8px;align-items:stretch;min-height:126px;">',
        f'<div style="width:4px;border-radius:3px;background:{accent_color};flex-shrink:0;"></div>',
        f'<div style="flex:1;min-width:0;">',
        f'<div style="font-size:0.55rem;font-weight:600;color:#555;text-transform:uppercase;'
        f'letter-spacing:0.04em;margin-bottom:4px;">{label}</div>',
        f'<div style="font-size:1.26rem;font-weight:700;color:#1a1a2e;line-height:1.1;">{value}</div>',
        f'<div style="margin-top:3px;font-size:0.57rem;font-weight:600;color:{delta_color};">{delta_str}</div>',
    ]
    if yoy_html:
        parts.append(f'<div style="margin-top:3px;">{yoy_html}</div>')
    parts += ['</div>', '</div>']
    return "".join(parts)


def render_isafe_page():
    st.markdown(
        '<style>section[data-testid="stMain"]{zoom:1;}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;white-space:nowrap;margin-bottom:0.5rem;">'
        'BÁO CÁO CHI TIẾT SẢN PHẨM I-SAFE</h1>',
        unsafe_allow_html=True,
    )

    try:
        full_df = _load_data()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    # Filter to I-Safe product only
    isafe_full_df = full_df[full_df["PROD_CODE"] == _ISAFE_PROD_CODE].copy()

    # ── Year filter (default 2026) ────────────────────────────────────────────
    all_years = sorted(isafe_full_df["Năm"].dropna().unique().astype(int).tolist(), reverse=True)
    default_years = [2026] if 2026 in all_years else (all_years[:1] if all_years else [])
    selected_years = st.multiselect(
        "Năm",
        options=all_years,
        default=default_years,
        placeholder="Chọn năm...",
    )
    df = isafe_full_df[isafe_full_df["Năm"].isin(selected_years)] if selected_years else isafe_full_df

    # ── Guard ─────────────────────────────────────────────────────────────────
    sorted_dates = sorted(df["Ngày phát sinh"].unique())
    if len(sorted_dates) < 2:
        st.warning("Không đủ dữ liệu để hiển thị. Vui lòng chọn thêm năm.")
        return

    last_date = sorted_dates[-2]   # most recent complete day (báo cáo chậm 1 ngày)
    prev_date = sorted_dates[-3] if len(sorted_dates) >= 3 else sorted_dates[0]

    last_df = df[df["Ngày phát sinh"] == last_date]
    prev_df = df[df["Ngày phát sinh"] == prev_date]

    # ── KPI aggregates ────────────────────────────────────────────────────────
    tong_tien    = df["Tiền thực thu"].sum()
    tong_cap_moi = int(df["Số đơn cấp mới"].sum())
    tong_tai_tuc = int(df["Số đơn cấp tái tục"].sum())
    tong_huy     = df["Số đơn hủy webview"].sum()

    tong_tai_tuc_dk = df["Số đơn tái tục dự kiến"].sum()

    kh_hien_huu  = int(last_df["Số đơn có hiệu lực"].sum())
    ty_le_huy    = tong_huy / (tong_cap_moi + tong_tai_tuc) if (tong_cap_moi + tong_tai_tuc) > 0 else 0
    ty_le_tai_tuc = tong_tai_tuc / tong_tai_tuc_dk if tong_tai_tuc_dk > 0 else 0

    # ── Deltas vs previous day ────────────────────────────────────────────────
    delta_tien    = last_df["Tiền thực thu"].sum()
    delta_cap_moi = int(last_df["Số đơn cấp mới"].sum())

    kh_prev  = int(prev_df["Số đơn có hiệu lực"].sum())
    delta_kh = kh_hien_huu - kh_prev

    prev_denom = int(prev_df["Số đơn cấp mới"].sum()) + int(prev_df["Số đơn cấp tái tục"].sum())
    prev_ty_le = prev_df["Số đơn hủy webview"].sum() / prev_denom if prev_denom > 0 else 0
    last_denom = int(last_df["Số đơn cấp mới"].sum()) + int(last_df["Số đơn cấp tái tục"].sum())
    last_ty_le = last_df["Số đơn hủy webview"].sum() / last_denom if last_denom > 0 else 0
    delta_ty_le = last_ty_le - prev_ty_le

    last_tai_tuc_dk = last_df["Số đơn tái tục dự kiến"].sum()
    prev_tai_tuc_dk = prev_df["Số đơn tái tục dự kiến"].sum()
    last_tt_rate = last_df["Số đơn cấp tái tục"].sum() / last_tai_tuc_dk if last_tai_tuc_dk > 0 else 0
    prev_tt_rate = prev_df["Số đơn cấp tái tục"].sum() / prev_tai_tuc_dk if prev_tai_tuc_dk > 0 else 0
    delta_tai_tuc = last_tt_rate - prev_tt_rate

    # ── YoY: cùng kỳ năm trước ───────────────────────────────────────────────
    current_year = int(last_date.year)
    prev_year    = current_year - 1
    try:
        yoy_cutoff = last_date.replace(year=prev_year)
    except ValueError:                    # leap-day guard
        yoy_cutoff = last_date.replace(year=prev_year, day=28)

    yoy_df = isafe_full_df[
        (isafe_full_df["Năm"] == prev_year) &
        (isafe_full_df["Ngày phát sinh"] <= yoy_cutoff)
    ]
    yoy_tien         = yoy_df["Tiền thực thu"].sum()
    yoy_cap_moi      = int(yoy_df["Số đơn cấp mới"].sum())
    yoy_tai_tuc_dk   = yoy_df["Số đơn tái tục dự kiến"].sum()
    yoy_ty_le_tai_tuc = (
        yoy_df["Số đơn cấp tái tục"].sum() / yoy_tai_tuc_dk
        if yoy_tai_tuc_dk > 0 else 0
    )

    # KH hiện hữu YoY: stock value at the equivalent date in prev_year
    yoy_last_date = yoy_df["Ngày phát sinh"].max() if not yoy_df.empty else None
    yoy_kh = 0
    if yoy_last_date is not None and pd.notna(yoy_last_date):
        yoy_kh = int(yoy_df[yoy_df["Ngày phát sinh"] == yoy_last_date]["Số đơn có hiệu lực"].sum())

    def _yoy_caption(current_val: float, yoy_val: float, fmt_fn) -> str:
        if yoy_val == 0:
            return f'<span style="font-size:0.56rem;color:#888">Cùng kỳ {prev_year}: N/A</span>'
        pct   = (current_val - yoy_val) / abs(yoy_val)
        arrow = "▲" if pct > 0 else "▼"
        color = "#2e7d32" if pct > 0 else "#c62828"
        return (
            f'<span style="font-size:0.56rem;color:#888">Cùng kỳ {prev_year}: {fmt_fn(yoy_val)}&nbsp;&nbsp;</span>'
            f'<span style="font-size:0.56rem;font-weight:600;color:{color}">{arrow} {pct:+.1%}</span>'
        )

    # ── Scorecards ───────────────────────────────────────────────────────────
    _prev_str = pd.Timestamp(prev_date).strftime("%d-%m-%Y")
    st.markdown(
        f'<p style="font-size:0.78rem;color:#888;margin-bottom:4px">'
        f'↕ Mũi tên xanh/đỏ: so với ngày trước đó ({_prev_str})</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)

    with cols[0]:
        _ds = "+" if delta_tien >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng tiền thực thu",
            value=_fmt_currency(tong_tien),
            delta_str=f"{_ds}{_fmt_currency(delta_tien)}",
            delta_color="#2e7d32",
            accent_color="#2C4C7B",
            yoy_html=_yoy_caption(tong_tien, yoy_tien, _fmt_currency),
        ), unsafe_allow_html=True)

    with cols[1]:
        _cap_sign = "+" if delta_cap_moi >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng số đơn cấp mới",
            value=f"{tong_cap_moi:,}",
            delta_str=f"{_cap_sign}{delta_cap_moi:,}",
            delta_color="#2e7d32",
            accent_color="#6A415E",
            yoy_html=_yoy_caption(tong_cap_moi, yoy_cap_moi, lambda v: f"{int(v):,}"),
        ), unsafe_allow_html=True)

    with cols[2]:
        _kh_color = "#2e7d32" if delta_kh >= 0 else "#c62828"
        _kh_sign  = "+" if delta_kh >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng số KH hiện hữu",
            value=f"{kh_hien_huu:,}",
            delta_str=f"{_kh_sign}{delta_kh:,}",
            delta_color=_kh_color,
            accent_color="#6b3fa0",
            yoy_html=_yoy_caption(kh_hien_huu, yoy_kh, lambda v: f"{int(v):,}"),
        ), unsafe_allow_html=True)

    with cols[3]:
        _huy_color = "#c62828" if delta_ty_le > 0 else "#2e7d32"
        st.markdown(_kpi_card(
            label="Tỷ lệ hủy chủ động",
            value=f"{ty_le_huy:.1%}",
            delta_str=f"{delta_ty_le:+.2%}",
            delta_color=_huy_color,
            accent_color="#d71149",
        ), unsafe_allow_html=True)

    with cols[4]:
        _tt_color = "#2e7d32" if delta_tai_tuc >= 0 else "#c62828"
        st.markdown(_kpi_card(
            label="Tỷ lệ tái tục / dự kiến",
            value=f"{ty_le_tai_tuc:.1%}",
            delta_str=f"{delta_tai_tuc:+.2%}",
            delta_color=_tt_color,
            accent_color="#2C7B6F",
            yoy_html=_yoy_caption(ty_le_tai_tuc, yoy_ty_le_tai_tuc, lambda v: f"{v:.1%}"),
        ), unsafe_allow_html=True)


# Alias for backward compatibility with app.py
render_operations_page = render_isafe_page
