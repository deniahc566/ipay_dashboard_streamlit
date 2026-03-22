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
        'BÁO CÁO SẢN PHẨM BÁN LẺ</h1>',
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

    cols = st.columns(2)

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

    # ── Rolling 12-month cutoff (dùng chung cho tất cả chart theo tháng) ──────
    _latest_date = prod_full_df["Ngày phát sinh"].max()
    _cutoff_dt = (_latest_date - pd.DateOffset(months=11)).replace(day=1)

    # ── Row 1: Revenue by product | Revenue by month ──────────────────────────
    st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
    col_rev, col_trend = st.columns(2)

    # Widgets first (so both filters are known before computing dataframes)
    with col_rev:
        _chart_title("Tiền thực thu theo sản phẩm")
        selected_months = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="other_rev_prod_months",
        )
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

    # Compute dataframes
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

    _src_trend = prod_full_df[prod_full_df["Ngày phát sinh"] >= _cutoff_dt]
    if selected_trend_prods:
        _src_trend = _src_trend[_src_trend["PROD_CODE"].map(_prod_label).isin(selected_trend_prods)]
    monthly_df = (
        _src_trend.assign(Tháng=_src_trend["Ngày phát sinh"].dt.to_period("M").astype(str))
        .groupby("Tháng", as_index=False)["Tiền thực thu"]
        .sum()
    )
    monthly_df["label"] = monthly_df["Tiền thực thu"].apply(_fmt_vnd)

    max_rev = float(pd.Series([rev_prod_df["Tiền thực thu"].max(), monthly_df["Tiền thực thu"].max(), 1]).max()) * 1.15

    # Charts
    with col_rev:
        bars = (
            alt.Chart(rev_prod_df)
            .mark_bar()
            .encode(
                y=alt.Y("PROD_CODE:N", title=None, sort=prod_order,
                         axis=alt.Axis(labelLimit=200, labelFontSize=11)),
                x=alt.X("Tiền thực thu:Q", title=None, axis=None,
                         scale=alt.Scale(domain=[0, max_rev])),
                color=alt.Color("Năm:N", title="Năm", legend=None,
                                 scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                yOffset=alt.YOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Sản phẩm"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("label:N", title="Tiền thực thu"),
                ],
            )
        )
        labels = (
            alt.Chart(rev_prod_df)
            .mark_text(dx=6, fontSize=11, align="left")
            .encode(
                y=alt.Y("PROD_CODE:N", sort=prod_order),
                x=alt.X("Tiền thực thu:Q", scale=alt.Scale(domain=[0, max_rev])),
                yOffset=alt.YOffset("Năm:N"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((bars + labels).properties(height=320), width='stretch')

    with col_trend:
        m_bars = (
            alt.Chart(monthly_df)
            .mark_bar(color="#2C4C7B")
            .encode(
                x=alt.X("Tháng:N", title=None, sort=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("Tiền thực thu:Q", title=None, axis=None),
                tooltip=[
                    alt.Tooltip("Tháng:N", title="Tháng"),
                    alt.Tooltip("label:N", title="Tiền thực thu"),
                ],
            )
        )
        m_labels = (
            alt.Chart(monthly_df[monthly_df["Tiền thực thu"] > 0])
            .mark_text(dy=-6, fontSize=11, color="#2C4C7B")
            .encode(
                x=alt.X("Tháng:N", sort=None),
                y=alt.Y("Tiền thực thu:Q"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((m_bars + m_labels).properties(height=280), width='stretch')

    # ── Row 2: Average daily line charts ──────────────────────────────────────
    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    col_avg_rev, col_avg_new = st.columns(2)

    with col_avg_rev:
        _chart_title("Tiền thực thu trung bình/ngày theo tháng")
        selected_avg_rev_prods = st.multiselect(
            "Lọc sản phẩm", options=all_prod_labels, default=[],
            placeholder="Tất cả sản phẩm", key="other_avg_rev_prods",
        )
    with col_avg_new:
        _chart_title("Số đơn cấp mới trung bình/ngày theo tháng")
        selected_avg_new_prods = st.multiselect(
            "Lọc sản phẩm", options=all_prod_labels, default=[],
            placeholder="Tất cả sản phẩm", key="other_avg_new_prods",
        )

    _src_avg_rev = prod_full_df[prod_full_df["Ngày phát sinh"] >= _cutoff_dt]
    if selected_avg_rev_prods:
        _src_avg_rev = _src_avg_rev[_src_avg_rev["PROD_CODE"].map(_prod_label).isin(selected_avg_rev_prods)]
    avg_rev_df = (
        _src_avg_rev.assign(Tháng=_src_avg_rev["Ngày phát sinh"].dt.to_period("M").astype(str))
        .groupby("Tháng")
        .agg(Tổng=("Tiền thực thu", "sum"), Ngày=("Ngày phát sinh", "nunique"))
        .reset_index()
    )
    avg_rev_df["TB/ngày"] = avg_rev_df["Tổng"] / avg_rev_df["Ngày"]
    avg_rev_df["label"] = avg_rev_df["TB/ngày"].apply(_fmt_vnd)

    _src_avg_new = prod_full_df[prod_full_df["Ngày phát sinh"] >= _cutoff_dt]
    if selected_avg_new_prods:
        _src_avg_new = _src_avg_new[_src_avg_new["PROD_CODE"].map(_prod_label).isin(selected_avg_new_prods)]
    avg_new_df = (
        _src_avg_new.assign(Tháng=_src_avg_new["Ngày phát sinh"].dt.to_period("M").astype(str))
        .groupby("Tháng")
        .agg(Tổng=("Số đơn cấp mới", "sum"), Ngày=("Ngày phát sinh", "nunique"))
        .reset_index()
    )
    avg_new_df["TB/ngày"] = avg_new_df["Tổng"] / avg_new_df["Ngày"]
    avg_new_df["label"] = avg_new_df["TB/ngày"].apply(lambda v: f"{v:,.1f}")

    with col_avg_rev:
        line_rev = (
            alt.Chart(avg_rev_df[avg_rev_df["TB/ngày"] > 0])
            .mark_line(color="#2C4C7B", point=alt.OverlayMarkDef(color="#2C4C7B"))
            .encode(
                x=alt.X("Tháng:N", title=None, sort=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("TB/ngày:Q", title=None, axis=None),
                tooltip=[
                    alt.Tooltip("Tháng:N", title="Tháng"),
                    alt.Tooltip("label:N", title="TB/ngày"),
                ],
            )
        )
        text_rev = (
            alt.Chart(avg_rev_df[avg_rev_df["TB/ngày"] > 0])
            .mark_text(dy=-12, fontSize=11, color="#2C4C7B")
            .encode(
                x=alt.X("Tháng:N", sort=None),
                y=alt.Y("TB/ngày:Q"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((line_rev + text_rev).properties(height=240), width="stretch")

    with col_avg_new:
        line_new = (
            alt.Chart(avg_new_df[avg_new_df["TB/ngày"] > 0])
            .mark_line(color="#6A415E", point=alt.OverlayMarkDef(color="#6A415E"))
            .encode(
                x=alt.X("Tháng:N", title=None, sort=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("TB/ngày:Q", title=None, axis=None),
                tooltip=[
                    alt.Tooltip("Tháng:N", title="Tháng"),
                    alt.Tooltip("label:N", title="TB/ngày"),
                ],
            )
        )
        text_new = (
            alt.Chart(avg_new_df[avg_new_df["TB/ngày"] > 0])
            .mark_text(dy=-12, fontSize=11, color="#6A415E")
            .encode(
                x=alt.X("Tháng:N", sort=None),
                y=alt.Y("TB/ngày:Q"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((line_new + text_new).properties(height=240), width="stretch")

    # ── Row 3: New orders by product | New orders by month ────────────────────
    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    col_new_prod, col_new_month = st.columns(2)

    with col_new_prod:
        _chart_title("Số đơn cấp mới theo sản phẩm")
        selected_months_new = st.multiselect(
            "Lọc tháng", options=list(range(1, 13)), default=[],
            placeholder="Tất cả tháng", key="other_new_prod_months",
        )
    with col_new_month:
        _chart_title("Số đơn cấp mới theo tháng")
        selected_new_month_prods = st.multiselect(
            "Lọc sản phẩm", options=all_prod_labels, default=[],
            placeholder="Tất cả sản phẩm", key="other_new_month_prods",
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

    _src_nm = prod_full_df[prod_full_df["Ngày phát sinh"] >= _cutoff_dt]
    if selected_new_month_prods:
        _src_nm = _src_nm[_src_nm["PROD_CODE"].map(_prod_label).isin(selected_new_month_prods)]
    new_monthly_df = (
        _src_nm.assign(Tháng=_src_nm["Ngày phát sinh"].dt.to_period("M").astype(str))
        .groupby("Tháng", as_index=False)["Số đơn cấp mới"]
        .sum()
    )
    new_monthly_df["label"] = new_monthly_df["Số đơn cấp mới"].apply(lambda v: f"{int(v):,}")

    max_new = float(pd.Series([new_prod_df["Số đơn cấp mới"].max(), new_monthly_df["Số đơn cấp mới"].max(), 1]).max()) * 1.15

    with col_new_prod:
        new_bars = (
            alt.Chart(new_prod_df)
            .mark_bar()
            .encode(
                y=alt.Y("PROD_CODE:N", title=None, sort=new_prod_order,
                         axis=alt.Axis(labelLimit=200, labelFontSize=11)),
                x=alt.X("Số đơn cấp mới:Q", title=None, axis=None,
                         scale=alt.Scale(domain=[0, max_new])),
                color=alt.Color("Năm:N", title=None, legend=None,
                                 scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                yOffset=alt.YOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Sản phẩm"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("Số đơn cấp mới:Q", title="Số đơn", format=",.0f"),
                ],
            )
        )
        new_labels = (
            alt.Chart(new_prod_df[new_prod_df["Số đơn cấp mới"] > 0])
            .mark_text(dx=6, fontSize=11, align="left")
            .encode(
                y=alt.Y("PROD_CODE:N", sort=new_prod_order),
                x=alt.X("Số đơn cấp mới:Q", scale=alt.Scale(domain=[0, max_new])),
                yOffset=alt.YOffset("Năm:N"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#6A415E", "#B07A9E"])),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((new_bars + new_labels).properties(height=320), width='stretch')

    with col_new_month:
        nm_bars = (
            alt.Chart(new_monthly_df)
            .mark_bar(color="#6A415E")
            .encode(
                x=alt.X("Tháng:N", title=None, sort=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("Số đơn cấp mới:Q", title=None, axis=None),
                tooltip=[
                    alt.Tooltip("Tháng:N", title="Tháng"),
                    alt.Tooltip("label:N", title="Số đơn cấp mới"),
                ],
            )
        )
        nm_labels = (
            alt.Chart(new_monthly_df[new_monthly_df["Số đơn cấp mới"] > 0])
            .mark_text(dy=-6, fontSize=11, color="#6A415E")
            .encode(
                x=alt.X("Tháng:N", sort=None),
                y=alt.Y("Số đơn cấp mới:Q"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((nm_bars + nm_labels).properties(height=280), width='stretch')

    # ── Detail table ──────────────────────────────────────────────────────────
    import calendar as _cal

    st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
    _chart_title("Bảng chi tiết theo ngày")

    _now = pd.Timestamp.now()
    tbl_cols = st.columns([1, 1, 3])
    with tbl_cols[0]:
        tbl_month = st.selectbox(
            "Tháng", options=list(range(1, 13)),
            index=_now.month - 1, key="other_tbl_month",
        )
    with tbl_cols[1]:
        tbl_year = st.selectbox(
            "Năm", options=all_years, index=0, key="other_tbl_year",
        )
    with tbl_cols[2]:
        _default_prod = ["Bảo hiểm sức khỏe"] if "Bảo hiểm sức khỏe" in all_prod_labels else []
        tbl_prods = st.multiselect(
            "Sản phẩm", options=all_prod_labels, default=_default_prod,
            placeholder="Tất cả sản phẩm", key="other_tbl_prods",
        )

    # Build prev-month lookup keyed by (date, prod_code)
    daily_all = (
        prod_full_df.groupby(["Ngày phát sinh", "PROD_CODE"], as_index=False)
        .agg(tien=("Tiền thực thu", "sum"), cap_moi=("Số đơn cấp mới", "sum"))
    )
    _lkmap = daily_all.set_index(["Ngày phát sinh", "PROD_CODE"])[["tien", "cap_moi"]].to_dict(orient="index")

    def _prev_month_date(d):
        y, m, day = d.year, d.month, d.day
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
        return d.replace(year=y, month=m, day=min(day, _cal.monthrange(y, m)[1]))

    def _lk(d, prod, field):
        prev = _prev_month_date(d)
        return float(_lkmap.get((prev, prod), {}).get(field, 0.0))

    def _arrow(cur, ref, higher_is_good=True):
        if ref == 0:
            return f'<span style="color:{"#2e7d32" if higher_is_good else "#c62828"}">▲&nbsp;</span>' if cur > 0 else ""
        if cur > ref:
            return f'<span style="color:{"#2e7d32" if higher_is_good else "#c62828"}">▲&nbsp;</span>'
        if cur < ref:
            return f'<span style="color:{"#c62828" if higher_is_good else "#2e7d32"}">▼&nbsp;</span>'
        return ""

    # Filter to selected month/year/products
    day_df = (
        prod_full_df[
            (prod_full_df["Ngày phát sinh"].dt.month == tbl_month) &
            (prod_full_df["Năm"] == tbl_year)
        ]
        .groupby(["Ngày phát sinh", "PROD_CODE"], as_index=False)
        .agg(tien=("Tiền thực thu", "sum"), cap_moi=("Số đơn cấp mới", "sum"))
    )
    if tbl_prods:
        day_df = day_df[day_df["PROD_CODE"].map(_prod_label).isin(tbl_prods)]

    if day_df.empty:
        st.info("Không có dữ liệu cho tháng/năm đã chọn.")
    else:
        # Expand to all days in month for each product present
        prods_in_data = day_df["PROD_CODE"].unique().tolist()
        _month_start = pd.Timestamp(tbl_year, tbl_month, 1)
        _full_dates = pd.date_range(_month_start, periods=_month_start.days_in_month, freq="D")
        full_grid = pd.DataFrame(
            [(d, p) for d in _full_dates for p in prods_in_data],
            columns=["Ngày phát sinh", "PROD_CODE"],
        )
        day_df = full_grid.merge(day_df, on=["Ngày phát sinh", "PROD_CODE"], how="left").fillna(0.0)
        day_df = day_df.sort_values(["Ngày phát sinh", "PROD_CODE"]).reset_index(drop=True)

        tot_cap_moi = tot_cap_moi_pm = tot_tien = tot_tien_pm = 0.0
        html_rows = []
        for i, r in day_df.iterrows():
            d        = r["Ngày phát sinh"]
            prod     = r["PROD_CODE"]
            cap_moi  = r["cap_moi"]
            tien     = r["tien"]
            cap_moi_pm = _lk(d, prod, "cap_moi")
            tien_pm    = _lk(d, prod, "tien")

            tot_cap_moi    += cap_moi
            tot_cap_moi_pm += cap_moi_pm
            tot_tien       += tien
            tot_tien_pm    += tien_pm

            bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
            html_rows.append(
                f'<tr style="background:{bg};">'
                f'<td style="padding:4px 8px;font-weight:500;">{d.strftime("%d-%m-%Y")}</td>'
                f'<td style="padding:4px 8px;">{_prod_label(prod)}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(cap_moi, cap_moi_pm)}{int(cap_moi):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#888;">{int(cap_moi_pm):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(tien, tien_pm)}{tien:,.0f}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#888;">{tien_pm:,.0f}</td>'
                f'</tr>'
            )

        total_row = (
            f'<tr style="background:#2C4C7B;color:white;font-weight:600;">'
            f'<td style="padding:5px 8px;" colspan="2">Tổng</td>'
            f'<td style="padding:5px 8px;text-align:right;">{int(tot_cap_moi):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;opacity:0.75;">{int(tot_cap_moi_pm):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{tot_tien:,.0f}</td>'
            f'<td style="padding:5px 8px;text-align:right;opacity:0.75;">{tot_tien_pm:,.0f}</td>'
            f'</tr>'
        )

        _HEADERS = [
            ("Ngày",                       "left",  "14%"),
            ("Sản phẩm",                   "left",  "22%"),
            ("Đơn cấp mới",                "right", "16%"),
            ("Đơn cùng ngày tháng trước",  "right", "16%"),
            ("Tiền thực thu",              "right", "16%"),
            ("Tiền TT tháng trước",        "right", "16%"),
        ]
        col_defs = "".join(f'<col style="width:{w};">' for _, _, w in _HEADERS)
        header_html = "".join(
            f'<th style="padding:6px 8px;text-align:{align};white-space:nowrap;">{h}</th>'
            for h, align, _ in _HEADERS
        )
        st.markdown(
            f'<div style="overflow-x:auto;margin-top:4px;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:0.75rem;table-layout:fixed;">'
            f'<colgroup>{col_defs}</colgroup>'
            f'<thead><tr style="background:#2C4C7B;color:white;">{header_html}</tr></thead>'
            f'<tbody>{"".join(html_rows)}</tbody>'
            f'<tfoot>{total_row}</tfoot>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="margin-bottom:32px;"></div>', unsafe_allow_html=True)
