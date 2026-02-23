import os
import streamlit as st
import duckdb
import pandas as pd
import altair as alt
from dotenv import load_dotenv

load_dotenv()


_NUMERIC_COLS = [
    "Tiền thực thu",
    "Số đơn cấp mới",
    "Số đơn cấp tái tục",
    "Số đơn có hiệu lực",
    "Số đơn tạm ngưng",
    "Số đơn hủy webview",
]


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


def _chart_title(text: str) -> None:
    """st.subheader replacement at 70% of default subheader size (~1.05 rem)."""
    st.markdown(
        f'<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);'
        f'margin:0 0 0.28rem 0;line-height:1.3;">{text}</p>',
        unsafe_allow_html=True,
    )


def _fmt_currency(value: float) -> str:
    billions = value / 1_000_000_000
    if billions >= 1:
        return f"{billions:,.2f} tỷ"
    millions = value / 1_000_000
    return f"{millions:,.1f} tr"


def render_overview_page():
    st.markdown(
        '<style>section[data-testid="stMain"]{zoom:1;}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;white-space:nowrap;margin-bottom:0.5rem;">'
        'BÁO CÁO TỔNG QUAN BẢO HIỂM VBI QUA KÊNH IPAY</h1>',
        unsafe_allow_html=True,
    )

    try:
        full_df = _load_data()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    # ── Filters ──────────────────────────────────────────────────────────────
    all_years = sorted(full_df["Năm"].dropna().unique().astype(int).tolist(), reverse=True)
    selected_years = st.multiselect(
        "Năm",
        options=all_years,
        default=all_years[:1],
        placeholder="Chọn năm...",
    )
    df = full_df[full_df["Năm"].isin(selected_years)] if selected_years else full_df

    # ── Compute KPIs ─────────────────────────────────────────────────────────
    tong_tien = df["Tiền thực thu"].sum()
    tong_cap_moi = int(df["Số đơn cấp mới"].sum())
    tong_tai_tuc = int(df["Số đơn cấp tái tục"].sum())

    sorted_dates = sorted(df["Ngày phát sinh"].unique())
    last_date = sorted_dates[-2]
    prev_date = sorted_dates[-3] if len(sorted_dates) >= 2 else None

    last_df = df[df["Ngày phát sinh"] == last_date]
    prev_df = df[df["Ngày phát sinh"] == prev_date] if prev_date is not None else None

    kh_hien_huu = int(last_df["Số đơn có hiệu lực"].sum())

    tong_huy = df["Số đơn hủy webview"].sum()
    tong_cap_tai_tuc = tong_cap_moi + tong_tai_tuc
    ty_le_huy = tong_huy / tong_cap_tai_tuc if tong_cap_tai_tuc > 0 else 0

    # ── YoY comparison (cùng kỳ năm trước) ───────────────────────────────────
    current_year = int(last_date.year)
    prev_year    = current_year - 1
    try:
        yoy_cutoff = last_date.replace(year=prev_year)
    except ValueError:                          # leap-day guard
        yoy_cutoff = last_date.replace(year=prev_year, day=28)

    yoy_df = full_df[
        (full_df["Năm"] == prev_year) &
        (full_df["Ngày phát sinh"] <= yoy_cutoff)
    ]
    yoy_tien    = yoy_df["Tiền thực thu"].sum()
    yoy_cap_moi = int(yoy_df["Số đơn cấp mới"].sum())
    yoy_tai_tuc = int(yoy_df["Số đơn cấp tái tục"].sum())

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

    # ── Shared constants (needed by both delta and chart sections) ───────────
    _NAMED_PRODUCTS = {"MIX_01", "VTB_HOMESAVING", "TAPCARE", "ISAFE_CYBER"}

    # ── Deltas — giá trị tuyệt đối của last_date (báo cáo chậm 1 ngày) ───────
    delta_tien    = last_df["Tiền thực thu"].sum()
    delta_cap_moi = int(last_df["Số đơn cấp mới"].sum())
    delta_tai_tuc = int(last_df["Số đơn cấp tái tục"].sum())

    # Stock metric: delta = change in Số đơn có hiệu lực vs prev day
    kh_prev      = int(prev_df["Số đơn có hiệu lực"].sum()) if prev_df is not None else kh_hien_huu
    delta_kh     = kh_hien_huu - kh_prev

    # Rate metric: delta = last_date daily rate vs prev_date daily rate
    if prev_df is not None:
        prev_denom  = int(prev_df["Số đơn cấp mới"].sum()) + int(prev_df["Số đơn cấp tái tục"].sum())
        prev_ty_le  = prev_df["Số đơn hủy webview"].sum() / prev_denom if prev_denom > 0 else 0
        last_denom  = int(last_df["Số đơn cấp mới"].sum()) + int(last_df["Số đơn cấp tái tục"].sum())
        last_ty_le  = last_df["Số đơn hủy webview"].sum() / last_denom if last_denom > 0 else 0
        delta_ty_le = last_ty_le - prev_ty_le
    else:
        delta_ty_le = 0.0

    # ── Product breakdown for scorecard tooltips ──────────────────────────────
    def _grp(s: pd.Series) -> pd.Series:
        return s.where(s.isin(_NAMED_PRODUCTS), other="Sản phẩm khác")

    last_grp     = last_df.assign(PROD_CODE=lambda x: _grp(x["PROD_CODE"]))
    tien_by_prod = last_grp.groupby("PROD_CODE")["Tiền thực thu"].sum().sort_values(ascending=False)
    cap_by_prod  = last_grp.groupby("PROD_CODE")["Số đơn cấp mới"].sum().sort_values(ascending=False)
    tai_by_prod  = last_grp.groupby("PROD_CODE")["Số đơn cấp tái tục"].sum().sort_values(ascending=False)
    huy_by_prod  = last_grp.groupby("PROD_CODE")["Số đơn hủy webview"].sum().sort_values(ascending=False)

    last_kh_prod = last_grp.groupby("PROD_CODE")["Số đơn có hiệu lực"].sum()
    if prev_df is not None:
        prev_kh_prod  = prev_df.assign(PROD_CODE=lambda x: _grp(x["PROD_CODE"])).groupby("PROD_CODE")["Số đơn có hiệu lực"].sum()
        kh_delta_prod = last_kh_prod.subtract(prev_kh_prod, fill_value=0).sort_values(ascending=False)
    else:
        kh_delta_prod = last_kh_prod.sort_values(ascending=False)

    # ── Scorecards ───────────────────────────────────────────────────────────
    def _kpi_card(
        label, value, delta_str, delta_color,
        accent_color="#2C4C7B", subtitle="", yoy_html="", progress_pct=None,
    ):
        # Sidebar: chỉ hiện khi có KPI target (progress_pct)
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
            sidebar   = ""
            pad_left  = "14px"
        # Dùng list + join để không tạo blank line — blank line phá HTML block trong markdown
        parts = [
            f'<div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;'
            f'padding:14px 14px 11px {pad_left};box-shadow:0 2px 8px rgba(0,0,0,0.06);'
            f'display:flex;gap:8px;align-items:stretch;min-height:126px;">',
            sidebar,
            f'<div style="flex:1;min-width:0;">',
            f'<div style="font-size:0.55rem;font-weight:600;color:#555;text-transform:uppercase;'
            f'letter-spacing:0.04em;margin-bottom:4px;">{label}</div>',
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

    _prev_str = pd.Timestamp(prev_date).strftime("%d-%m-%Y") if prev_date is not None else "N/A"
    st.markdown(
        f'<p style="font-size:0.78rem;color:#888;margin-bottom:4px">'
        f'↕ Mũi tên xanh/đỏ: so với ngày trước đó ({_prev_str})</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)

    with cols[0]:
        _pct = min(tong_tien / 320_000_000_000, 1.0)
        _ds  = "+" if delta_tien >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng tiền thực thu",
            value=_fmt_currency(tong_tien),
            delta_str=f"{_ds}{_fmt_currency(delta_tien)}",
            delta_color="#2e7d32",
            accent_color="#2C4C7B",
            subtitle=f"/ 320 tỷ &nbsp;·&nbsp; <strong style='color:#2C4C7B;'>{_pct:.1%}</strong>",
            yoy_html=_yoy_caption(tong_tien, yoy_tien, _fmt_currency),
            progress_pct=_pct,
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

    with cols[2]:
        st.markdown(_kpi_card(
            label="Tổng số đơn tái tục",
            value=f"{tong_tai_tuc:,}",
            delta_str=f"+{delta_tai_tuc:,}",
            delta_color="#2e7d32",
            accent_color="#2C7B6F",
            yoy_html=_yoy_caption(tong_tai_tuc, yoy_tai_tuc, lambda v: f"{int(v):,}"),
        ), unsafe_allow_html=True)

    with cols[3]:
        _kh_color = "#2e7d32" if delta_kh >= 0 else "#c62828"
        _kh_sign  = "+" if delta_kh >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng số KH hiện hữu",
            value=f"{kh_hien_huu:,}",
            delta_str=f"{_kh_sign}{delta_kh:,}",
            delta_color=_kh_color,
            accent_color="#6b3fa0",
        ), unsafe_allow_html=True)

    with cols[4]:
        _huy_color = "#c62828" if delta_ty_le > 0 else "#2e7d32"
        st.markdown(_kpi_card(
            label="Tỷ lệ hủy chủ động",
            value=f"{ty_le_huy:.1%}",
            delta_str=f"{delta_ty_le:+.2%}",
            delta_color=_huy_color,
            accent_color="#d71149",
        ), unsafe_allow_html=True)

    # ── Expander: delta chi tiết theo sản phẩm ───────────────────────────────
    st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
    _exp_date = pd.Timestamp(last_date).strftime("%d/%m/%Y")
    with st.expander(f"↕ Chi tiết thay đổi theo sản phẩm — ngày {_exp_date}"):
        _all_prods = sorted({
            *tien_by_prod.index, *cap_by_prod.index,
            *tai_by_prod.index,  *kh_delta_prod.index,
            *huy_by_prod.index,
        })
        _rows = []
        for _prod in _all_prods:
            _t   = float(tien_by_prod.get(_prod, 0))
            _cap = int(cap_by_prod.get(_prod, 0))
            _tai = int(tai_by_prod.get(_prod, 0))
            _kh  = int(kh_delta_prod.get(_prod, 0))
            _huy = int(huy_by_prod.get(_prod, 0))
            def _pfx(v, fmt): return f"+{fmt(v)}" if v >= 0 else fmt(v)
            _rows.append({
                "Sản phẩm":        _prod,
                "Δ Tiền thực thu": _pfx(_t,   _fmt_currency),
                "Δ Cấp mới":       _pfx(_cap, lambda v: f"{int(v):,}"),
                "Δ Tái tục":       _pfx(_tai, lambda v: f"{int(v):,}"),
                "Δ KH hiện hữu":   _pfx(_kh,  lambda v: f"{int(v):,}"),
                "Δ Hủy chủ động":   _pfx(_huy, lambda v: f"{int(v):,}"),
            })
        _detail_df = pd.DataFrame(_rows).set_index("Sản phẩm")
        _green = ("Δ Tiền thực thu", "Δ Cấp mới", "Δ Tái tục", "Δ KH hiện hữu")
        _red   = ("Δ Hủy chủ động",)
        _styled = (
            _detail_df.style
            .map(lambda _: "color:#2e7d32;font-weight:600", subset=_green)
            .map(lambda _: "color:#d71149;font-weight:600", subset=_red)
        )
        st.dataframe(_styled, width='stretch')

    # ── Shared helpers ────────────────────────────────────────────────────────
    _NAMED_PRODUCTS = {"MIX_01", "VTB_HOMESAVING", "TAPCARE", "ISAFE_CYBER"}

    def _fmt_vnd(v: float) -> str:
        if v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f} tỷ"
        return f"{v / 1_000_000:.2f} triệu"

    def _group_prod(series: pd.Series) -> pd.Series:
        return series.where(series.isin(_NAMED_PRODUCTS), other="Sản phẩm khác")

    # ── KH hiện hữu — pie chart mỗi sản phẩm ────────────────────────────────
    kh_prod_df = (
        df[df["Ngày phát sinh"] == last_date]
        .assign(PROD_CODE=lambda x: _group_prod(x["PROD_CODE"]))
        .groupby("PROD_CODE", as_index=False)[["Số đơn có hiệu lực", "Số đơn tạm ngưng"]]
        .sum()
    )
    kh_prod_df = (
        kh_prod_df[kh_prod_df["PROD_CODE"].isin(_NAMED_PRODUCTS)]
        .copy()
    )
    kh_prod_df["total"] = kh_prod_df["Số đơn có hiệu lực"] + kh_prod_df["Số đơn tạm ngưng"]
    kh_prod_df = kh_prod_df.sort_values("total", ascending=False).reset_index(drop=True)

    st.markdown('<div style="margin-top:32px;"></div>', unsafe_allow_html=True)
    _chart_title("Số khách hàng hiện hữu theo sản phẩm")

    _legend_html = (
        '<div style="display:flex;gap:14px;margin-bottom:6px;font-size:0.57rem;">'
        '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        'background:#6b3fa0;margin-right:4px;vertical-align:middle;"></span>Có hiệu lực</span>'
        '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        'background:#b39ddb;margin-right:4px;vertical-align:middle;"></span>Tạm ngưng</span>'
        '</div>'
    )
    st.markdown(_legend_html, unsafe_allow_html=True)

    kh_cols = st.columns(len(kh_prod_df))
    for col, (_, row) in zip(kh_cols, kh_prod_df.iterrows()):
        prod  = row["PROD_CODE"]
        total = int(row["total"])
        pie_df = pd.DataFrame({
            "Loại":   ["Có hiệu lực", "Tạm ngưng"],
            "Số đơn": [row["Số đơn có hiệu lực"], row["Số đơn tạm ngưng"]],
        })
        pie = (
            alt.Chart(pie_df)
            .mark_arc(innerRadius=42)
            .encode(
                theta=alt.Theta("Số đơn:Q"),
                color=alt.Color(
                    "Loại:N",
                    scale=alt.Scale(
                        domain=["Có hiệu lực", "Tạm ngưng"],
                        range=["#6b3fa0", "#b39ddb"],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("Loại:N",   title="Loại"),
                    alt.Tooltip("Số đơn:Q", title="Số đơn", format=",.0f"),
                ],
            )
            .properties(title=prod, height=185)
        )
        total_str  = f"{total/1e6:.3f} triệu" if total >= 1_000_000 else f"{total:,}"
        hieu_luc   = row["Số đơn có hiệu lực"]
        pct_hieu   = hieu_luc / total if total > 0 else 0
        with col:
            st.altair_chart(pie, width='stretch')
            st.markdown(
                f'<div style="text-align:center;font-size:0.60rem;color:#444;margin-top:-6px;">'
                f'Tổng KH hiện hữu<br>'
                f'<strong style="font-size:0.70rem;color:#1a1a2e;">{total_str}</strong>'
                f'</div>'
                f'<div style="text-align:center;font-size:0.57rem;color:#6b3fa0;margin-top:3px;">'
                f'Có hiệu lực: <strong>{pct_hieu:.1%}</strong>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="margin-bottom:32px;"></div>', unsafe_allow_html=True)

    # ── Row 1: revenue by product | revenue by month ─────────────────────────
    col_rev, col_trend = st.columns(2)

    # ── Chart 1: Tiền thực thu theo sản phẩm ─────────────────────────────────
    with col_rev:
        _chart_title("Tiền thực thu theo sản phẩm")
        selected_months = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="rev_prod_months",
        )
        df_prod = (
            df[df["Ngày phát sinh"].dt.month.isin(selected_months)]
            if selected_months else df
        )
        chart_df = (
            df_prod.assign(
                PROD_CODE=lambda x: x["PROD_CODE"].where(
                    x["PROD_CODE"].isin(_NAMED_PRODUCTS), other="Sản phẩm khác"
                )
            )
            .groupby(["PROD_CODE", "Năm"], as_index=False)["Tiền thực thu"]
            .sum()
            .assign(Năm=lambda x: x["Năm"].astype(str))
        )
        chart_df["label"] = chart_df["Tiền thực thu"].apply(_fmt_vnd)
        prod_order = (
            chart_df.groupby("PROD_CODE")["Tiền thực thu"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        bars = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("PROD_CODE:N", title=None, sort=prod_order, axis=alt.Axis(labelAngle=0, labelLimit=0)),
                y=alt.Y("Tiền thực thu:Q", title=None, axis=None),
                color=alt.Color("Năm:N", title="Năm", legend=None, scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Mã sản phẩm"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("label:N", title="Tiền thực thu"),
                ],
            )
        )
        labels = (
            alt.Chart(chart_df)
            .mark_text(dy=-6, fontSize=12, fontWeight="normal")
            .encode(
                x=alt.X("PROD_CODE:N", sort=prod_order),
                y=alt.Y("Tiền thực thu:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((bars + labels).properties(height=280), width='stretch')

    # ── Chart 2: Tiền thực thu theo tháng (bar) ───────────────────────────────
    with col_trend:
        _chart_title("Tiền thực thu theo tháng")
        prod_options = sorted(_NAMED_PRODUCTS) + ["Sản phẩm khác"]
        selected_trend_prods = st.multiselect(
            "Lọc sản phẩm",
            options=prod_options,
            default=[],
            placeholder="Tất cả sản phẩm",
            key="rev_month_prods",
        )
        if selected_trend_prods:
            mask = _group_prod(df["PROD_CODE"]).isin(selected_trend_prods)
            df_trend = df[mask]
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
                color=alt.Color("Năm:N", title=None, legend=None, scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
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
            .mark_text(dy=-6, fontSize=12, fontWeight="normal")
            .encode(
                x=alt.X("Tháng:O"),
                y=alt.Y("Tiền thực thu:Q"),
                color=alt.Color("Năm:N", scale=alt.Scale(range=["#2C4C7B", "#6B9ED4"])),
                xOffset=alt.XOffset("Năm:N"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((m_bars + m_labels).properties(height=280), width='stretch')

    # ── Row 2: Tỷ lệ hủy | Cấp mới + hủy theo sản phẩm | Cấp mới + hủy theo tháng ──
    _CAP_COLORS = ["#6A415E", "#B07A9E"]
    _HUY_COLORS = ["#d71149", "#FF6B8A"]
    _LOAI_RAW_MAP = {"Số đơn cấp mới": "Cấp mới", "Số đơn hủy webview": "Hủy"}

    def _build_nhom_scale(years: list) -> tuple:
        domain = [f"Cấp mới {y}" for y in years] + [f"Hủy {y}" for y in years]
        rng    = [_CAP_COLORS[i % 2] for i in range(len(years))] + \
                 [_HUY_COLORS[i % 2] for i in range(len(years))]
        return domain, rng

    col_huy, col_new_prod, col_new_month = st.columns(3)

    # ── Chart: Tỷ lệ hủy chủ động theo sản phẩm ─────────────────────────────
    with col_huy:
        _chart_title("Tỷ lệ hủy chủ động theo sản phẩm")
        selected_months_huy = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="huy_prod_months",
        )
        df_huy = (
            df[df["Ngày phát sinh"].dt.month.isin(selected_months_huy)]
            if selected_months_huy else df
        )
        huy_prod_df = (
            df_huy.assign(PROD_CODE=lambda x: _group_prod(x["PROD_CODE"]))
            .groupby("PROD_CODE", as_index=False)
            .agg(
                huy=("Số đơn hủy webview", "sum"),
                cap=("Số đơn cấp mới", "sum"),
                tai_tuc=("Số đơn cấp tái tục", "sum"),
            )
        )
        huy_prod_df["Tỷ lệ hủy"] = huy_prod_df["huy"] / (huy_prod_df["cap"] + huy_prod_df["tai_tuc"]).replace(0, float("nan"))
        huy_prod_df = huy_prod_df[huy_prod_df["PROD_CODE"] != "Sản phẩm khác"]
        huy_prod_df = huy_prod_df.sort_values("Tỷ lệ hủy", ascending=False)
        huy_prod_df["label"] = huy_prod_df["Tỷ lệ hủy"].apply(lambda v: f"{v:.2%}")
        huy_order = huy_prod_df["PROD_CODE"].tolist()
        huy_bars = (
            alt.Chart(huy_prod_df)
            .mark_bar(color="#d71149")
            .encode(
                x=alt.X("PROD_CODE:N", sort=huy_order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=0)),
                y=alt.Y("Tỷ lệ hủy:Q", title=None, axis=None),
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Sản phẩm"),
                    alt.Tooltip("label:N", title="Tỷ lệ hủy"),
                ],
            )
        )
        huy_labels = (
            alt.Chart(huy_prod_df)
            .mark_text(dy=-8, fontSize=12, fontWeight="normal")
            .encode(
                x=alt.X("PROD_CODE:N", sort=huy_order),
                y=alt.Y("Tỷ lệ hủy:Q"),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart(
            (huy_bars + huy_labels).properties(height=266),
            width='stretch',
        )

    # ── Chart: Số đơn cấp mới và số đơn hủy theo sản phẩm ───────────────────
    with col_new_prod:
        _chart_title("Số đơn cấp mới và số đơn hủy theo sản phẩm")
        selected_months_new = st.multiselect(
            "Lọc tháng",
            options=list(range(1, 13)),
            default=[],
            placeholder="Tất cả tháng",
            key="new_prod_months",
        )
        df_new_prod = (
            df[df["Ngày phát sinh"].dt.month.isin(selected_months_new)]
            if selected_months_new else df
        )
        new_prod_agg = (
            df_new_prod.assign(
                PROD_CODE=lambda x: x["PROD_CODE"].where(
                    x["PROD_CODE"].isin(_NAMED_PRODUCTS), other="Sản phẩm khác"
                )
            )
            .groupby(["PROD_CODE", "Năm"], as_index=False)[["Số đơn cấp mới", "Số đơn hủy webview"]]
            .sum()
            .assign(Năm=lambda x: x["Năm"].astype(str))
        )
        new_prod_order = (
            new_prod_agg.groupby("PROD_CODE")["Số đơn cấp mới"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        years_np = sorted(new_prod_agg["Năm"].unique().tolist())
        nhom_domain_np, nhom_range_np = _build_nhom_scale(years_np)
        np_melted = (
            new_prod_agg
            .melt(
                id_vars=["PROD_CODE", "Năm"],
                value_vars=["Số đơn cấp mới", "Số đơn hủy webview"],
                var_name="Loại_raw", value_name="Số đơn",
            )
            .assign(Loại=lambda x: x["Loại_raw"].map(_LOAI_RAW_MAP))
        )
        np_melted["Nhóm"]  = np_melted["Loại"] + " " + np_melted["Năm"]
        np_melted["label"] = np_melted["Số đơn"].apply(lambda v: f"{int(v):,}")
        _np_color = alt.Color(
            "Nhóm:N",
            legend=None,
            scale=alt.Scale(domain=nhom_domain_np, range=nhom_range_np),
        )
        np_bars = (
            alt.Chart(np_melted)
            .mark_bar()
            .encode(
                x=alt.X("PROD_CODE:N", title=None, sort=new_prod_order, axis=alt.Axis(labelAngle=0, labelFontSize=11, labelLimit=0)),
                y=alt.Y("Số đơn:Q", title=None, axis=None),
                xOffset=alt.XOffset("Nhóm:N", sort=nhom_domain_np),
                color=_np_color,
                tooltip=[
                    alt.Tooltip("PROD_CODE:N", title="Mã sản phẩm"),
                    alt.Tooltip("Loại:N", title="Loại"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("Số đơn:Q", title="Số đơn", format=",.0f"),
                ],
            )
        )
        np_labels = (
            alt.Chart(np_melted[np_melted["Số đơn"] > 0])
            .mark_text(dy=-6, fontSize=11, fontWeight="normal")
            .encode(
                x=alt.X("PROD_CODE:N", sort=new_prod_order),
                y=alt.Y("Số đơn:Q"),
                xOffset=alt.XOffset("Nhóm:N", sort=nhom_domain_np),
                color=alt.Color("Nhóm:N", scale=alt.Scale(domain=nhom_domain_np, range=nhom_range_np)),
                text=alt.Text("label:N"),
            )
        )
        st.altair_chart((np_bars + np_labels).properties(height=266), width='stretch')

    # ── Chart: Số đơn cấp mới và số đơn hủy theo tháng (no labels) ──────────
    with col_new_month:
        _chart_title("Số đơn cấp mới và số đơn hủy theo tháng")
        selected_new_prods = st.multiselect(
            "Lọc sản phẩm",
            options=sorted(_NAMED_PRODUCTS) + ["Sản phẩm khác"],
            default=[],
            placeholder="Tất cả sản phẩm",
            key="new_month_prods",
        )
        if selected_new_prods:
            mask_new = _group_prod(df["PROD_CODE"]).isin(selected_new_prods)
            df_new_month = df[mask_new]
        else:
            df_new_month = df
        new_monthly_agg = (
            df_new_month.assign(
                Tháng=df_new_month["Ngày phát sinh"].dt.month,
                Năm=df_new_month["Năm"].astype(str),
            )
            .groupby(["Năm", "Tháng"], as_index=False)[["Số đơn cấp mới", "Số đơn hủy webview"]]
            .sum()
        )
        year_list_new = new_monthly_agg["Năm"].unique().tolist()
        full_grid_new = pd.DataFrame(
            [(y, m) for y in year_list_new for m in range(1, 13)],
            columns=["Năm", "Tháng"],
        )
        new_monthly_agg = full_grid_new.merge(new_monthly_agg, on=["Năm", "Tháng"], how="left").fillna(0)
        years_nm = sorted(new_monthly_agg["Năm"].unique().tolist())
        nhom_domain_nm, nhom_range_nm = _build_nhom_scale(years_nm)
        nm_melted = (
            new_monthly_agg
            .melt(
                id_vars=["Năm", "Tháng"],
                value_vars=["Số đơn cấp mới", "Số đơn hủy webview"],
                var_name="Loại_raw", value_name="Số đơn",
            )
            .assign(Loại=lambda x: x["Loại_raw"].map(_LOAI_RAW_MAP))
        )
        nm_melted["Nhóm"] = nm_melted["Loại"] + " " + nm_melted["Năm"]
        _nm_color = alt.Color(
            "Nhóm:N",
            legend=None,
            scale=alt.Scale(domain=nhom_domain_nm, range=nhom_range_nm),
        )
        nm_bars = (
            alt.Chart(nm_melted)
            .mark_bar()
            .encode(
                x=alt.X("Tháng:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Số đơn:Q", title=None, axis=None),
                xOffset=alt.XOffset("Nhóm:N", sort=nhom_domain_nm),
                color=_nm_color,
                tooltip=[
                    alt.Tooltip("Tháng:O", title="Tháng"),
                    alt.Tooltip("Loại:N", title="Loại"),
                    alt.Tooltip("Năm:N", title="Năm"),
                    alt.Tooltip("Số đơn:Q", title="Số đơn", format=",.0f"),
                ],
            )
        )
        st.altair_chart(nm_bars.properties(height=266), width='stretch')
