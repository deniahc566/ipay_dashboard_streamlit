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
    "Số đơn tái tục dự kiến",
    "Số đơn có hiệu lực",
    "Số đơn tạm ngưng",
    "Số đơn hủy webview",
]

_PROD_CODE = "TAPCARE"
_PHI_DON = 6000


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
    accent_color="#2C4C7B", yoy_html="", tooltip="",
):
    _label_html = label
    if tooltip:
        _label_html += (
            f'&nbsp;<abbr title="{tooltip}" '
            f'style="font-size:0.65rem;color:#aaa;cursor:help;text-decoration:none;">ℹ</abbr>'
        )
    parts = [
        f'<div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;'
        f'padding:14px 14px 11px 10px;box-shadow:0 2px 8px rgba(0,0,0,0.06);'
        f'display:flex;gap:8px;align-items:stretch;min-height:126px;">',
        f'<div style="width:4px;border-radius:3px;background:{accent_color};flex-shrink:0;"></div>',
        f'<div style="flex:1;min-width:0;">',
        f'<div style="font-size:0.55rem;font-weight:600;color:#555;text-transform:uppercase;'
        f'letter-spacing:0.04em;margin-bottom:4px;">{_label_html}</div>',
        f'<div style="font-size:1.26rem;font-weight:700;color:#1a1a2e;line-height:1.1;">{value}</div>',
        f'<div style="margin-top:3px;font-size:0.57rem;font-weight:600;color:{delta_color};">{delta_str}</div>',
    ]
    if yoy_html:
        parts.append(f'<div style="margin-top:3px;">{yoy_html}</div>')
    parts += ['</div>', '</div>']
    return "".join(parts)


def render_tapcare_page():
    st.markdown(
        '<style>section[data-testid="stMain"]{zoom:1;}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;white-space:nowrap;margin-bottom:0.5rem;">'
        'BÁO CÁO CHI TIẾT SẢN PHẨM TAPCARE</h1>',
        unsafe_allow_html=True,
    )

    try:
        full_df = _load_data()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    prod_full_df = full_df[full_df["PROD_CODE"] == _PROD_CODE].copy()

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

    # ── Guard ─────────────────────────────────────────────────────────────────
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
    tong_tai_tuc = int(df["Số đơn cấp tái tục"].sum())
    tong_huy     = df["Số đơn hủy webview"].sum()

    tong_tai_tuc_dk = df["Số đơn tái tục dự kiến"].sum()

    kh_hien_huu   = int(last_df["Số đơn có hiệu lực"].sum())
    ty_le_huy     = tong_huy / (tong_cap_moi + tong_tai_tuc) if (tong_cap_moi + tong_tai_tuc) > 0 else 0
    ty_le_tai_tuc = tong_tai_tuc / tong_tai_tuc_dk if tong_tai_tuc_dk > 0 else 0
    tong_tang_truong = int(tong_cap_moi - tong_huy - tong_tai_tuc_dk + tong_tai_tuc)

    # ── Deltas vs previous day ────────────────────────────────────────────────
    delta_tien       = last_df["Tiền thực thu"].sum()
    delta_tang_truong = int(
        last_df["Số đơn cấp mới"].sum()
        - last_df["Số đơn hủy webview"].sum()
        - last_df["Số đơn tái tục dự kiến"].sum()
        + last_df["Số đơn cấp tái tục"].sum()
    )

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
    yoy_tien         = yoy_df["Tiền thực thu"].sum()
    yoy_tang_truong  = int(
        yoy_df["Số đơn cấp mới"].sum()
        - yoy_df["Số đơn hủy webview"].sum()
        - yoy_df["Số đơn tái tục dự kiến"].sum()
        + yoy_df["Số đơn cấp tái tục"].sum()
    )
    yoy_tai_tuc_dk   = yoy_df["Số đơn tái tục dự kiến"].sum()
    yoy_ty_le_tai_tuc = (
        yoy_df["Số đơn cấp tái tục"].sum() / yoy_tai_tuc_dk
        if yoy_tai_tuc_dk > 0 else 0
    )

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

    # ── Scorecards ────────────────────────────────────────────────────────────
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
            accent_color="#1B6B3A",
            yoy_html=_yoy_caption(tong_tien, yoy_tien, _fmt_currency),
        ), unsafe_allow_html=True)

    with cols[1]:
        _tg_color = "#2e7d32" if delta_tang_truong >= 0 else "#c62828"
        _tg_sign  = "+" if delta_tang_truong >= 0 else ""
        st.markdown(_kpi_card(
            label="Số KH tăng trưởng",
            value=f"{tong_tang_truong:,}",
            delta_str=f"{_tg_sign}{delta_tang_truong:,}",
            delta_color=_tg_color,
            accent_color="#145228",
            yoy_html=_yoy_caption(tong_tang_truong, yoy_tang_truong, lambda v: f"{int(v):,}"),
            tooltip="Cấp mới − Hủy − Tái tục dự kiến + Tái tục thực tế",
        ), unsafe_allow_html=True)

    with cols[2]:
        _kh_color = "#2e7d32" if delta_kh >= 0 else "#c62828"
        _kh_sign  = "+" if delta_kh >= 0 else ""
        st.markdown(_kpi_card(
            label="Tổng số KH hiện hữu",
            value=f"{kh_hien_huu:,}",
            delta_str=f"{_kh_sign}{delta_kh:,}",
            delta_color=_kh_color,
            accent_color="#2E8B57",
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

    # ── Row 2: Charts ─────────────────────────────────────────────────────────
    st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)

    _daily_all = (
        prod_full_df.groupby("Ngày phát sinh")
        .agg(
            tien=("Tiền thực thu", "sum"),
            cap_moi=("Số đơn cấp mới", "sum"),
            tai_tuc_dk=("Số đơn tái tục dự kiến", "sum"),
            huy=("Số đơn hủy webview", "sum"),
        )
        .sort_index()
    )
    if not _daily_all.empty:
        _daily_all = _daily_all.reindex(
            pd.date_range(_daily_all.index.min(), _daily_all.index.max(), freq="D"),
            fill_value=0.0,
        )
        _daily_all["tien_dk"] = (
            (_daily_all["cap_moi"].shift(30).fillna(0)
             - _daily_all["huy"].shift(30).fillna(0)
             + _daily_all["tai_tuc_dk"] * 0.9
             - _daily_all["tai_tuc_dk"].shift(-5).fillna(0))
            * _PHI_DON * 0.95
            + _daily_all["tien"].shift(30).fillna(0) * 0.95
        )
        _yr_filter = selected_years if selected_years else all_years
        _daily_chart = _daily_all[_daily_all.index.year.isin(_yr_filter)].copy()
        _daily_chart["Tháng"] = _daily_chart.index.to_period("M").astype(str)
        _monthly = (
            _daily_chart.groupby("Tháng")[["tien", "tien_dk"]]
            .sum()
            .reset_index()
            .rename(columns={"tien": "Thực thu", "tien_dk": "Dự kiến"})
        )
        _melted = _monthly.melt(
            id_vars="Tháng",
            value_vars=["Thực thu", "Dự kiến"],
            var_name="Loại",
            value_name="Tiền (VND)",
        )
    else:
        _melted = pd.DataFrame(columns=["Tháng", "Loại", "Tiền (VND)"])

    _kh_active    = float(last_df["Số đơn có hiệu lực"].sum())
    _kh_tam_nguong = float(last_df["Số đơn tạm ngưng"].sum())
    _pie_df = pd.DataFrame({
        "Loại KH": ["Có hiệu lực", "Tạm ngưng"],
        "Số đơn": [_kh_active, _kh_tam_nguong],
    })

    chart_cols = st.columns([1, 2])

    with chart_cols[0]:
        st.markdown(
            '<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);margin:0 0 0.28rem 0;">'
            'KH hiện hữu</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="display:flex;gap:14px;margin-bottom:6px;font-size:0.57rem;">'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            'background:#2E8B57;margin-right:4px;vertical-align:middle;"></span>Có hiệu lực</span>'
            '<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            'background:#90EE90;margin-right:4px;vertical-align:middle;"></span>Tạm ngưng</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        _pie = (
            alt.Chart(_pie_df)
            .mark_arc(innerRadius=42)
            .encode(
                theta=alt.Theta("Số đơn:Q"),
                color=alt.Color(
                    "Loại KH:N",
                    scale=alt.Scale(
                        domain=["Có hiệu lực", "Tạm ngưng"],
                        range=["#2E8B57", "#90EE90"],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("Loại KH:N", title="Loại"),
                    alt.Tooltip("Số đơn:Q", title="Số đơn", format=",.0f"),
                ],
            )
            .properties(height=185)
        )
        st.altair_chart(_pie, width='stretch')
        _kh_total = _kh_active + _kh_tam_nguong
        _kh_total_str = (
            f"{_kh_total / 1e6:.3f} triệu" if _kh_total >= 1_000_000 else f"{int(_kh_total):,}"
        )
        _pct_hieu_luc = _kh_active / _kh_total if _kh_total > 0 else 0
        st.markdown(
            f'<div style="text-align:center;font-size:0.60rem;color:#444;margin-top:-6px;">'
            f'Tổng KH hiện hữu<br>'
            f'<strong style="font-size:0.70rem;color:#1a1a2e;">{_kh_total_str}</strong>'
            f'</div>'
            f'<div style="text-align:center;font-size:0.57rem;color:#2E8B57;margin-top:3px;">'
            f'Có hiệu lực: <strong>{_pct_hieu_luc:.1%}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with chart_cols[1]:
        st.markdown(
            '<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);margin:0 0 0.28rem 0;">'
            'Tiền thực thu vs dự kiến theo tháng</p>',
            unsafe_allow_html=True,
        )
        if not _melted.empty:
            _melted["label"] = _melted["Tiền (VND)"].apply(_fmt_currency)
            _bar_order = ["Thực thu", "Dự kiến"]
            _bars = (
                alt.Chart(_melted)
                .mark_bar()
                .encode(
                    x=alt.X("Tháng:N", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Tiền (VND):Q", title=None, axis=None),
                    color=alt.Color(
                        "Loại:N",
                        scale=alt.Scale(
                            domain=_bar_order,
                            range=["#1B6B3A", "#5CB87A"],
                        ),
                        legend=None,
                    ),
                    xOffset=alt.XOffset("Loại:N", sort=_bar_order),
                    tooltip=[
                        alt.Tooltip("Tháng:N", title="Tháng"),
                        alt.Tooltip("Loại:N", title="Loại"),
                        alt.Tooltip("label:N", title="Tiền"),
                    ],
                )
            )
            _bar_labels = (
                alt.Chart(_melted[_melted["Tiền (VND)"] > 0])
                .mark_text(dy=-6, fontSize=11, fontWeight="normal")
                .encode(
                    x=alt.X("Tháng:N", sort=None),
                    y=alt.Y("Tiền (VND):Q"),
                    xOffset=alt.XOffset("Loại:N", sort=_bar_order),
                    color=alt.Color(
                        "Loại:N",
                        scale=alt.Scale(domain=_bar_order, range=["#1B6B3A", "#5CB87A"]),
                    ),
                    text=alt.Text("label:N"),
                )
            )
            st.markdown(
                '<div style="display:flex;gap:14px;margin-bottom:6px;font-size:0.57rem;">'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;'
                'background:#1B6B3A;margin-right:4px;vertical-align:middle;"></span>Thực thu</span>'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;'
                'background:#5CB87A;margin-right:4px;vertical-align:middle;"></span>Dự kiến</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.altair_chart((_bars + _bar_labels).properties(height=280), width='stretch')
        else:
            st.info("Không có dữ liệu để vẽ biểu đồ.")

    # ── Row 3: Tỷ lệ hủy & tái tục theo tháng ────────────────────────────────
    st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
    rate_cols = st.columns(2)

    with rate_cols[0]:
        st.markdown(
            '<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);margin:0 0 0.28rem 0;">'
            'Tỷ lệ hủy theo tháng</p>',
            unsafe_allow_html=True,
        )
        _monthly_huy = (
            df.assign(Tháng=df["Ngày phát sinh"].dt.to_period("M").astype(str))
            .groupby("Tháng", as_index=False)
            .agg(
                huy=("Số đơn hủy webview", "sum"),
                cap=("Số đơn cấp mới", "sum"),
                tai_tuc=("Số đơn cấp tái tục", "sum"),
            )
        )
        _monthly_huy["Tỷ lệ hủy"] = (
            _monthly_huy["huy"]
            / (_monthly_huy["cap"] + _monthly_huy["tai_tuc"]).replace(0, float("nan"))
        )
        _monthly_huy["label"] = _monthly_huy["Tỷ lệ hủy"].apply(
            lambda v: f"{v:.1%}" if pd.notna(v) else ""
        )
        if not _monthly_huy.empty:
            _huy_m_line = (
                alt.Chart(_monthly_huy)
                .mark_line(color="#d71149", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#d71149", size=60))
                .encode(
                    x=alt.X("Tháng:N", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Tỷ lệ hủy:Q", title=None, axis=None),
                    tooltip=[
                        alt.Tooltip("Tháng:N", title="Tháng"),
                        alt.Tooltip("label:N", title="Tỷ lệ hủy"),
                    ],
                )
            )
            _huy_m_labels = (
                alt.Chart(_monthly_huy[_monthly_huy["Tỷ lệ hủy"] > 0])
                .mark_text(dy=-12, fontSize=11, fontWeight="normal", color="#d71149")
                .encode(
                    x=alt.X("Tháng:N"),
                    y=alt.Y("Tỷ lệ hủy:Q"),
                    text=alt.Text("label:N"),
                )
            )
            st.altair_chart(
                (_huy_m_line + _huy_m_labels).properties(height=220),
                width='stretch',
            )
        else:
            st.info("Không có dữ liệu.")

    with rate_cols[1]:
        st.markdown(
            '<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);margin:0 0 0.28rem 0;">'
            'Tái tục thực tế vs dự kiến theo tháng</p>',
            unsafe_allow_html=True,
        )
        _monthly_tt = (
            df.assign(Tháng=df["Ngày phát sinh"].dt.to_period("M").astype(str))
            .groupby("Tháng", as_index=False)
            .agg(
                tai_tuc=("Số đơn cấp tái tục", "sum"),
                tai_tuc_dk=("Số đơn tái tục dự kiến", "sum"),
            )
        )
        _tt_order = ["Thực tế", "Dự kiến"]
        _melted_tt = _monthly_tt.melt(
            id_vars="Tháng",
            value_vars=["tai_tuc", "tai_tuc_dk"],
            var_name="Loại_raw",
            value_name="Số đơn",
        ).assign(
            Loại=lambda x: x["Loại_raw"].map({"tai_tuc": "Thực tế", "tai_tuc_dk": "Dự kiến"})
        )
        _melted_tt["label"] = _melted_tt["Số đơn"].apply(lambda v: f"{int(v):,}")
        if not _melted_tt.empty:
            st.markdown(
                '<div style="display:flex;gap:14px;margin-bottom:6px;font-size:0.57rem;">'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;'
                'background:#2C7B6F;margin-right:4px;vertical-align:middle;"></span>Thực tế</span>'
                '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;'
                'background:#6DB4AC;margin-right:4px;vertical-align:middle;"></span>Dự kiến</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            _tt_bars = (
                alt.Chart(_melted_tt)
                .mark_bar()
                .encode(
                    x=alt.X("Tháng:N", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Số đơn:Q", title=None, axis=None),
                    color=alt.Color(
                        "Loại:N",
                        scale=alt.Scale(domain=_tt_order, range=["#2C7B6F", "#6DB4AC"]),
                        legend=None,
                    ),
                    xOffset=alt.XOffset("Loại:N", sort=_tt_order),
                    tooltip=[
                        alt.Tooltip("Tháng:N", title="Tháng"),
                        alt.Tooltip("Loại:N", title="Loại"),
                        alt.Tooltip("label:N", title="Số đơn"),
                    ],
                )
            )
            _tt_labels = (
                alt.Chart(_melted_tt[_melted_tt["Số đơn"] > 0])
                .mark_text(dy=-6, fontSize=11, fontWeight="normal")
                .encode(
                    x=alt.X("Tháng:N", sort=None),
                    y=alt.Y("Số đơn:Q"),
                    xOffset=alt.XOffset("Loại:N", sort=_tt_order),
                    color=alt.Color(
                        "Loại:N",
                        scale=alt.Scale(domain=_tt_order, range=["#2C7B6F", "#6DB4AC"]),
                    ),
                    text=alt.Text("label:N"),
                )
            )
            st.altair_chart(
                (_tt_bars + _tt_labels).properties(height=220),
                width='stretch',
            )
        else:
            st.info("Không có dữ liệu.")

    # ── Daily detail table ────────────────────────────────────────────────────
    st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.89rem;font-weight:600;color:rgb(49,51,63);'
        'margin:0 0 0.5rem 0;line-height:1.3;">Bảng chi tiết theo ngày</p>',
        unsafe_allow_html=True,
    )

    _now = pd.Timestamp.now()
    tbl_cols = st.columns([1, 1, 6])
    with tbl_cols[0]:
        tbl_month = st.selectbox(
            "Tháng",
            options=list(range(1, 13)),
            index=_now.month - 1,
            key="tapcare_tbl_month",
        )
    with tbl_cols[1]:
        tbl_year_opts = sorted(
            prod_full_df["Năm"].dropna().unique().astype(int).tolist(), reverse=True
        )
        tbl_year = st.selectbox(
            "Năm", options=tbl_year_opts, index=0, key="tapcare_tbl_year"
        )

    day_df = (
        prod_full_df[
            (prod_full_df["Ngày phát sinh"].dt.month == tbl_month) &
            (prod_full_df["Năm"] == tbl_year)
        ]
        .groupby("Ngày phát sinh", as_index=False)
        .agg(
            tien=("Tiền thực thu", "sum"),
            cap_moi=("Số đơn cấp mới", "sum"),
            tai_tuc=("Số đơn cấp tái tục", "sum"),
            tai_tuc_dk=("Số đơn tái tục dự kiến", "sum"),
            huy=("Số đơn hủy webview", "sum"),
        )
        .sort_values("Ngày phát sinh")
        .reset_index(drop=True)
    )

    if day_df.empty:
        st.info("Không có dữ liệu cho tháng/năm đã chọn.")
    else:
        _lkmap = (
            prod_full_df
            .groupby("Ngày phát sinh")
            .agg(
                tien=("Tiền thực thu", "sum"),
                cap_moi=("Số đơn cấp mới", "sum"),
                tai_tuc_dk=("Số đơn tái tục dự kiến", "sum"),
                huy=("Số đơn hủy webview", "sum"),
            )
            .to_dict(orient="index")
        )

        def _lk(date, field, offset):
            return float(_lkmap.get(date + pd.Timedelta(days=offset), {}).get(field, 0.0))

        def _arrow(current, ref, higher_is_good=True):
            if ref == 0:
                if current > 0:
                    c = "#2e7d32" if higher_is_good else "#c62828"
                    return f'<span style="color:{c}">▲&nbsp;</span>'
                return ""
            if current > ref:
                c = "#2e7d32" if higher_is_good else "#c62828"
                return f'<span style="color:{c}">▲&nbsp;</span>'
            if current < ref:
                c = "#c62828" if higher_is_good else "#2e7d32"
                return f'<span style="color:{c}">▼&nbsp;</span>'
            return ""

        tot_so_don = tot_so_don_30 = 0.0
        tot_tien = tot_tien_30 = tot_tien_dk = 0.0
        tot_cap_moi = tot_cap_moi_30 = 0.0
        tot_huy = tot_tai_tuc = tot_tai_tuc_dk = tot_tang_truong = 0.0

        prev_tang_truong = None
        html_rows = []
        for i, r in day_df.iterrows():
            d        = r["Ngày phát sinh"]
            tien     = r["tien"]
            cap_moi  = r["cap_moi"]
            tai_tuc  = r["tai_tuc"]
            ttdk     = r["tai_tuc_dk"]
            huy      = r["huy"]

            tien_30      = _lk(d, "tien",      -30)
            cap_moi_30   = _lk(d, "cap_moi",   -30)
            huy_30       = _lk(d, "huy",       -30)
            ttdk_5       = _lk(d, "tai_tuc_dk", +5)

            so_don      = tien / _PHI_DON
            so_don_30   = tien_30 / _PHI_DON
            tien_dk     = (cap_moi_30 - huy_30 + ttdk * 0.9 - ttdk_5) * _PHI_DON * 0.95 + tien_30 * 0.95
            tt_rate     = tai_tuc / ttdk if ttdk > 0 else 0.0
            tang_truong = cap_moi - huy - ttdk + tai_tuc

            tot_so_don      += so_don
            tot_so_don_30   += so_don_30
            tot_tien        += tien
            tot_tien_30     += tien_30
            tot_tien_dk     += tien_dk
            tot_cap_moi     += cap_moi
            tot_cap_moi_30  += cap_moi_30
            tot_huy         += huy
            tot_tai_tuc     += tai_tuc
            tot_tai_tuc_dk  += ttdk
            tot_tang_truong += tang_truong

            if prev_tang_truong is not None:
                arr_tt = _arrow(tang_truong, prev_tang_truong)
            else:
                arr_tt = '<span style="color:#2e7d32">▲&nbsp;</span>' if tang_truong > 0 else (
                    '<span style="color:#c62828">▼&nbsp;</span>' if tang_truong < 0 else ""
                )
            prev_tang_truong = tang_truong

            _tt_val_color = "#2e7d32" if tang_truong >= 0 else "#c62828"
            bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
            html_rows.append(
                f'<tr style="background:{bg};">'
                f'<td style="padding:4px 8px;font-weight:500;">{d.day}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(so_don, so_don_30)}{int(round(so_don)):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#888;">{int(round(so_don_30)):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(tien, tien_30)}{tien:,.0f}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#888;">{tien_30:,.0f}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#1B6B3A;">{tien_dk:,.0f}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(cap_moi, cap_moi_30)}{int(cap_moi):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#888;">{int(cap_moi_30):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;">'
                f'{_arrow(huy, huy_30, higher_is_good=False)}'
                f'{int(huy):,}</td>'
                f'<td style="padding:4px 8px;text-align:right;">{tt_rate:.1%}</td>'
                f'<td style="padding:4px 8px;text-align:right;font-weight:600;color:{_tt_val_color};">'
                f'{arr_tt}{int(tang_truong):,}</td>'
                f'</tr>'
            )

        tot_tt_rate = tot_tai_tuc / tot_tai_tuc_dk if tot_tai_tuc_dk > 0 else 0.0
        total_row = (
            f'<tr style="background:#1B6B3A;color:white;font-weight:600;">'
            f'<td style="padding:5px 8px;">Tổng</td>'
            f'<td style="padding:5px 8px;text-align:right;">{int(round(tot_so_don)):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;opacity:0.75;">{int(round(tot_so_don_30)):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{tot_tien:,.0f}</td>'
            f'<td style="padding:5px 8px;text-align:right;opacity:0.75;">{tot_tien_30:,.0f}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{tot_tien_dk:,.0f}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{int(tot_cap_moi):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;opacity:0.75;">{int(tot_cap_moi_30):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{int(tot_huy):,}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{tot_tt_rate:.1%}</td>'
            f'<td style="padding:5px 8px;text-align:right;">{int(tot_tang_truong):,}</td>'
            f'</tr>'
        )

        _HEADERS = [
            "Ngày",
            "Số đơn thu được phí",
            "Số đơn 30NT",
            "Tiền thực thu",
            "Tiền TT 30NT",
            "Tiền TT dự kiến",
            "Số đơn cấp mới",
            "Số đơn cấp mới 30NT",
            "Số đơn hủy",
            "Tỷ lệ TT / DK",
            "Số KH tăng trưởng",
        ]
        header_html = "".join(
            f'<th style="padding:6px 8px;text-align:{"left" if i == 0 else "right"};'
            f'white-space:nowrap;">{h}</th>'
            for i, h in enumerate(_HEADERS)
        )
        st.markdown(
            f'<div style="overflow-x:auto;margin-top:4px;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:0.75rem;">'
            f'<thead><tr style="background:#1B6B3A;color:white;">{header_html}</tr></thead>'
            f'<tbody>{"".join(html_rows)}</tbody>'
            f'<tfoot>{total_row}</tfoot>'
            f'</table></div>',
            unsafe_allow_html=True,
        )
