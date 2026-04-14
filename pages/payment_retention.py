"""
payment_retention.py
---------------------
Trang phân tích tỉ lệ thu phí và duy trì đóng phí theo kỳ.

4 tab:
  1. Thu phí theo tháng hiệu lực — Q1: trong số HĐ đến hạn, bao nhiêu % đã thu? (heatmap tháng × kỳ)
  2. Thu phí theo tháng thu phí  — Q2: trong số HĐ hiệu lực, bao nhiêu % đang đóng phí?
  3. Duy trì đóng phí theo kỳ   — tỉ lệ tiếp tục đóng phí qua từng kỳ
  4. Trạng thái thu phí theo ngày — bảng chi tiết payment_tracking_by_payment_date, lọc theo Tháng & Năm
"""

import streamlit as st
import pandas as pd
import altair as alt

from data_loader import load_all_payment_tracking, load_portfolio_health, load_payment_retention_by_ky_thu
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
    df_health: pd.DataFrame,
    products: list[str],
) -> dict:
    """Tính toán các chỉ số tổng hợp cho scorecard."""
    fky = df_ky[df_ky["san_pham"].isin(products)]

    # Q1 — Hiệu quả thu trong kỳ: bỏ qua cohort < 3 tháng (kỳ 2 chưa đủ thời gian thu)
    cohort_max = (pd.Timestamp.now() - pd.DateOffset(months=3)).to_period("M").to_timestamp()
    fky_q1 = fky[fky["cohort_month"] <= cohort_max]

    da_thu  = fky_q1.loc[fky_q1["trang_thai"] == "da_thu",           "so_gcn"].sum()
    qua_han = fky_q1.loc[fky_q1["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
    tong    = da_thu + qua_han
    ty_le   = da_thu / tong * 100 if tong > 0 else 0.0

    # Delta Q1: 2 cohort gần nhất trong window
    cohorts = sorted(fky_q1["cohort_month"].unique())
    ty_le_delta = None
    if len(cohorts) >= 2:
        def _rate(cohort):
            sub = fky_q1[fky_q1["cohort_month"] == cohort]
            d = sub.loc[sub["trang_thai"] == "da_thu",           "so_gcn"].sum()
            c = sub.loc[sub["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
            return d / (d + c) * 100 if (d + c) > 0 else None
        r_new  = _rate(cohorts[-1])
        r_prev = _rate(cohorts[-2])
        if r_new is not None and r_prev is not None:
            ty_le_delta = r_new - r_prev

    cutoff_month = (pd.Timestamp.now() - pd.DateOffset(months=1)).to_period("M").to_timestamp()

    # Kỳ có retention thấp nhất (drop-off point)
    fm_all = df_month[
        df_month["san_pham"].isin(products)
        & (df_month["thang_tra_ky_k"] < cutoff_month)
        & df_month["ky"].between(2, 11)
    ]
    dropoff_ky = None
    best_ky = None
    best_ky_ret = None
    best_ky_delta = None
    if not fm_all.empty:
        avg_by_ky = fm_all.groupby("ky")["ty_le_giu_chan_pct"].mean()
        if not avg_by_ky.empty:
            dropoff_ky = int(avg_by_ky.idxmin())
            dropoff_val = avg_by_ky.min()
            best_ky = int(avg_by_ky.idxmax())
            best_ky_ret = float(avg_by_ky.max())
            fm_best = fm_all[fm_all["ky"] == best_ky]
            months_best = sorted(fm_best["thang_tra_ky_k"].unique())
            if len(months_best) >= 2:
                r_new = fm_best[fm_best["thang_tra_ky_k"] == months_best[-1]]["ty_le_giu_chan_pct"].mean()
                r_prev = fm_best[fm_best["thang_tra_ky_k"] == months_best[-2]]["ty_le_giu_chan_pct"].mean()
                if pd.notna(r_new) and pd.notna(r_prev):
                    best_ky_delta = float(r_new - r_prev)
        else:
            dropoff_val = None
    else:
        dropoff_val = None

    # Avg retention tổng kỳ 2–11 (mature)
    ret_overall = fm_all["ty_le_giu_chan_pct"].mean() if not fm_all.empty else None

    # Q2 — Sức khỏe danh mục: distinct GCN đang đóng phí / GCN có hiệu lực
    # Dùng tháng mới nhất có đủ cả distinct_gcn lẫn hieu_luc cho các sản phẩm đang chọn
    df_health_filtered = df_health[
        df_health["san_pham"].isin(products)
        & df_health["hieu_luc"].notna()
        & (df_health["hieu_luc"] > 0)
    ]
    mature_month = df_health_filtered["thang"].max() if not df_health_filtered.empty else None

    def _q2_rate(thang):
        if thang is None:
            return None, None, None
        dh = df_health_filtered[df_health_filtered["thang"] == thang]
        if dh.empty or not dh["hieu_luc"].notna().any():
            return None, None, None
        gcn = int(dh["distinct_gcn"].sum())
        hl  = int(dh["hieu_luc"].sum())
        rate = gcn / hl * 100 if hl > 0 else None
        return gcn, hl, rate

    active_gcn, active_hieu_luc, ty_le_active = _q2_rate(mature_month)
    active_month_label = mature_month.strftime("%m/%Y") if mature_month is not None else "—"

    prev_month = (
        (mature_month - pd.DateOffset(months=1)).to_period("M").to_timestamp()
        if mature_month is not None else None
    )
    _, _, ty_le_active_prev = _q2_rate(prev_month)
    prev_month_label = prev_month.strftime("%m/%Y") if prev_month is not None else "—"
    ty_le_active_delta = (
        ty_le_active - ty_le_active_prev
        if ty_le_active is not None and ty_le_active_prev is not None
        else None
    )

    return dict(
        da_thu=int(da_thu), qua_han=int(qua_han), tong=int(tong),
        ty_le=ty_le, ty_le_delta=ty_le_delta,
        best_ky=best_ky, best_ky_ret=best_ky_ret, best_ky_delta=best_ky_delta,
        ret_overall=ret_overall,
        dropoff_ky=dropoff_ky, dropoff_val=dropoff_val,
        active_gcn=active_gcn, active_hieu_luc=active_hieu_luc,
        ty_le_active=ty_le_active, active_month_label=active_month_label,
        ty_le_active_prev=ty_le_active_prev, prev_month_label=prev_month_label,
        ty_le_active_delta=ty_le_active_delta,
    )


def _render_scorecard(
    df_ky: pd.DataFrame,
    df_month: pd.DataFrame,
    df_date: pd.DataFrame,
    df_health: pd.DataFrame,
    products: list[str],
) -> None:
    m = _scorecard_metrics(df_ky, df_month, df_date, df_health, products)

    # ── Row 1: 5 KPI cards ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    # Card 1: Tỉ lệ thu phí
    ty_le_delta_str = ""
    ty_le_delta_color = "#888"
    if m["ty_le_delta"] is not None:
        sign = "▲" if m["ty_le_delta"] >= 0 else "▼"
        ty_le_delta_color = "#2e7d32" if m["ty_le_delta"] >= 0 else "#c62828"
        ty_le_delta_str = f"{sign} {abs(m['ty_le_delta']):.1f} điểm % so với nhóm trước"

    with c1:
        st.markdown(kpi_card(
            label="TỶ LỆ THU PHÍ THEO THÁNG HIỆU LỰC",
            value=f"{m['ty_le']:.1f}%",
            delta_str=ty_le_delta_str or "—",
            delta_color=ty_le_delta_color,
            accent_color="#1565C0",
            subtitle=f"HĐ hiệu lực từ đầu đến 3 tháng trước · {m['da_thu']:,}/{m['tong']:,} HĐ",
            tooltip="Trong số các hợp đồng đã đến hạn phải trả kỳ này, "
                    "bao nhiêu % thực sự đã trả? "
                    "Loại trừ cohort < 3 tháng tuổi (kỳ 2 chưa đủ thời gian thu, cần 90 ngày).",
        ), unsafe_allow_html=True)

    # Card 2: Q2 — Sức khỏe danh mục
    with c2:
        if m["ty_le_active"] is not None:
            active_val   = f"{m['ty_le_active']:.1f}%"
            active_sub   = (
                f"Tháng {m['active_month_label']} · "
                f"{m['active_gcn']:,} / {m['active_hieu_luc']:,} HĐ"
            )
            active_color = (
                "#2e7d32" if m["ty_le_active"] >= 70
                else "#e65100" if m["ty_le_active"] >= 50
                else "#c62828"
            )
            if m["ty_le_active_delta"] is not None:
                sign = "▲" if m["ty_le_active_delta"] >= 0 else "▼"
                d_color = "#2e7d32" if m["ty_le_active_delta"] >= 0 else "#c62828"
                active_delta_str = (
                    f"{sign} {abs(m['ty_le_active_delta']):.1f} điểm % so với {m['prev_month_label']}"
                )
            else:
                active_delta_str = active_sub
                d_color = active_color
        else:
            active_val        = "—"
            active_sub        = "Chưa đủ dữ liệu"
            active_delta_str  = "—"
            active_color      = "#888"
            d_color           = "#888"
        st.markdown(kpi_card(
            label="TỶ LỆ THU PHÍ THEO THÁNG THU PHÍ",
            value=active_val,
            delta_str=active_delta_str,
            delta_color=d_color,
            accent_color="#6a1b9a",
            subtitle=active_sub if m["ty_le_active"] is not None else "Chưa đủ dữ liệu",
            tooltip="Số hợp đồng đã trả ít nhất 1 kỳ trong tháng / Số hợp đồng đang hiệu lực. "
                    "Lưu ý: số HĐ hiệu lực của Cyber Risk không cập nhật từ đầu năm 2026.",
        ), unsafe_allow_html=True)

    # Card 3: HĐ quá hạn
    qh_pct = m["qua_han"] / m["tong"] * 100 if m["tong"] > 0 else 0
    with c3:
        st.markdown(kpi_card(
            label="HỢP ĐỒNG QUÁ HẠN CHƯA THU",
            value=f"{m['qua_han']:,}",
            delta_str=f"{qh_pct:.1f}% tổng hợp đồng đang theo dõi",
            delta_color="#c62828" if qh_pct > 30 else "#e65100" if qh_pct > 15 else "#2e7d32",
            accent_color="#b71c1c",
            subtitle=f"Tổng {m['tong']:,} hợp đồng đang theo dõi",
        ), unsafe_allow_html=True)

    # Card 4: Kỳ thu phí tốt nhất
    if m["best_ky"] is not None:
        best_ky_display = f"Kỳ {m['best_ky']} → {m['best_ky'] + 1}"
        best_ky_ret_str = f"{m['best_ky_ret']:.1f}%"
    else:
        best_ky_display = "—"
        best_ky_ret_str = "—"

    with c4:
        st.markdown(kpi_card(
            label="KỲ THU PHÍ TỐT NHẤT",
            value=best_ky_display,
            delta_str=f"Duy trì: {best_ky_ret_str}",
            delta_color="#2e7d32",
            accent_color="#2e7d32",
            subtitle="Kỳ khách hàng duy trì đóng phí tốt nhất",
            tooltip="Kỳ thu phí có tỉ lệ duy trì đóng phí cao nhất, tính trên kỳ 2–11 "
                    "của các tháng đã có đủ dữ liệu (mature).",
        ), unsafe_allow_html=True)

    # Card 5: Kỳ duy trì thấp nhất
    if m["dropoff_ky"] is not None:
        dropoff_val_str = f"{m['dropoff_val']:.1f}%" if m["dropoff_val"] is not None else "—"
        dropoff_display = f"Kỳ {m['dropoff_ky']} → {m['dropoff_ky'] + 1}"
    else:
        dropoff_val_str = "—"
        dropoff_display = "—"

    with c5:
        st.markdown(kpi_card(
            label="KỲ DỄ NGHỈ NHẤT",
            value=dropoff_display,
            delta_str=f"Duy trì: {dropoff_val_str}",
            delta_color="#e65100",
            accent_color="#e65100",
            subtitle="Kỳ khách hàng dễ dừng đóng phí nhất",
            tooltip="Kỳ mà tỉ lệ tiếp tục đóng phí thấp nhất, tính trên các tháng đã có đủ dữ liệu (kỳ 2–11).",
        ), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── Row 2: Per-product breakdown ──────────────────────────────────────────
    with st.expander("Chi tiết theo sản phẩm", expanded=True):
        rows = []
        cohort_max = (pd.Timestamp.now() - pd.DateOffset(months=3)).to_period("M").to_timestamp()
        cutoff_month = (pd.Timestamp.now() - pd.DateOffset(months=1)).to_period("M").to_timestamp()
        # Dùng max thang từ data (giống scorecard), không hardcode offset
        _dh_all = df_health[
            df_health["san_pham"].isin(products)
            & df_health["hieu_luc"].notna()
            & (df_health["hieu_luc"] > 0)
        ]
        mature_month = _dh_all["thang"].max() if not _dh_all.empty else None

        for sp in sorted(products):
            # Q1: loại trừ cohort < 3 tháng tuổi
            sp_ky = df_ky[
                (df_ky["san_pham"] == sp)
                & (df_ky["cohort_month"] <= cohort_max)
            ]
            d = sp_ky.loc[sp_ky["trang_thai"] == "da_thu",           "so_gcn"].sum()
            q = sp_ky.loc[sp_ky["trang_thai"] == "chua_thu_qua_han", "so_gcn"].sum()
            tl = d / (d + q) * 100 if (d + q) > 0 else 0

            sp_m = df_month[
                df_month["san_pham"].eq(sp)
                & df_month["thang_tra_ky_k"].lt(cutoff_month)
            ]
            avg_by_ky_sp = sp_m[sp_m["ky"].between(2, 11)].groupby("ky")["ty_le_giu_chan_pct"].mean()
            best_ky_sp = int(avg_by_ky_sp.idxmax()) if not avg_by_ky_sp.empty else None
            best_ky_ret_sp = float(avg_by_ky_sp.max()) if not avg_by_ky_sp.empty else None
            ret_all = sp_m[sp_m["ky"].between(2, 11)]["ty_le_giu_chan_pct"].mean()

            dp_ky_val = None
            dp_ret = None
            avg_by_ky = sp_m[sp_m["ky"].between(2, 11)].groupby("ky")["ty_le_giu_chan_pct"].mean()
            if not avg_by_ky.empty:
                dp_ky_val = int(avg_by_ky.idxmin())
                dp_ret = avg_by_ky.min()

            # Q2: sức khỏe danh mục tháng mature gần nhất (cùng logic scorecard)
            sp_h = (
                df_health[
                    (df_health["san_pham"] == sp)
                    & (df_health["thang"] == mature_month)
                ]
                if mature_month is not None else pd.DataFrame()
            )
            if not sp_h.empty and sp_h["hieu_luc"].notna().any():
                gcn_paying = int(sp_h["distinct_gcn"].iloc[0])
                hl = int(sp_h["hieu_luc"].iloc[0])
                ty_le_active_sp = f"{gcn_paying / hl * 100:.1f}%" if hl > 0 else "—"
            else:
                ty_le_active_sp = "—"

            rows.append({
                "Sản phẩm":            sp,
                "Thu phí theo Tháng hiệu lực (%)": f"{tl:.1f}",
                "HĐ đã thu":           f"{int(d):,}",
                "HĐ quá hạn":          f"{int(q):,}",
                "Thu phí theo Tháng thu phí (%)": ty_le_active_sp,
                "Kỳ thu phí tốt nhất": f"Kỳ {best_ky_sp}→{best_ky_sp+1} ({best_ky_ret_sp:.1f}%)" if best_ky_sp else "—",
                "Kỳ dễ nghỉ nhất":     f"Kỳ {dp_ky_val}→{dp_ky_val+1} ({dp_ret:.1f}%)" if dp_ky_val else "—",
                "Duy trì đóng phí TB (%)": f"{ret_all:.1f}" if pd.notna(ret_all) else "—",
            })

        if rows:
            st.dataframe(
                pd.DataFrame(rows).set_index("Sản phẩm"),
                use_container_width=True,
            )


# ── Tab Q1: Hiệu quả thu trong kỳ ────────────────────────────────────────────

def _render_q1_tab(df_ky: pd.DataFrame, products: list[str]) -> None:
    st.markdown(
        "**Câu hỏi:** Trong số hợp đồng đã đến hạn phải trả, bao nhiêu % thực sự đã trả?\n\n"
        "_Chỉ tính từ kỳ 2 trở đi — kỳ 1 luôn đạt 100% vì tất cả HĐ mới đều bắt đầu từ đây._"
    )

    import numpy as np

    df = df_ky[df_ky["san_pham"].isin(products) & (df_ky["ky"] >= 2)].copy()
    if df.empty:
        st.info("Không có dữ liệu.")
        return

    # ── Heatmap: Tỉ lệ thu thành công theo tháng hiệu lực ───────────────────
    st.markdown("##### Tỉ lệ thu thành công theo tháng hiệu lực")
    st.caption(
        "Mỗi ô = tỉ lệ hợp đồng đã thu / (đã thu + quá hạn chưa thu) cho tháng hiệu lực đó ở kỳ đó. "
        "Vùng trống góc phải = kỳ chưa đến hạn với các hợp đồng mới."
    )

    grp_hm = (
        df.groupby(["san_pham", "cohort_month", "ky", "trang_thai"])["so_gcn"]
        .sum()
        .reset_index()
    )
    wide_hm = grp_hm.pivot_table(
        index=["san_pham", "cohort_month", "ky"],
        columns="trang_thai",
        values="so_gcn",
        aggfunc="sum",
    ).fillna(0).reset_index()
    wide_hm.columns.name = None
    if "da_thu" not in wide_hm.columns:
        wide_hm["da_thu"] = 0
    if "chua_thu_qua_han" not in wide_hm.columns:
        wide_hm["chua_thu_qua_han"] = 0

    da_hm   = np.array(wide_hm["da_thu"].fillna(0), dtype=float)
    chua_hm = np.array(wide_hm["chua_thu_qua_han"].fillna(0), dtype=float)
    tong_hm = da_hm + chua_hm
    wide_hm["ty_le"] = np.where(
        tong_hm > 0,
        np.round(da_hm / np.where(tong_hm > 0, tong_hm, 1.0), 4),
        np.nan,
    )
    wide_hm["cohort_str"]    = wide_hm["cohort_month"].dt.strftime("%Y-%m")
    wide_hm["ty_le_pct_str"] = wide_hm["ty_le"].apply(
        lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
    )

    n_hm = len(wide_hm["san_pham"].unique())
    cols_hm = st.columns(min(n_hm, 2))
    for i, sp in enumerate(sorted(wide_hm["san_pham"].unique())):
        sp_df = wide_hm[wide_hm["san_pham"] == sp].copy()
        with cols_hm[i % 2]:
            st.markdown(f"**{sp}**")
            hm_chart = (
                alt.Chart(sp_df)
                .mark_rect(stroke="white", strokeWidth=0.5)
                .encode(
                    x=alt.X(
                        "cohort_str:O",
                        title="Tháng hiệu lực",
                        sort="ascending",
                        axis=alt.Axis(labelAngle=-45),
                    ),
                    y=alt.Y(
                        "ky:O",
                        title="Kỳ thu phí",
                        sort="descending",
                    ),
                    color=alt.Color(
                        "ty_le:Q",
                        scale=_retention_color_scale(),
                        title="Tỉ lệ thu",
                        legend=alt.Legend(format=".0%"),
                    ),
                    tooltip=[
                        alt.Tooltip("cohort_str:N", title="Tháng HĐ hiệu lực"),
                        alt.Tooltip("ky:O", title="Kỳ"),
                        alt.Tooltip("ty_le_pct_str:N", title="Tỉ lệ thu"),
                        alt.Tooltip("da_thu:Q", title="Đã thu", format=","),
                        alt.Tooltip("chua_thu_qua_han:Q", title="Quá hạn chưa thu", format=","),
                    ],
                )
                .properties(height=max(200, len(sp_df["ky"].unique()) * 30 + 60))
            )
            st.altair_chart(hm_chart, use_container_width=True)

    # ── Chart 2: Tỉ lệ thu theo từng kỳ ─────────────────────────────────────
    st.markdown("##### Tỉ lệ thu theo từng kỳ")
    st.caption("Tổng hợp tất cả các tháng. Cho thấy kỳ nào khó thu nhất.")

    grp_ky = (
        df.groupby(["san_pham", "ky", "trang_thai"])["so_gcn"]
        .sum()
        .reset_index()
    )
    wide_ky = grp_ky.pivot_table(
        index=["san_pham", "ky"],
        columns="trang_thai",
        values="so_gcn",
        aggfunc="sum",
    ).fillna(0).reset_index()
    wide_ky.columns.name = None
    if "da_thu" not in wide_ky.columns:
        wide_ky["da_thu"] = 0
    if "chua_thu_qua_han" not in wide_ky.columns:
        wide_ky["chua_thu_qua_han"] = 0
    da_k = np.array(wide_ky["da_thu"], dtype=float)
    to_k = da_k + np.array(wide_ky["chua_thu_qua_han"], dtype=float)
    wide_ky["ty_le_pct"]   = np.where(to_k > 0, np.round(da_k / to_k * 100, 1), np.nan)
    wide_ky["da_thu_fmt"]  = wide_ky["da_thu"].apply(lambda x: f"{int(x):,}")
    wide_ky["qua_han_fmt"] = wide_ky["chua_thu_qua_han"].apply(lambda x: f"{int(x):,}")

    bar_chart = (
        alt.Chart(wide_ky)
        .mark_bar()
        .encode(
            x=alt.X("ky:O", title="Kỳ", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "ty_le_pct:Q",
                title="Tỉ lệ thu (%)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(
                "san_pham:N",
                title="Sản phẩm",
                scale=alt.Scale(
                    domain=list(_PRODUCT_COLORS.keys()),
                    range=list(_PRODUCT_COLORS.values()),
                ),
            ),
            xOffset="san_pham:N",
            tooltip=[
                alt.Tooltip("san_pham:N", title="Sản phẩm"),
                alt.Tooltip("ky:O", title="Kỳ"),
                alt.Tooltip("ty_le_pct:Q", title="Tỉ lệ thu (%)", format=".1f"),
                alt.Tooltip("da_thu_fmt:N", title="Đã thu"),
                alt.Tooltip("qua_han_fmt:N", title="Quá hạn chưa thu"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(bar_chart, use_container_width=True)


# ── Tab Q2: Sức khỏe danh mục ────────────────────────────────────────────────

def _render_q2_tab(df_health: pd.DataFrame, products: list[str]) -> None:
    st.markdown(
        "**Câu hỏi:** Trong toàn bộ hợp đồng đang có hiệu lực, "
        "bao nhiêu % đang thực sự đóng phí?\n\n"
        "_Tử số: số HĐ unique đã trả ≥1 kỳ trong tháng. "
        "Mẫu số: số HĐ đang có hiệu lực cuối tháng._"
    )

    df = df_health[
        df_health["san_pham"].isin(products)
        & df_health["hieu_luc"].notna()
        & (df_health["hieu_luc"] > 0)
    ].copy()
    if df.empty:
        st.info("Không có dữ liệu.")
        return

    df["ty_le_pct"] = (df["distinct_gcn"] / df["hieu_luc"] * 100).round(1)
    df["thang_str"] = df["thang"].dt.strftime("%m/%Y")
    df["gcn_fmt"]   = df["distinct_gcn"].apply(lambda x: f"{int(x):,}")
    df["hl_fmt"]    = df["hieu_luc"].apply(lambda x: f"{int(x):,}")

    # ── Chart 1: Xu hướng theo tháng ─────────────────────────────────────────
    st.markdown("##### Tỷ lệ thu phí theo tháng thu phí")
    st.caption("% HĐ đang đóng phí / HĐ có hiệu lực theo từng tháng và sản phẩm.")

    trend = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("thang:T",
                    timeUnit="yearmonth",
                    axis=alt.Axis(format="%m/%Y", labelAngle=-45, title=None)),
            y=alt.Y(
                "ty_le_pct:Q",
                title="% HĐ đang đóng phí",
                scale=alt.Scale(zero=False),
            ),
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
                alt.Tooltip("thang_str:N", title="Tháng"),
                alt.Tooltip("ty_le_pct:Q", title="% đang đóng phí", format=".1f"),
                alt.Tooltip("gcn_fmt:N", title="HĐ đang đóng phí"),
                alt.Tooltip("hl_fmt:N", title="HĐ có hiệu lực"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(trend, use_container_width=True)

    # ── Chart 2: So sánh tháng gần nhất ──────────────────────────────────────
    df_latest = df[df["thang"] == df["thang"].max()]

    if not df_latest.empty:
        latest_label = df_latest["thang_str"].iloc[0]
        st.markdown(f"##### So sánh theo sản phẩm — tháng {latest_label}")

        bar = (
            alt.Chart(df_latest)
            .mark_bar()
            .encode(
                x=alt.X(
                    "san_pham:N",
                    title="Sản phẩm",
                    sort=alt.SortField("ty_le_pct", order="descending"),
                ),
                y=alt.Y(
                    "ty_le_pct:Q",
                    title="% HĐ đang đóng phí",
                    scale=alt.Scale(zero=False),
                ),
                color=alt.Color(
                    "san_pham:N",
                    scale=alt.Scale(
                        domain=list(_PRODUCT_COLORS.keys()),
                        range=list(_PRODUCT_COLORS.values()),
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("san_pham:N", title="Sản phẩm"),
                    alt.Tooltip("ty_le_pct:Q", title="% đang đóng phí", format=".1f"),
                    alt.Tooltip("gcn_fmt:N", title="HĐ đang đóng phí"),
                    alt.Tooltip("hl_fmt:N", title="HĐ có hiệu lực"),
                ],
            )
            .properties(height=280)
        )
        text = bar.mark_text(align="center", baseline="bottom", dy=-4).encode(
            text=alt.Text("ty_le_pct:Q", format=".1f"),
        )
        st.altair_chart((bar + text), use_container_width=True)


# ── Retention Curve ───────────────────────────────────────────────────────────

def _render_retention_curve(df_retention: pd.DataFrame, products: list[str], min_gcn: int):
    st.markdown("#### Tỷ lệ GCN còn thu phí qua từng kỳ")
    st.caption(
        "Kỳ 2 = 100% (tất cả HĐ bắt đầu đóng phí). "
        "Cột xanh = % còn lại (tích lũy), cột đỏ = % bị mất tại kỳ đó. "
        "Chỉ tính GCN có kỳ k+1 đã đến hạn (tính theo ngày hiệu lực thực tế)."
    )

    df = df_retention[df_retention["san_pham"].isin(products)].copy()
    if df.empty:
        st.info("Không có dữ liệu.")
        return

    n_products = len(df["san_pham"].unique())
    cols = st.columns(min(n_products, 2))

    for i, sp in enumerate(sorted(df["san_pham"].unique())):
        sp_df = df[df["san_pham"] == sp].copy()

        # retention_pct đã là tỷ lệ chính xác theo GCN thực tế (không dùng MEAN)
        avg_rates = sp_df.set_index("ky")["retention_pct"].sort_index()

        # Xây dữ liệu waterfall: mỗi kỳ có (con_lai, mat, prev)
        wf_rows = [{"ky_label": "Kỳ 2", "con_lai": 100.0, "mat": 0.0, "prev": 100.0}]
        surv = 100.0
        for ky, rate in avg_rates.items():
            prev = surv
            surv = surv * rate / 100
            drop = prev - surv
            wf_rows.append({
                "ky_label": f"Kỳ {int(ky) + 1}",
                "con_lai": round(surv, 1),
                "mat": round(drop, 1),
                "prev": round(prev, 1),
            })
        wf_df = pd.DataFrame(wf_rows)
        ky_order = list(wf_df["ky_label"])

        # Cột xanh: từ 0 đến con_lai
        bar_remain = (
            alt.Chart(wf_df)
            .mark_bar(color="#2ca02c", opacity=0.85)
            .encode(
                x=alt.X("ky_label:N", title="Kỳ thu phí", sort=ky_order, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("con_lai:Q", title="% GCN", scale=alt.Scale(domain=[0, 112])),
                y2=alt.Y2(datum=0),
                tooltip=[
                    alt.Tooltip("ky_label:N", title="Kỳ"),
                    alt.Tooltip("con_lai:Q", title="% còn lại (tích lũy)", format=".1f"),
                ],
            )
        )

        # Cột đỏ nổi: từ con_lai đến prev (phần bị mất tại kỳ đó)
        wf_lost = wf_df[wf_df["mat"] > 0.05]
        bar_lost = (
            alt.Chart(wf_lost)
            .mark_bar(color="#d62728", opacity=0.75)
            .encode(
                x=alt.X("ky_label:N", sort=ky_order),
                y=alt.Y("prev:Q"),
                y2=alt.Y2("con_lai:Q"),
                tooltip=[
                    alt.Tooltip("ky_label:N", title="Kỳ"),
                    alt.Tooltip("mat:Q", title="% bị mất tại kỳ này", format=".1f"),
                    alt.Tooltip("con_lai:Q", title="% còn lại (tích lũy)", format=".1f"),
                ],
            )
        )

        # Label con_lai: giữa cột xanh
        labels = (
            alt.Chart(wf_df)
            .mark_text(fontSize=11, fontWeight="bold", color="white")
            .encode(
                x=alt.X("ky_label:N", sort=ky_order),
                y=alt.Y("y_mid:Q"),
                text=alt.Text("con_lai:Q", format=".1f"),
            )
            .transform_calculate(y_mid="datum.con_lai / 2")
        )

        # Label mat: giữa cột đỏ
        labels_lost = (
            alt.Chart(wf_lost)
            .mark_text(fontSize=9, color="white", fontWeight="bold")
            .encode(
                x=alt.X("ky_label:N", sort=ky_order),
                y=alt.Y("y_mid:Q"),
                text=alt.Text("mat:Q", format=".1f"),
            )
            .transform_calculate(y_mid="(datum.con_lai + datum.prev) / 2")
        )

        chart = (bar_remain + bar_lost + labels + labels_lost).properties(title=sp, height=300)
        with cols[i % 2]:
            st.altair_chart(chart, use_container_width=True)


# ── Chart 3: Day-of-Month Heatmap ────────────────────────────────────────────

# ── Tab: Trạng thái thu phí theo ngày ───────────────────────────────────────

_MONTH_NAMES = {
    1: "Tháng 1", 2: "Tháng 2", 3: "Tháng 3", 4: "Tháng 4",
    5: "Tháng 5", 6: "Tháng 6", 7: "Tháng 7", 8: "Tháng 8",
    9: "Tháng 9", 10: "Tháng 10", 11: "Tháng 11", 12: "Tháng 12",
}


def _render_payment_date_table(df_date: pd.DataFrame, products: list[str]) -> None:
    st.markdown("#### Trạng thái thu phí theo ngày")

    df_filtered = df_date[df_date["san_pham"].isin(products)].copy()

    # ── Filters: Năm | Tháng | Kỳ thu phí ───────────────────────────────────
    available_years = sorted(df_filtered["ngay_tra_ky_k"].dt.year.unique(), reverse=True)

    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        selected_year = st.selectbox(
            "Năm", options=available_years, index=0, key="pdt_year",
        )
    with fc2:
        months_in_year = sorted(
            df_filtered[df_filtered["ngay_tra_ky_k"].dt.year == selected_year][
                "ngay_tra_ky_k"
            ].dt.month.unique(),
            reverse=True,
        )
        _prev_month_num = (pd.Timestamp.now() - pd.DateOffset(months=1)).month
        _default_month_idx = (
            months_in_year.index(_prev_month_num)
            if _prev_month_num in months_in_year
            else 0
        )
        selected_month = st.selectbox(
            "Tháng", options=months_in_year, index=_default_month_idx, key="pdt_month",
            format_func=lambda m: _MONTH_NAMES.get(m, f"Tháng {m}"),
        )

    # Data cả tháng — dùng cho charts và bảng
    df_month_data = df_filtered[
        (df_filtered["ngay_tra_ky_k"].dt.year == selected_year)
        & (df_filtered["ngay_tra_ky_k"].dt.month == selected_month)
    ].copy()

    with fc3:
        available_ky = sorted(df_month_data["ky"].unique())
        ky_min_avail = int(available_ky[0]) if available_ky else 2
        ky_max_avail = int(available_ky[-1]) if available_ky else 11
        ky_range = st.slider(
            "Kỳ thu phí",
            min_value=ky_min_avail,
            max_value=ky_max_avail,
            value=(ky_min_avail, ky_max_avail),
            key="pdt_ky",
            format="Kỳ %d",
        )

    if df_month_data.empty:
        st.info("Không có dữ liệu cho tháng và năm đã chọn.")
        return

    ky_lo, ky_hi = ky_range
    df_chart = df_month_data[
        df_month_data["ky"].between(ky_lo, ky_hi)
    ].copy()
    df_chart["ngay"] = df_chart["ngay_tra_ky_k"].dt.day

    ky_label = f"Kỳ {ky_lo}–{ky_hi}" if ky_lo != ky_hi else f"Kỳ {ky_lo}"

    # ── Biểu đồ ─────────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    # Chart 1: Stacked bar — Số GCN đã/chưa thu kỳ tiếp
    with col_left:
        st.markdown(f"##### Số GCN theo ngày — {ky_label}")
        agg = (
            df_chart.groupby("ngay")
            .agg(da_thu=("da_tra_ky_tiep", "sum"), chua_thu=("chua_tra_ky_tiep", "sum"))
            .reset_index()
        )
        melted = agg.melt(
            id_vars=["ngay"],
            value_vars=["da_thu", "chua_thu"],
            var_name="trang_thai",
            value_name="so_gcn",
        )
        melted["trang_thai"] = melted["trang_thai"].map(
            {"da_thu": "Đã thu kỳ tiếp", "chua_thu": "Chưa thu kỳ tiếp"}
        )
        bar = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("ngay:O", title="Ngày", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("so_gcn:Q", title="Số GCN", stack="zero"),
                color=alt.Color(
                    "trang_thai:N",
                    title="Trạng thái",
                    scale=alt.Scale(
                        domain=["Đã thu kỳ tiếp", "Chưa thu kỳ tiếp"],
                        range=["#2ca02c", "#d62728"],
                    ),
                    legend=alt.Legend(orient="bottom"),
                ),
                tooltip=[
                    alt.Tooltip("ngay:O", title="Ngày"),
                    alt.Tooltip("trang_thai:N", title="Trạng thái"),
                    alt.Tooltip("so_gcn:Q", title="Số GCN", format=",d"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(bar, use_container_width=True)

    # Chart 2: Line — Tỉ lệ duy trì thu phí (chỉ is_mature)
    with col_right:
        st.markdown(f"##### Tỉ lệ duy trì thu phí — {ky_label}")
        df_line = df_chart[df_chart["is_mature"]].copy()
        if df_line.empty:
            st.info("Chưa có ngày nào đã quá 30 ngày trong tháng này.")
        else:
            line_agg = (
                df_line.groupby(["ngay", "san_pham"])
                .agg(da_thu=("da_tra_ky_tiep", "sum"), so_gcn=("so_gcn", "sum"))
                .reset_index()
            )
            line_agg["ty_le"] = (
                line_agg["da_thu"]
                / line_agg["so_gcn"].replace(0, float("nan"))
                * 100
            ).round(1)
            line_chart = (
                alt.Chart(line_agg)
                .mark_line(point=True, strokeWidth=2)
                .encode(
                    x=alt.X("ngay:O", title="Ngày", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "ty_le:Q",
                        title="Duy trì thu phí (%)",
                        scale=alt.Scale(zero=False),
                    ),
                    color=alt.Color(
                        "san_pham:N",
                        title="Sản phẩm",
                        scale=alt.Scale(
                            domain=list(_PRODUCT_COLORS.keys()),
                            range=list(_PRODUCT_COLORS.values()),
                        ),
                        legend=alt.Legend(orient="bottom"),
                    ),
                    tooltip=[
                        alt.Tooltip("san_pham:N", title="Sản phẩm"),
                        alt.Tooltip("ngay:O", title="Ngày"),
                        alt.Tooltip("ty_le:Q", title="Duy trì thu phí (%)", format=".1f"),
                        alt.Tooltip("so_gcn:Q", title="Số GCN", format=",d"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(line_chart, use_container_width=True)

    st.divider()

    # ── Bảng — lọc theo Kỳ + Ngày ────────────────────────────────────────────
    df_show = df_month_data[df_month_data["ky"].between(ky_lo, ky_hi)].copy()

    available_days = sorted(df_show["ngay_tra_ky_k"].dt.day.unique())
    day_min_avail = int(available_days[0]) if available_days else 1
    day_max_avail = int(available_days[-1]) if available_days else 31
    day_range = st.slider(
        "Ngày",
        min_value=day_min_avail,
        max_value=day_max_avail,
        value=(day_min_avail, day_max_avail),
        key="pdt_days",
    )
    day_lo, day_hi = day_range
    df_show = df_show[df_show["ngay_tra_ky_k"].dt.day.between(day_lo, day_hi)]

    if df_show.empty:
        st.info("Không có dữ liệu cho lựa chọn đã chọn.")
        return

    df_show["ngay_tra_ky_k"] = df_show["ngay_tra_ky_k"].dt.strftime("%d/%m/%Y")
    df_show = df_show.rename(columns={
        "san_pham": "Sản phẩm",
        "ngay_tra_ky_k": "Ngày thu phí",
        "ky": "Kỳ thu phí",
        "so_gcn": "Số GCN đã thu phí",
        "da_tra_ky_tiep": "Đã thu phí kỳ tiếp theo",
        "chua_tra_ky_tiep": "Chưa thu phí kỳ tiếp theo",
        "ty_le_giu_chan_pct": "Duy trì thu phí",
        "is_mature": "Đã quá 30 ngày",
    }).sort_values(["Sản phẩm", "Ngày thu phí", "Kỳ thu phí"])

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Sản phẩm": st.column_config.TextColumn(
                "Sản phẩm",
                help="Tên sản phẩm bảo hiểm.",
            ),
            "Ngày thu phí": st.column_config.TextColumn(
                "Ngày thu phí",
                help="Ngày thu phí kỳ k.",
            ),
            "Kỳ thu phí": st.column_config.NumberColumn(
                "Kỳ thu phí",
                help="Kỳ phí đã được thanh toán (kỳ 2 đến kỳ 11; kỳ 1 miễn phí không theo dõi).",
                format="%d",
            ),
            "Số GCN đã thu phí": st.column_config.NumberColumn(
                "Số GCN đã thu phí",
                help="Số giấy chứng nhận thu phí kỳ k vào ngày này.",
                format="%d",
            ),
            "Đã thu phí kỳ tiếp theo": st.column_config.NumberColumn(
                "Đã thu phí kỳ tiếp theo",
                help="Trong số GCN thu kỳ k, số GCN đã tiếp tục thu kỳ k+1 (bất kể ngày nào).",
                format="%d",
            ),
            "Chưa thu phí kỳ tiếp theo": st.column_config.NumberColumn(
                "Chưa thu phí kỳ tiếp theo",
                help="Trong số GCN thu kỳ k, số GCN chưa thu kỳ k+1 tính đến thời điểm truy vấn.",
                format="%d",
            ),
            "Duy trì thu phí": st.column_config.NumberColumn(
                "Duy trì thu phí",
                help=(
                    "Tỉ lệ GCN thu kỳ k tiếp tục thu kỳ k+1 (%).\n\n"
                    "Chỉ đáng tin cậy khi cột 'Đã quá 30 ngày' = ✓ "
                    "(tức là ngày thu phí + 30 ngày ≤ hôm nay, kỳ k+1 đã có đủ thời gian xảy ra)."
                ),
                format="%.1f",
            ),
            "Đã quá 30 ngày": st.column_config.CheckboxColumn(
                "Đã quá 30 ngày",
                help=(
                    "TRUE khi ngày thu phí + 30 ngày ≤ hôm nay, tức là kỳ k+1 "
                    "đã có đủ thời gian để xảy ra. "
                    "Các dòng chưa đủ 30 ngày có tỉ lệ duy trì bị bias thấp do dữ liệu chưa đầy đủ."
                ),
            ),
        },
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render_payment_retention_page():
    col_title, col_refresh = st.columns([9, 1])
    with col_title:
        st.markdown(
            '<h1 style="font-size:1.4rem;font-weight:700;margin-bottom:0.5rem;">'
            "PHÂN TÍCH THU PHÍ VÀ DUY TRÌ ĐÓNG PHÍ THEO KỲ</h1>",
            unsafe_allow_html=True,
        )
    with col_refresh:
        if st.button(
            "⟳ Làm mới",
            use_container_width=True,
            help="Xóa cache và tải lại dữ liệu mới nhất từ MotherDuck",
        ):
            load_all_payment_tracking.clear()
            load_portfolio_health.clear()
            load_payment_retention_by_ky_thu.clear()
            st.rerun()

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        df_ky, df_month, df_date = load_all_payment_tracking()
        df_health = load_portfolio_health()
        df_retention = load_payment_retention_by_ky_thu()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        st.info(
            "Chạy lệnh sau để xây dựng các bảng tracking:\n"
            "```\npython Scripts/transform_data/build_payment_tracking.py\n```"
        )
        return

    # ── Global filters ────────────────────────────────────────────────────────
    selected_products = st.segmented_control(
        "Sản phẩm",
        options=_PRODUCTS,
        default=_PRODUCTS,
        selection_mode="multi",
        key="ret_products",
    )

    f_col2, f_col3 = st.columns([3, 1])
    with f_col2:
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
            "Tối thiểu HĐ/ngày",
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
    _render_scorecard(df_ky, df_month, df_date, df_health, selected_products)

    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "Thu phí theo tháng hiệu lực",
        "Thu phí theo tháng thu phí",
        "Duy trì đóng phí theo kỳ",
        "Trạng thái thu phí theo ngày",
    ])

    with tab1:
        _render_q1_tab(df_ky, selected_products)

    with tab2:
        _render_q2_tab(df_health, selected_products)

    with tab3:
        _render_retention_curve(df_retention, selected_products, min_gcn)

    with tab4:
        _render_payment_date_table(df_date, selected_products)
