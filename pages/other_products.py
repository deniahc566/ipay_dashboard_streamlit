import streamlit as st
import pandas as pd
import altair as alt

from data_loader import load_ipay_data
from ui_helpers import render_action_buttons

_NAMED_PRODUCTS = {"MIX_01", "VTB_HOMESAVING", "TAPCARE", "ISAFE_CYBER"}

_PRODUCT_DISPLAY_NAMES = {
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
}


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


def render_other_products_page():
    st.markdown(
        '<style>section[data-testid="stMain"]{zoom:1;}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;white-space:nowrap;margin-bottom:0.5rem;">'
        'BÁO CÁO SẢN PHẨM KHÁC</h1>',
        unsafe_allow_html=True,
    )
    render_action_buttons()

    try:
        full_df = load_ipay_data()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    # Filter to "other" products only
    prod_full_df = full_df[~full_df["PROD_CODE"].isin(_NAMED_PRODUCTS)].copy()

    # ── Year filter ────────────────────────────────────────────────────────────
    all_years = sorted(prod_full_df["Năm"].dropna().unique().astype(int).tolist(), reverse=True)
    default_years = [2026] if 2026 in all_years else (all_years[:1] if all_years else [])
    selected_years = st.multiselect(
        "Năm",
        options=all_years,
        default=default_years,
        placeholder="Chọn năm...",
    )
    df = prod_full_df[prod_full_df["Năm"].isin(selected_years)] if selected_years else prod_full_df

    if df.empty:
        st.warning("Không có dữ liệu cho các năm đã chọn.")
        return

    # ── Sorted dates ──────────────────────────────────────────────────────────
    sorted_dates = sorted(df["Ngày phát sinh"].unique())
    if len(sorted_dates) < 2:
        st.warning("Không đủ dữ liệu để hiển thị. Vui lòng chọn thêm năm.")
        return

    last_date = sorted_dates[-2]
    prev_date = sorted_dates[-3] if len(sorted_dates) >= 3 else sorted_dates[0]

    last_df = df[df["Ngày phát sinh"] == last_date]
    prev_df = df[df["Ngày phát sinh"] == prev_date]

    # ── KPI aggregates ────────────────────────────────────────────────────────
    tong_tien    = df["Tiền thực thu"].sum()
    tong_cap_moi = int(df["Số đơn cấp mới"].sum())

    # ── Deltas vs previous day ────────────────────────────────────────────────
    delta_tien    = last_df["Tiền thực thu"].sum()
    delta_cap_moi = int(last_df["Số đơn cấp mới"].sum())

    # ── YoY ───────────────────────────────────────────────────────────────────
    current_year = int(last_date.year)
    prev_year    = current_year - 1
    try:
        yoy_cutoff = last_date.replace(year=prev_year)
    except ValueError:
        yoy_cutoff = last_date.replace(year=prev_year, day=28)

    yoy_df = prod_full_df[
        (prod_full_df["Năm"] == prev_year) &
        (prod_full_df["Ngày phát sinh"] <= yoy_cutoff)
    ]
    yoy_tien    = yoy_df["Tiền thực thu"].sum()
    yoy_cap_moi = int(yoy_df["Số đơn cấp mới"].sum())

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

    # ── Scorecards ────────────────────────────────────────────────────────────
    _prev_str = pd.Timestamp(prev_date).strftime("%d-%m-%Y")
    st.markdown(
        f'<p style="font-size:0.78rem;color:#888;margin-bottom:4px">'
        f'↕ Mũi tên xanh/đỏ: so với ngày trước đó ({_prev_str})</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(3)

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
        st.markdown(_kpi_card(
            label="Tổng số đơn cấp mới",
            value=f"{tong_cap_moi:,}",
            delta_str=f"+{delta_cap_moi:,}",
            delta_color="#2e7d32",
            accent_color="#6A415E",
            yoy_html=_yoy_caption(tong_cap_moi, yoy_cap_moi, lambda v: f"{int(v):,}"),
        ), unsafe_allow_html=True)

    # ── Helpers ───────────────────────────────────────────────────────────────
    _display_names = _PRODUCT_DISPLAY_NAMES

    def _prod_label(code: str) -> str:
        return _display_names.get(code, code)

    def _fmt_vnd(v: float) -> str:
        if v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f} tỷ"
        return f"{v / 1_000_000:.2f} triệu"

    def _chart_title(text: str) -> None:
        st.markdown(
            f'<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);'
            f'margin:0 0 0.28rem 0;line-height:1.3;">{text}</p>',
            unsafe_allow_html=True,
        )

    # ── Row 1: Revenue by product | Revenue by month ──────────────────────────
    st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
    col_rev, col_trend = st.columns(2)

    with col_rev:
        _chart_title("Tiền thực thu theo sản phẩm")
        selected_months = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="other_rev_prod_months",
        )
        df_prod = (
            df[df["Ngày phát sinh"].dt.month.isin(selected_months)]
            if selected_months else df
        )
        rev_prod_df = (
            df_prod.groupby(["PROD_CODE", "Năm"], as_index=False)["Tiền thực thu"]
            .sum()
            .assign(Năm=lambda x: x["Năm"].astype(str))
        )
        rev_prod_df["label"] = rev_prod_df["Tiền thực thu"].apply(_fmt_vnd)
        rev_prod_df["PROD_CODE"] = rev_prod_df["PROD_CODE"].map(_prod_label)
        prod_order = (
            rev_prod_df.groupby("PROD_CODE")["Tiền thực thu"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        bars = (
            alt.Chart(rev_prod_df)
            .mark_bar()
            .encode(
                x=alt.X("PROD_CODE:N", title=None, sort=prod_order,
                         axis=alt.Axis(labelAngle=-30, labelLimit=120)),
                y=alt.Y("Tiền thực thu:Q", title=None, axis=None),
                color=alt.Color("Năm:N", title="Năm", legend=None,
                                 scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Sản phẩm"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("label:N", title="Tiền thực thu"),
                ],
            )
        )
        labels = (
            alt.Chart(rev_prod_df)
            .mark_text(dy=-6, fontSize=11, fontWeight="normal")
            .encode(
                x=alt.X("PROD_CODE:N", sort=prod_order),
                y=alt.Y("Tiền thực thu:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((bars + labels).properties(height=280), width='stretch')

    with col_trend:
        _chart_title("Tiền thực thu theo tháng")
        all_prod_labels = sorted(
            df["PROD_CODE"].map(_prod_label).unique().tolist()
        )
        selected_trend_prods = st.multiselect(
            "Lọc sản phẩm",
            options=all_prod_labels,
            default=[],
            placeholder="Tất cả sản phẩm",
            key="other_rev_month_prods",
        )
        if selected_trend_prods:
            df_trend = df[df["PROD_CODE"].map(_prod_label).isin(selected_trend_prods)]
        else:
            df_trend = df
        monthly_df = (
            df_trend.assign(
                Tháng=df_trend["Ngày phát sinh"].dt.month,
                Năm=df_trend["Năm"].astype(str),
            )
            .groupby(["Năm", "Tháng"], as_index=False)["Tiền thực thu"]
            .sum()
        )
        year_list = monthly_df["Năm"].unique().tolist()
        full_grid = pd.DataFrame(
            [(y, m) for y in year_list for m in range(1, 13)],
            columns=["Năm", "Tháng"],
        )
        monthly_df = full_grid.merge(monthly_df, on=["Năm", "Tháng"], how="left").fillna(0)
        monthly_df["label"] = monthly_df["Tiền thực thu"].apply(_fmt_vnd)
        m_bars = (
            alt.Chart(monthly_df)
            .mark_bar()
            .encode(
                x=alt.X("Tháng:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Tiền thực thu:Q", title=None, axis=None),
                color=alt.Color("Năm:N", title=None, legend=None,
                                 scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("Tháng:O", title="Tháng"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("label:N", title="Tiền thực thu"),
                ],
            )
        )
        m_labels = (
            alt.Chart(monthly_df[monthly_df["Tiền thực thu"] > 0])
            .mark_text(dy=-6, fontSize=11, fontWeight="normal")
            .encode(
                x=alt.X("Tháng:O"),
                y=alt.Y("Tiền thực thu:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((m_bars + m_labels).properties(height=280), width='stretch')

    # ── Row 2: New orders by product | New orders by month ────────────────────
    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    col_new_prod, col_new_month = st.columns(2)

    with col_new_prod:
        _chart_title("Số đơn cấp mới theo sản phẩm")
        selected_months_new = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="other_new_prod_months",
        )
        df_new_prod = (
            df[df["Ngày phát sinh"].dt.month.isin(selected_months_new)]
            if selected_months_new else df
        )
        new_prod_df = (
            df_new_prod.groupby(["PROD_CODE", "Năm"], as_index=False)["Số đơn cấp mới"]
            .sum()
            .assign(Năm=lambda x: x["Năm"].astype(str))
        )
        new_prod_df["label"] = new_prod_df["Số đơn cấp mới"].apply(lambda v: f"{int(v):,}")
        new_prod_df["PROD_CODE"] = new_prod_df["PROD_CODE"].map(_prod_label)
        new_prod_order = (
            new_prod_df.groupby("PROD_CODE")["Số đơn cấp mới"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        new_bars = (
            alt.Chart(new_prod_df)
            .mark_bar()
            .encode(
                x=alt.X("PROD_CODE:N", title=None, sort=new_prod_order,
                         axis=alt.Axis(labelAngle=-30, labelLimit=120)),
                y=alt.Y("Số đơn cấp mới:Q", title=None, axis=None),
                color=alt.Color("Năm:N", title=None, legend=None,
                                 scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                xOffset=alt.XOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Sản phẩm"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("Số đơn cấp mới:Q", title="Số đơn", format=",.0f"),
                ],
            )
        )
        new_labels = (
            alt.Chart(new_prod_df[new_prod_df["Số đơn cấp mới"] > 0])
            .mark_text(dy=-6, fontSize=11, fontWeight="normal")
            .encode(
                x=alt.X("PROD_CODE:N", sort=new_prod_order),
                y=alt.Y("Số đơn cấp mới:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((new_bars + new_labels).properties(height=280), width='stretch')

    with col_new_month:
        _chart_title("Số đơn cấp mới theo tháng")
        selected_new_month_prods = st.multiselect(
            "Lọc sản phẩm",
            options=all_prod_labels,
            default=[],
            placeholder="Tất cả sản phẩm",
            key="other_new_month_prods",
        )
        if selected_new_month_prods:
            df_nm = df[df["PROD_CODE"].map(_prod_label).isin(selected_new_month_prods)]
        else:
            df_nm = df
        new_monthly_df = (
            df_nm.assign(
                Tháng=df_nm["Ngày phát sinh"].dt.month,
                Năm=df_nm["Năm"].astype(str),
            )
            .groupby(["Năm", "Tháng"], as_index=False)["Số đơn cấp mới"]
            .sum()
        )
        year_list_nm = new_monthly_df["Năm"].unique().tolist()
        full_grid_nm = pd.DataFrame(
            [(y, m) for y in year_list_nm for m in range(1, 13)],
            columns=["Năm", "Tháng"],
        )
        new_monthly_df = full_grid_nm.merge(new_monthly_df, on=["Năm", "Tháng"], how="left").fillna(0)
        new_monthly_df["label"] = new_monthly_df["Số đơn cấp mới"].apply(lambda v: f"{int(v):,}")
        nm_bars = (
            alt.Chart(new_monthly_df)
            .mark_bar()
            .encode(
                x=alt.X("Tháng:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Số đơn cấp mới:Q", title=None, axis=None),
                color=alt.Color("Năm:N", title=None, legend=None,
                                 scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                xOffset=alt.XOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("Tháng:O", title="Tháng"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("Số đơn cấp mới:Q", title="Số đơn", format=",.0f"),
                ],
            )
        )
        nm_labels = (
            alt.Chart(new_monthly_df[new_monthly_df["Số đơn cấp mới"] > 0])
            .mark_text(dy=-6, fontSize=11, fontWeight="normal")
            .encode(
                x=alt.X("Tháng:O"),
                y=alt.Y("Số đơn cấp mới:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((nm_bars + nm_labels).properties(height=280), width='stretch')

    st.markdown('<div style="margin-bottom:32px;"></div>', unsafe_allow_html=True)
