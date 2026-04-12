"""
payment_retention.py
---------------------
Trang phân tích tỉ lệ thu phí và retention theo kỳ.

4 tab:
  1. Cohort Heatmap    — cohort hiệu lực × kỳ, màu = tỉ lệ thu thành công
  2. Retention Curve   — đường giữ chân tháng-qua-tháng, mỗi đường 1 cohort
  3. Xu hướng theo ngày — rolling 7-ngày, xem retention đang tốt lên/xấu đi
  4. Phân bố theo ngày — ngày trong tháng nào thu nhiều / retention tốt
"""

import streamlit as st
import pandas as pd
import altair as alt

from data_loader import load_all_payment_tracking
from ui_helpers import kpi_card

_PRODUCTS = ["Cyber Risk", "HomeSaving", "I-Safe", "TapCare"]

_PRODUCT_COLORS = {
    "Cyber Risk": "#1f77b4",
    "HomeSaving": "#2ca02c",
    "I-Safe":     "#ff7f0e",
    "TapCare":    "#9467bd",
}

_MIN_GCN_DEFAULT = 100   # lọc ngày/tháng có quá ít dữ liệu


# ── helpers ──────────────────────────────────────────────────────────────────

def _retention_color_scale():
    return alt.Scale(
        scheme="redyellowgreen",
        domain=[0, 1],
        clamp=True,
    )


def _pct_fmt(v):
    return f"{v:.1f}%" if pd.notna(v) else "—"


# ── Scorecard ────────────────────────────────────────────────────────────────

def _scorecard_metrics(
    df_ky: pd.DataFrame,
    df_month: pd.DataFrame,
    df_date: pd.DataFrame,
    products: list[str],
) -> dict:
    """Tính toán các chỉ số tổng hợp cho scorecard."""
    fky = df_ky[df_ky["san_pham"].isin(products)]

    da_thu   = fky.loc[fky["trang_thai"] == "da_thu",           "so_gcn"].sum()
    qua_han  = fky.loc[fky["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
    tong     = da_thu + qua_han
    ty_le    = da_thu / tong * 100 if tong > 0 else 0.0

    # Delta tỉ lệ thu: cohort mới nhất vs cohort trước đó
    cohorts = sorted(fky["cohort_month"].unique())
    ty_le_delta = None
    if len(cohorts) >= 2:
        def _rate(cohort):
            sub = fky[fky["cohort_month"] == cohort]
            d = sub.loc[sub["trang_thai"] == "da_thu",           "so_gcn"].sum()
            c = sub.loc[sub["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
            return d / (d + c) * 100 if (d + c) > 0 else None
        r_new  = _rate(cohorts[-1])
        r_prev = _rate(cohorts[-2])
        if r_new is not None and r_prev is not None:
            ty_le_delta = r_new - r_prev

    # Avg retention kỳ 2→3 (mature months only: < tháng hiện tại - 1)
    cutoff_month = (pd.Timestamp.now() - pd.DateOffset(months=1)).to_period("M").to_timestamp()
    fm = df_month[
        df_month["san_pham"].isin(products)
        & (df_month["thang_tra_ky_k"] < cutoff_month)
        & (df_month["ky"] == 2)
    ]
    ret_ky2 = fm["ty_le_giu_chan_pct"].mean() if not fm.empty else None

    # MoM delta retention kỳ 2: tháng gần nhất mature vs tháng trước đó
    ret_delta = None
    months_ky2 = sorted(fm["thang_tra_ky_k"].unique()) if not fm.empty else []
    if len(months_ky2) >= 2:
        r_new  = fm[fm["thang_tra_ky_k"] == months_ky2[-1]]["ty_le_giu_chan_pct"].mean()
        r_prev = fm[fm["thang_tra_ky_k"] == months_ky2[-2]]["ty_le_giu_chan_pct"].mean()
        if pd.notna(r_new) and pd.notna(r_prev):
            ret_delta = r_new - r_prev

    # Kỳ có retention thấp nhất (drop-off point)
    fm_all = df_month[
        df_month["san_pham"].isin(products)
        & (df_month["thang_tra_ky_k"] < cutoff_month)
        & df_month["ky"].between(2, 11)
    ]
    dropoff_ky = None
    if not fm_all.empty:
        avg_by_ky = fm_all.groupby("ky")["ty_le_giu_chan_pct"].mean()
        if not avg_by_ky.empty:
            dropoff_ky = int(avg_by_ky.idxmin())
            dropoff_val = avg_by_ky.min()
        else:
            dropoff_val = None
    else:
        dropoff_val = None

    # Avg retention tổng kỳ 2–11 (mature)
    ret_overall = fm_all["ty_le_giu_chan_pct"].mean() if not fm_all.empty else None

    return dict(
        da_thu=int(da_thu), qua_han=int(qua_han), tong=int(tong),
        ty_le=ty_le, ty_le_delta=ty_le_delta,
        ret_ky2=ret_ky2, ret_delta=ret_delta,
        ret_overall=ret_overall,
        dropoff_ky=dropoff_ky, dropoff_val=dropoff_val,
    )


def _render_scorecard(
    df_ky: pd.DataFrame,
    df_month: pd.DataFrame,
    df_date: pd.DataFrame,
    products: list[str],
) -> None:
    m = _scorecard_metrics(df_ky, df_month, df_date, products)

    # ── Row 1: 4 KPI cards ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    # Card 1: Tỉ lệ thu phí
    ty_le_delta_str = ""
    ty_le_delta_color = "#888"
    if m["ty_le_delta"] is not None:
        sign = "▲" if m["ty_le_delta"] >= 0 else "▼"
        ty_le_delta_color = "#2e7d32" if m["ty_le_delta"] >= 0 else "#c62828"
        ty_le_delta_str = f"{sign} {abs(m['ty_le_delta']):.1f}pp so với cohort trước"

    with c1:
        st.markdown(kpi_card(
            label="TỈ LỆ THU PHÍ",
            value=f"{m['ty_le']:.1f}%",
            delta_str=ty_le_delta_str or "—",
            delta_color=ty_le_delta_color,
            accent_color="#1565C0",
            subtitle=f"{m['da_thu']:,} / {m['tong']:,} GCN-kỳ",
            tooltip="da_thu / (da_thu + chua_thu_qua_han) theo cohort hiệu lực",
        ), unsafe_allow_html=True)

    # Card 2: GCN quá hạn
    qh_pct = m["qua_han"] / m["tong"] * 100 if m["tong"] > 0 else 0
    with c2:
        st.markdown(kpi_card(
            label="GCN QUÁ HẠN CHƯA THU",
            value=f"{m['qua_han']:,}",
            delta_str=f"{qh_pct:.1f}% tổng GCN-kỳ cần thu",
            delta_color="#c62828" if qh_pct > 30 else "#e65100" if qh_pct > 15 else "#2e7d32",
            accent_color="#b71c1c",
            subtitle=f"Tổng {m['tong']:,} GCN-kỳ được theo dõi",
        ), unsafe_allow_html=True)

    # Card 3: Retention kỳ 2→3
    ret_str = f"{m['ret_ky2']:.1f}%" if m["ret_ky2"] is not None else "—"
    ret_delta_str = ""
    ret_delta_color = "#888"
    if m["ret_delta"] is not None:
        sign = "▲" if m["ret_delta"] >= 0 else "▼"
        ret_delta_color = "#2e7d32" if m["ret_delta"] >= 0 else "#c62828"
        ret_delta_str = f"{sign} {abs(m['ret_delta']):.1f}pp so với tháng trước"

    with c3:
        st.markdown(kpi_card(
            label="RETENTION KỲ 2 → 3",
            value=ret_str,
            delta_str=ret_delta_str or "—",
            delta_color=ret_delta_color,
            accent_color="#1b5e20",
            subtitle="Avg các tháng đã đủ thời gian",
            tooltip="Tỉ lệ GCN trả kỳ 2 rồi tiếp tục trả kỳ 3 (tháng mature)",
        ), unsafe_allow_html=True)

    # Card 4: Kỳ drop-off
    if m["dropoff_ky"] is not None:
        dropoff_val_str = f"{m['dropoff_val']:.1f}%" if m["dropoff_val"] is not None else "—"
        dropoff_display = f"Kỳ {m['dropoff_ky']} → {m['dropoff_ky'] + 1}"
        dropoff_sub = f"Avg retention: {dropoff_val_str}"
    else:
        dropoff_display = "—"
        dropoff_sub = "Chưa đủ dữ liệu"

    with c4:
        st.markdown(kpi_card(
            label="KỲ DROP-OFF THẤP NHẤT",
            value=dropoff_display,
            delta_str=f"Retention avg: {dropoff_val_str if m['dropoff_ky'] else '—'}",
            delta_color="#e65100",
            accent_color="#e65100",
            subtitle="Kỳ có tỉ lệ giữ chân thấp nhất",
            tooltip="Kỳ k→k+1 có avg retention thấp nhất (tháng mature, kỳ 2–11)",
        ), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── Row 2: Per-product breakdown ──────────────────────────────────────────
    with st.expander("Chi tiết theo sản phẩm", expanded=True):
        rows = []
        cutoff_month = (
            pd.Timestamp.now() - pd.DateOffset(months=1)
        ).to_period("M").to_timestamp()

        for sp in sorted(products):
            sp_ky = df_ky[df_ky["san_pham"] == sp]
            d = sp_ky.loc[sp_ky["trang_thai"] == "da_thu",           "so_gcn"].sum()
            q = sp_ky.loc[sp_ky["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
            tl = d / (d + q) * 100 if (d + q) > 0 else 0

            sp_m = df_month[
                df_month["san_pham"].eq(sp)
                & df_month["thang_tra_ky_k"].lt(cutoff_month)
            ]
            ret2 = sp_m[sp_m["ky"] == 2]["ty_le_giu_chan_pct"].mean()
            ret_all = sp_m[sp_m["ky"].between(2, 11)]["ty_le_giu_chan_pct"].mean()

            dp_ky_val = None
            dp_ret = None
            avg_by_ky = sp_m[sp_m["ky"].between(2, 11)].groupby("ky")["ty_le_giu_chan_pct"].mean()
            if not avg_by_ky.empty:
                dp_ky_val = int(avg_by_ky.idxmin())
                dp_ret = avg_by_ky.min()

            rows.append({
                "Sản phẩm":        sp,
                "Tỉ lệ thu (%)":   f"{tl:.1f}",
                "GCN đã thu":      f"{int(d):,}",
                "GCN quá hạn":     f"{int(q):,}",
                "Retention K2→3 (%)": f"{ret2:.1f}" if pd.notna(ret2) else "—",
                "Retention avg (%)":  f"{ret_all:.1f}" if pd.notna(ret_all) else "—",
                "Kỳ drop-off":     f"Kỳ {dp_ky_val}→{dp_ky_val+1} ({dp_ret:.1f}%)" if dp_ky_val else "—",
            })

        if rows:
            st.dataframe(
                pd.DataFrame(rows).set_index("Sản phẩm"),
                use_container_width=True,
            )


# ── Chart 1: Cohort Heatmap ───────────────────────────────────────────────────

def _render_cohort_heatmap(df_ky: pd.DataFrame, products: list[str]):
    st.markdown("#### Tỉ lệ thu thành công theo cohort hiệu lực")
    st.caption(
        "Mỗi ô = tỉ lệ GCN **đã thu** / (đã thu + chưa thu quá hạn) cho cohort đó ở kỳ đó. "
        "Vùng trống góc trên-phải = kỳ chưa đến hạn với cohort mới."
    )

    df = df_ky[df_ky["san_pham"].isin(products)].copy()
    if df.empty:
        st.info("Không có dữ liệu cho sản phẩm đã chọn.")
        return

    # Tính tỉ lệ thu mỗi (san_pham, cohort_month, ky)
    grp = (
        df.groupby(["san_pham", "cohort_month", "ky", "trang_thai"])["so_gcn"]
        .sum()
        .reset_index()
    )
    wide = grp.pivot_table(
        index=["san_pham", "cohort_month", "ky"],
        columns="trang_thai",
        values="so_gcn",
        aggfunc="sum",
    ).fillna(0).reset_index()
    wide.columns.name = None

    if "da_thu" not in wide.columns:
        wide["da_thu"] = 0
    if "chua_thu_qua_han" not in wide.columns:
        wide["chua_thu_qua_han"] = 0

    import numpy as np
    da_thu = np.array(wide["da_thu"].fillna(0), dtype=float)
    chua   = np.array(wide["chua_thu_qua_han"].fillna(0), dtype=float)
    tong   = da_thu + chua
    wide["tong"] = tong
    wide["ty_le"] = np.where(tong > 0, np.round(da_thu / np.where(tong > 0, tong, 1.0), 4), np.nan)
    wide["cohort_str"] = wide["cohort_month"].dt.strftime("%Y-%m")
    wide["ty_le_pct_str"] = wide["ty_le"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")

    n_products = len(wide["san_pham"].unique())
    cols = st.columns(min(n_products, 2))

    for i, sp in enumerate(sorted(wide["san_pham"].unique())):
        sp_df = wide[wide["san_pham"] == sp].copy()
        with cols[i % 2]:
            st.markdown(f"**{sp}**")
            chart = (
                alt.Chart(sp_df)
                .mark_rect(stroke="white", strokeWidth=0.5)
                .encode(
                    x=alt.X(
                        "ky:O",
                        title="Kỳ thu",
                        axis=alt.Axis(labelAngle=0),
                    ),
                    y=alt.Y(
                        "cohort_str:O",
                        title="Tháng hiệu lực",
                        sort="descending",
                    ),
                    color=alt.Color(
                        "ty_le:Q",
                        scale=_retention_color_scale(),
                        title="Tỉ lệ thu",
                        legend=alt.Legend(format=".0%"),
                    ),
                    tooltip=[
                        alt.Tooltip("cohort_str:N", title="Cohort"),
                        alt.Tooltip("ky:O", title="Kỳ"),
                        alt.Tooltip("ty_le_pct_str:N", title="Tỉ lệ thu"),
                        alt.Tooltip("da_thu:Q", title="Đã thu", format=","),
                        alt.Tooltip("chua_thu_qua_han:Q", title="Chưa thu", format=","),
                    ],
                )
                .properties(height=max(200, len(sp_df["cohort_str"].unique()) * 24 + 60))
            )
            st.altair_chart(chart, use_container_width=True)


# ── Chart 2: Retention Curve ─────────────────────────────────────────────────

def _render_retention_curve(df_month: pd.DataFrame, products: list[str], min_gcn: int):
    st.markdown("#### Đường retention theo kỳ (tháng-qua-tháng)")
    st.caption(
        "Mỗi đường mờ = 1 cohort tháng. Đường đậm = trung bình. "
        "Đọc: điểm (kỳ=3, 85%) nghĩa là 85% GCN trả kỳ 2 tháng đó đã trả tiếp kỳ 3."
    )

    df = df_month[df_month["san_pham"].isin(products)].copy()
    if df.empty:
        st.info("Không có dữ liệu.")
        return

    # Chỉ lấy tháng đủ cũ để kỳ k+1 có thể đã xảy ra (tháng < tháng hiện tại)
    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(months=1)
    df_old = df[df["thang_tra_ky_k"] <= cutoff].copy()
    if df_old.empty:
        st.info("Chưa đủ dữ liệu lịch sử (cần ít nhất 1 tháng cũ).")
        return

    df_old["thang_str"] = df_old["thang_tra_ky_k"].dt.strftime("%Y-%m")

    n_products = len(df_old["san_pham"].unique())
    cols = st.columns(min(n_products, 2))

    for i, sp in enumerate(sorted(df_old["san_pham"].unique())):
        sp_df = df_old[df_old["san_pham"] == sp].copy()
        color = _PRODUCT_COLORS.get(sp, "steelblue")

        # Đường từng cohort (mờ)
        faint_lines = (
            alt.Chart(sp_df)
            .mark_line(opacity=0.25, strokeWidth=1.2, color=color)
            .encode(
                x=alt.X("ky:O", title="Kỳ thu", axis=alt.Axis(labelAngle=0)),
                y=alt.Y(
                    "ty_le_giu_chan_pct:Q",
                    title="Tỉ lệ giữ chân (%)",
                    scale=alt.Scale(domain=[0, 105]),
                ),
                detail="thang_str:N",
                tooltip=[
                    alt.Tooltip("thang_str:N", title="Tháng"),
                    alt.Tooltip("ky:O", title="Kỳ"),
                    alt.Tooltip("ty_le_giu_chan_pct:Q", title="Giữ chân %", format=".1f"),
                    alt.Tooltip("so_gcn:Q", title="Tổng GCN", format=","),
                ],
            )
        )

        # Đường trung bình (đậm)
        avg_line = (
            alt.Chart(sp_df)
            .mark_line(strokeWidth=3, color=color)
            .encode(
                x=alt.X("ky:O"),
                y=alt.Y("mean(ty_le_giu_chan_pct):Q"),
                tooltip=[
                    alt.Tooltip("ky:O", title="Kỳ"),
                    alt.Tooltip(
                        "mean(ty_le_giu_chan_pct):Q",
                        title="Avg giữ chân %",
                        format=".1f",
                    ),
                ],
            )
        )

        # Điểm trên đường avg
        avg_points = (
            alt.Chart(sp_df)
            .mark_point(filled=True, size=60, color=color)
            .encode(
                x="ky:O",
                y="mean(ty_le_giu_chan_pct):Q",
            )
        )

        chart = (faint_lines + avg_line + avg_points).properties(
            title=sp, height=280
        )
        with cols[i % 2]:
            st.altair_chart(chart, use_container_width=True)


# ── Chart 3: Rolling 7-day Trend ─────────────────────────────────────────────

def _render_rolling_trend(df_date: pd.DataFrame, products: list[str], min_gcn: int):
    st.markdown("#### Xu hướng retention theo ngày (rolling 7 ngày)")
    st.caption(
        "Tỉ lệ giữ chân trung bình 7 ngày. Chỉ tính ngày có ≥ "
        f"{min_gcn:,} GCN để tránh nhiễu từ ngày ít dữ liệu."
    )

    col_ky, _ = st.columns([1, 3])
    with col_ky:
        selected_ky = st.selectbox(
            "Xem kỳ",
            options=list(range(2, 12)),
            index=0,
            key="trend_ky",
            format_func=lambda k: f"Kỳ {k} → Kỳ {k+1}",
        )

    df = df_date[
        df_date["san_pham"].isin(products)
        & (df_date["ky"] == selected_ky)
        & (df_date["so_gcn"] >= min_gcn)
    ].copy()

    if df.empty:
        st.info("Không có dữ liệu cho kỳ và bộ lọc đã chọn.")
        return

    # Rolling 7-ngày cho mỗi sản phẩm
    records = []
    for sp, grp in df.groupby("san_pham"):
        g = grp.sort_values("ngay_tra_ky_k").copy()
        g["rolling_7"] = g["ty_le_giu_chan_pct"].rolling(7, min_periods=3).mean().round(2)
        records.append(g)
    df_roll = pd.concat(records, ignore_index=True)

    # Cắt bỏ 30 ngày gần nhất vì kỳ k+1 chưa có đủ thời gian xảy ra
    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(days=30)
    df_roll = df_roll[df_roll["ngay_tra_ky_k"] <= cutoff]
    if df_roll.empty:
        st.info("Chưa đủ dữ liệu lịch sử.")
        return

    base = alt.Chart(df_roll).encode(
        x=alt.X("ngay_tra_ky_k:T", title="Ngày"),
        color=alt.Color(
            "san_pham:N",
            title="Sản phẩm",
            scale=alt.Scale(
                domain=list(_PRODUCT_COLORS.keys()),
                range=list(_PRODUCT_COLORS.values()),
            ),
        ),
        tooltip=[
            alt.Tooltip("san_pham:N", title="Sản phẩm"),
            alt.Tooltip("ngay_tra_ky_k:T", title="Ngày", format="%d/%m/%Y"),
            alt.Tooltip("rolling_7:Q", title="Giữ chân 7-ngày avg (%)", format=".1f"),
            alt.Tooltip("ty_le_giu_chan_pct:Q", title="Giữ chân ngày (%)", format=".1f"),
            alt.Tooltip("so_gcn:Q", title="GCN", format=","),
        ],
    )

    lines = base.mark_line(strokeWidth=2).encode(
        y=alt.Y("rolling_7:Q", title="Tỉ lệ giữ chân 7-ngày avg (%)", scale=alt.Scale(zero=False)),
    )
    band = base.mark_errorband(extent="ci").encode(
        y=alt.Y("ty_le_giu_chan_pct:Q"),
    )

    chart = (band + lines).properties(height=320)
    st.altair_chart(chart, use_container_width=True)


# ── Chart 4: Day-of-Month Heatmap ────────────────────────────────────────────

def _render_dom_heatmap(df_date: pd.DataFrame, products: list[str], min_gcn: int):
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Volume thu theo ngày trong tháng")
        st.caption("Tổng GCN trung bình theo ngày trong tháng × kỳ. "
                   "Cho thấy ngày nào dồn nhiều giao dịch nhất.")

    with col_right:
        st.markdown("#### Retention theo ngày trong tháng")
        st.caption("Tỉ lệ giữ chân avg theo ngày trong tháng × kỳ. "
                   "GCN trả vào ngày cuối tháng có retention thấp hơn không?")

    df = df_date[
        df_date["san_pham"].isin(products)
        & (df_date["so_gcn"] >= min_gcn)
    ].copy()

    if df.empty:
        st.info("Không có dữ liệu.")
        return

    df["ngay_trong_thang"] = df["ngay_tra_ky_k"].dt.day

    dom = (
        df.groupby(["ngay_trong_thang", "ky"])
        .agg(
            avg_gcn=("so_gcn", "mean"),
            avg_retention=("ty_le_giu_chan_pct", "mean"),
        )
        .reset_index()
    )
    dom["avg_gcn"] = dom["avg_gcn"].round(0)
    dom["avg_retention"] = dom["avg_retention"].round(2)

    base = alt.Chart(dom).encode(
        x=alt.X(
            "ngay_trong_thang:O",
            title="Ngày trong tháng",
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y("ky:O", title="Kỳ thu", sort="descending"),
    )

    with col_left:
        vol_chart = base.mark_rect(stroke="white", strokeWidth=0.3).encode(
            color=alt.Color(
                "avg_gcn:Q",
                scale=alt.Scale(scheme="blues"),
                title="GCN/ngày (avg)",
                legend=alt.Legend(format=".0f"),
            ),
            tooltip=[
                alt.Tooltip("ngay_trong_thang:O", title="Ngày"),
                alt.Tooltip("ky:O", title="Kỳ"),
                alt.Tooltip("avg_gcn:Q", title="GCN avg/ngày", format=",.0f"),
            ],
        ).properties(height=300)
        st.altair_chart(vol_chart, use_container_width=True)

    with col_right:
        r_min = dom["avg_retention"].min()
        r_max = dom["avg_retention"].max()
        # Stretch domain to actual data range so variation is visible
        r_domain = [r_min, r_max] if r_max > r_min else [max(0, r_min - 0.01), r_max]
        ret_chart = base.mark_rect(stroke="white", strokeWidth=0.3).encode(
            color=alt.Color(
                "avg_retention:Q",
                scale=alt.Scale(scheme="redyellowgreen", domain=r_domain, clamp=True),
                title="Giữ chân avg (%)",
                legend=alt.Legend(format=".2f"),
            ),
            tooltip=[
                alt.Tooltip("ngay_trong_thang:O", title="Ngày"),
                alt.Tooltip("ky:O", title="Kỳ"),
                alt.Tooltip("avg_retention:Q", title="Giữ chân avg %", format=".1f"),
                alt.Tooltip("avg_gcn:Q", title="GCN avg/ngày", format=",.0f"),
            ],
        ).properties(height=300)
        st.altair_chart(ret_chart, use_container_width=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render_payment_retention_page():
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;margin-bottom:0.5rem;">'
        "PHÂN TÍCH TỈ LỆ THU PHÍ VÀ RETENTION THEO KỲ</h1>",
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        df_ky, df_month, df_date = load_all_payment_tracking()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        st.info(
            "Chạy lệnh sau để xây dựng các bảng tracking:\n"
            "```\npython Scripts/transform_data/build_payment_tracking.py\n```"
        )
        return

    # ── Global filters ────────────────────────────────────────────────────────
    f_col1, f_col2, f_col3 = st.columns([3, 2, 1])
    with f_col1:
        selected_products = st.multiselect(
            "Sản phẩm",
            options=_PRODUCTS,
            default=_PRODUCTS,
            key="ret_products",
        )
    with f_col2:
        # Date range from df_date
        d_min = df_date["ngay_tra_ky_k"].min().date()
        d_max = df_date["ngay_tra_ky_k"].max().date()
        date_range = st.date_input(
            "Khoảng thời gian",
            value=(d_min, d_max),
            min_value=d_min,
            max_value=d_max,
            key="ret_dates",
        )
    with f_col3:
        min_gcn = st.number_input(
            "Tối thiểu GCN/ngày",
            min_value=10,
            max_value=10000,
            value=_MIN_GCN_DEFAULT,
            step=50,
            key="ret_min_gcn",
        )

    if not selected_products:
        st.warning("Vui lòng chọn ít nhất một sản phẩm.")
        return

    # Apply date filter to df_date and df_month
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_start = pd.Timestamp(date_range[0])
        d_end   = pd.Timestamp(date_range[1])
        df_date  = df_date[
            df_date["ngay_tra_ky_k"].between(d_start, d_end)
        ]
        df_month = df_month[
            df_month["thang_tra_ky_k"].between(
                d_start.to_period("M").to_timestamp(),
                d_end.to_period("M").to_timestamp(),
            )
        ]

    st.divider()

    # ── Scorecard ─────────────────────────────────────────────────────────────
    _render_scorecard(df_ky, df_month, df_date, selected_products)

    st.divider()

    # ── 4 tabs ────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Cohort Heatmap",
        "📈 Retention Curve",
        "📉 Xu hướng theo ngày",
        "📅 Phân bố ngày trong tháng",
    ])

    with tab1:
        _render_cohort_heatmap(df_ky, selected_products)

    with tab2:
        _render_retention_curve(df_month, selected_products, min_gcn)

    with tab3:
        _render_rolling_trend(df_date, selected_products, min_gcn)

    with tab4:
        _render_dom_heatmap(df_date, selected_products, min_gcn)
