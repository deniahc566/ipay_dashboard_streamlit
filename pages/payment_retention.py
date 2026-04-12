"""
payment_retention.py
---------------------
Trang phân tích tỉ lệ thu phí và duy trì đóng phí theo kỳ.

7 tab:
  1. Hiệu quả thu trong kỳ — Q1: trong số HĐ đến hạn, bao nhiêu % đã thu?
  2. Sức khỏe danh mục     — Q2: trong số HĐ hiệu lực, bao nhiêu % đang đóng phí?
  3. Bản đồ thu phí        — tháng hiệu lực × kỳ, màu = tỉ lệ thu thành công
  4. Duy trì đóng phí theo kỳ — tỉ lệ tiếp tục đóng phí qua từng kỳ
  5. Xu hướng theo ngày    — trung bình 7 ngày
  6. Phân bố ngày trong tháng — ngày nào thu nhiều / duy trì tốt
  7. Dữ liệu chi tiết      — bảng lọc chi tiết
"""

import streamlit as st
import pandas as pd
import altair as alt

from data_loader import load_all_payment_tracking, load_portfolio_health
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

    # Q1 — Hiệu quả thu trong kỳ: chỉ dùng cohort 2–8 tháng trước
    # Tránh: cohort quá mới (chưa hết window thu) và cohort quá cũ (survivor bias)
    cohort_min = (pd.Timestamp.now() - pd.DateOffset(months=8)).to_period("M").to_timestamp()
    cohort_max = (pd.Timestamp.now() - pd.DateOffset(months=2)).to_period("M").to_timestamp()
    fky_q1 = fky[fky["cohort_month"].between(cohort_min, cohort_max)]

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

    # Q2 — Sức khỏe danh mục: distinct GCN đang đóng phí / GCN có hiệu lực
    # Dùng tháng mature gần nhất (60 ngày trước để đảm bảo đủ data)
    mature_month = (
        (pd.Timestamp.now().normalize() - pd.Timedelta(days=60))
        .to_period("M").to_timestamp()
    )
    dh = df_health[
        df_health["san_pham"].isin(products)
        & (df_health["thang"] == mature_month)
    ]
    active_gcn     = int(dh["distinct_gcn"].sum()) if not dh.empty else None
    active_hieu_luc = int(dh["hieu_luc"].sum())    if not dh.empty and dh["hieu_luc"].notna().any() else None
    ty_le_active   = (
        active_gcn / active_hieu_luc * 100
        if active_gcn and active_hieu_luc and active_hieu_luc > 0
        else None
    )
    active_month_label = mature_month.strftime("%m/%Y")

    return dict(
        da_thu=int(da_thu), qua_han=int(qua_han), tong=int(tong),
        ty_le=ty_le, ty_le_delta=ty_le_delta,
        ret_ky2=ret_ky2, ret_delta=ret_delta,
        ret_overall=ret_overall,
        dropoff_ky=dropoff_ky, dropoff_val=dropoff_val,
        active_gcn=active_gcn, active_hieu_luc=active_hieu_luc,
        ty_le_active=ty_le_active, active_month_label=active_month_label,
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
            label="HIỆU QUẢ THU PHÍ",
            value=f"{m['ty_le']:.1f}%",
            delta_str=ty_le_delta_str or "—",
            delta_color=ty_le_delta_color,
            accent_color="#1565C0",
            subtitle=f"Nhóm HĐ hiệu lực 2–8 tháng trước · {m['da_thu']:,}/{m['tong']:,} HĐ",
            tooltip="Trong số các hợp đồng đã đến hạn phải trả kỳ này, "
                    "bao nhiêu % thực sự đã trả? "
                    "Chỉ tính nhóm hiệu lực 2–8 tháng trước để loại bỏ "
                    "nhóm quá mới (chưa đủ thời gian thu) và nhóm quá cũ (ít biến động).",
        ), unsafe_allow_html=True)

    # Card 2: HĐ quá hạn
    qh_pct = m["qua_han"] / m["tong"] * 100 if m["tong"] > 0 else 0
    with c2:
        st.markdown(kpi_card(
            label="HỢP ĐỒNG QUÁ HẠN CHƯA THU",
            value=f"{m['qua_han']:,}",
            delta_str=f"{qh_pct:.1f}% tổng hợp đồng đang theo dõi",
            delta_color="#c62828" if qh_pct > 30 else "#e65100" if qh_pct > 15 else "#2e7d32",
            accent_color="#b71c1c",
            subtitle=f"Tổng {m['tong']:,} hợp đồng đang theo dõi",
        ), unsafe_allow_html=True)

    # Card 3: Duy trì đóng phí K2→3
    ret_str = f"{m['ret_ky2']:.1f}%" if m["ret_ky2"] is not None else "—"
    ret_delta_str = ""
    ret_delta_color = "#888"
    if m["ret_delta"] is not None:
        sign = "▲" if m["ret_delta"] >= 0 else "▼"
        ret_delta_color = "#2e7d32" if m["ret_delta"] >= 0 else "#c62828"
        ret_delta_str = f"{sign} {abs(m['ret_delta']):.1f} điểm % so với tháng trước"

    with c3:
        st.markdown(kpi_card(
            label="DUY TRÌ ĐÓNG PHÍ K2→3",
            value=ret_str,
            delta_str=ret_delta_str or "—",
            delta_color=ret_delta_color,
            accent_color="#1b5e20",
            subtitle="Trung bình các tháng có đủ dữ liệu",
            tooltip="Trong 100 hợp đồng đã trả kỳ 2, có bao nhiêu hợp đồng tiếp tục trả kỳ 3?",
        ), unsafe_allow_html=True)

    # Card 4: Kỳ duy trì thấp nhất
    if m["dropoff_ky"] is not None:
        dropoff_val_str = f"{m['dropoff_val']:.1f}%" if m["dropoff_val"] is not None else "—"
        dropoff_display = f"Kỳ {m['dropoff_ky']} → {m['dropoff_ky'] + 1}"
        dropoff_sub = f"Duy trì: {dropoff_val_str}"
    else:
        dropoff_display = "—"
        dropoff_sub = "Chưa đủ dữ liệu"

    with c4:
        st.markdown(kpi_card(
            label="KỲ DỄ NGHỈ NHẤT",
            value=dropoff_display,
            delta_str=f"Duy trì: {dropoff_val_str if m['dropoff_ky'] else '—'}",
            delta_color="#e65100",
            accent_color="#e65100",
            subtitle="Kỳ khách hàng dễ dừng đóng phí nhất",
            tooltip="Kỳ mà tỉ lệ tiếp tục đóng phí thấp nhất, tính trên các tháng đã có đủ dữ liệu (kỳ 2–11).",
        ), unsafe_allow_html=True)

    # Card 5: Q2 — Sức khỏe danh mục
    with c5:
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
        else:
            active_val   = "—"
            active_sub   = "Chưa đủ dữ liệu"
            active_color = "#888"
        st.markdown(kpi_card(
            label="SỨC KHỎE DANH MỤC",
            value=active_val,
            delta_str=active_sub,
            delta_color=active_color,
            accent_color="#6a1b9a",
            subtitle="HĐ đang đóng phí / HĐ đang có hiệu lực",
            tooltip="Số hợp đồng đã trả ít nhất 1 kỳ trong tháng / Số hợp đồng đang hiệu lực. "
                    "Lưu ý: số HĐ hiệu lực của Cyber Risk không cập nhật từ đầu năm 2026.",
        ), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── Row 2: Per-product breakdown ──────────────────────────────────────────
    with st.expander("Chi tiết theo sản phẩm", expanded=True):
        rows = []
        cohort_min = (pd.Timestamp.now() - pd.DateOffset(months=8)).to_period("M").to_timestamp()
        cohort_max = (pd.Timestamp.now() - pd.DateOffset(months=2)).to_period("M").to_timestamp()
        cutoff_month = (pd.Timestamp.now() - pd.DateOffset(months=1)).to_period("M").to_timestamp()
        mature_month = (
            (pd.Timestamp.now().normalize() - pd.Timedelta(days=60))
            .to_period("M").to_timestamp()
        )

        for sp in sorted(products):
            # Q1: chỉ dùng cohort 2–8 tháng trước
            sp_ky = df_ky[
                (df_ky["san_pham"] == sp)
                & df_ky["cohort_month"].between(cohort_min, cohort_max)
            ]
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

            # Q2: sức khỏe danh mục tháng mature gần nhất
            sp_h = df_health[
                (df_health["san_pham"] == sp)
                & (df_health["thang"] == mature_month)
            ]
            if not sp_h.empty and sp_h["hieu_luc"].notna().any():
                gcn_paying = int(sp_h["distinct_gcn"].iloc[0])
                hl = int(sp_h["hieu_luc"].iloc[0])
                ty_le_active_sp = f"{gcn_paying / hl * 100:.1f}%" if hl > 0 else "—"
            else:
                ty_le_active_sp = "—"

            rows.append({
                "Sản phẩm":            sp,
                "Hiệu quả thu (%)":    f"{tl:.1f}",
                "HĐ đã thu":           f"{int(d):,}",
                "HĐ quá hạn":          f"{int(q):,}",
                "Sức khỏe danh mục":   ty_le_active_sp,
                "Duy trì đóng phí K2→3 (%)": f"{ret2:.1f}" if pd.notna(ret2) else "—",
                "Duy trì đóng phí TB (%)":   f"{ret_all:.1f}" if pd.notna(ret_all) else "—",
                "Kỳ dễ nghỉ nhất":     f"Kỳ {dp_ky_val}→{dp_ky_val+1} ({dp_ret:.1f}%)" if dp_ky_val else "—",
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

    # ── Chart 1: Xu hướng theo tháng hiệu lực ────────────────────────────────
    st.markdown("##### Xu hướng tỉ lệ thu theo tháng")
    st.caption(
        "Tỉ lệ thu tổng hợp (kỳ 2+) theo tháng HĐ hiệu lực. "
        "Tháng gần nhất bị ẩn vì chưa đủ dữ liệu (HĐ chưa đến hạn kỳ 2)."
    )

    grp = (
        df.groupby(["san_pham", "cohort_month", "trang_thai"])["so_gcn"]
        .sum()
        .reset_index()
    )
    wide = grp.pivot_table(
        index=["san_pham", "cohort_month"],
        columns="trang_thai",
        values="so_gcn",
        aggfunc="sum",
    ).fillna(0).reset_index()
    wide.columns.name = None
    if "da_thu" not in wide.columns:
        wide["da_thu"] = 0
    if "chua_thu_qua_han" not in wide.columns:
        wide["chua_thu_qua_han"] = 0
    da = np.array(wide["da_thu"], dtype=float)
    to = da + np.array(wide["chua_thu_qua_han"], dtype=float)
    wide["ty_le_pct"]   = np.where(to > 0, np.round(da / to * 100, 1), np.nan)
    wide["cohort_str"]  = wide["cohort_month"].dt.strftime("%m/%Y")
    wide["da_thu_fmt"]  = wide["da_thu"].apply(lambda x: f"{int(x):,}")
    wide["qua_han_fmt"] = wide["chua_thu_qua_han"].apply(lambda x: f"{int(x):,}")

    # Exclude cohorts < 2 months old — incomplete window
    cutoff_new = (pd.Timestamp.now() - pd.DateOffset(months=2)).to_period("M").to_timestamp()
    wide_trend = wide[wide["cohort_month"] <= cutoff_new].copy()

    trend_chart = (
        alt.Chart(wide_trend)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("cohort_month:T", title="Tháng HĐ hiệu lực"),
            y=alt.Y(
                "ty_le_pct:Q",
                title="Tỉ lệ thu (%)",
                scale=alt.Scale(domain=[0, 100]),
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
                alt.Tooltip("cohort_str:N", title="Tháng HĐ hiệu lực"),
                alt.Tooltip("ty_le_pct:Q", title="Tỉ lệ thu (%)", format=".1f"),
                alt.Tooltip("da_thu_fmt:N", title="Đã thu"),
                alt.Tooltip("qua_han_fmt:N", title="Quá hạn chưa thu"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(trend_chart, use_container_width=True)

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
                scale=alt.Scale(domain=[0, 100]),
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

    if "Cyber Risk" in products:
        st.warning(
            "**Lưu ý — Cyber Risk:** Số HĐ có hiệu lực không cập nhật từ đầu năm 2026 (lỗi API). "
            "Tỉ lệ Cyber Risk từ tháng 01/2026 trở đi chỉ mang tính tham khảo."
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
    st.markdown("##### Xu hướng sức khỏe danh mục theo tháng")
    st.caption("% HĐ đang đóng phí / HĐ có hiệu lực theo từng tháng và sản phẩm.")

    trend = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("thang:T", title="Tháng"),
            y=alt.Y(
                "ty_le_pct:Q",
                title="% HĐ đang đóng phí",
                scale=alt.Scale(domain=[0, 100]),
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
    mature_month = (
        (pd.Timestamp.now().normalize() - pd.Timedelta(days=60))
        .to_period("M").to_timestamp()
    )
    df_latest = df[df["thang"] == mature_month]
    if df_latest.empty:
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
                    scale=alt.Scale(domain=[0, 100]),
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


# ── Chart 1: Cohort Heatmap ───────────────────────────────────────────────────

def _render_cohort_heatmap(df_ky: pd.DataFrame, products: list[str]):
    st.markdown("#### Tỉ lệ thu thành công theo tháng hiệu lực")
    st.caption(
        "Mỗi ô = tỉ lệ hợp đồng **đã thu** / (đã thu + quá hạn chưa thu) cho tháng đó ở kỳ đó. "
        "Vùng trống góc trên-phải = kỳ chưa đến hạn với các hợp đồng mới."
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
                        alt.Tooltip("cohort_str:N", title="Tháng HĐ hiệu lực"),
                        alt.Tooltip("ky:O", title="Kỳ"),
                        alt.Tooltip("ty_le_pct_str:N", title="Tỉ lệ thu"),
                        alt.Tooltip("da_thu:Q", title="Đã thu", format=","),
                        alt.Tooltip("chua_thu_qua_han:Q", title="Quá hạn chưa thu", format=","),
                    ],
                )
                .properties(height=max(200, len(sp_df["cohort_str"].unique()) * 24 + 60))
            )
            st.altair_chart(chart, use_container_width=True)


# ── Chart 2: Retention Curve ─────────────────────────────────────────────────

def _render_retention_curve(df_month: pd.DataFrame, products: list[str], min_gcn: int):
    st.info(
        "**Lưu ý:** Tab này trả lời câu hỏi **khác** với tab 'Hiệu quả thu trong kỳ'.\n\n"
        "- **Hiệu quả thu:** Trong số HĐ ĐẾN HẠN kỳ này → bao nhiêu % đã thu được?\n"
        "- **Tab này:** Trong số HĐ đã trả kỳ k tháng M → bao nhiêu % tiếp tục trả kỳ k+1?"
    )
    st.markdown("#### Duy trì đóng phí qua từng kỳ")
    st.caption(
        "Mỗi đường mờ = 1 tháng. Đường đậm = trung bình. "
        "Ví dụ: điểm (kỳ=3, 85%) nghĩa là 85% hợp đồng đã trả kỳ 2 tiếp tục trả kỳ 3."
    )

    df = df_month[df_month["san_pham"].isin(products)].copy()
    if df.empty:
        st.info("Không có dữ liệu.")
        return

    # Tháng M đủ mature khi ngày cuối tháng + 30 ngày đã qua
    # (đảm bảo kỳ k+1 có đủ thời gian để được thu)
    # Điều kiện: last_day(M) + 30 ngày <= hôm nay ≈ M_start + 60 ngày <= hôm nay
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
    df_old = df[df["thang_tra_ky_k"] <= cutoff].copy()
    if df_old.empty:
        st.info("Chưa đủ dữ liệu lịch sử (cần ít nhất 1 tháng có đủ thời gian thu).")
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
                    title="Duy trì đóng phí (%)",
                    scale=alt.Scale(domain=[0, 105]),
                ),
                detail="thang_str:N",
                tooltip=[
                    alt.Tooltip("thang_str:N", title="Tháng"),
                    alt.Tooltip("ky:O", title="Kỳ"),
                    alt.Tooltip("ty_le_giu_chan_pct:Q", title="Duy trì đóng phí (%)", format=".1f"),
                    alt.Tooltip("so_gcn:Q", title="Số HĐ", format=","),
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
                        title="Duy trì đóng phí TB (%)",
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
    st.markdown("#### Xu hướng duy trì đóng phí theo ngày (trung bình 7 ngày)")
    st.caption(
        "Tỉ lệ tiếp tục đóng phí qua kỳ, trung bình trượt 7 ngày. Chỉ tính ngày có ≥ "
        f"{min_gcn:,} hợp đồng để tránh nhiễu từ ngày ít giao dịch."
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
            alt.Tooltip("rolling_7:Q", title="Duy trì đóng phí TB 7 ngày (%)", format=".1f"),
            alt.Tooltip("ty_le_giu_chan_pct:Q", title="Duy trì đóng phí ngày (%)", format=".1f"),
            alt.Tooltip("so_gcn:Q", title="Số HĐ", format=","),
        ],
    )

    lines = base.mark_line(strokeWidth=2).encode(
        y=alt.Y("rolling_7:Q", title="Duy trì đóng phí TB 7 ngày (%)", scale=alt.Scale(zero=False)),
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
        st.markdown("#### Số HĐ thu theo ngày trong tháng")
        st.caption("Trung bình số hợp đồng thu phí theo ngày trong tháng × kỳ. "
                   "Cho thấy ngày nào dồn nhiều giao dịch nhất.")

    with col_right:
        st.markdown("#### Duy trì đóng phí theo ngày trong tháng")
        st.caption("Tỉ lệ duy trì đóng phí trung bình theo ngày trong tháng × kỳ. "
                   "Hợp đồng thu vào cuối tháng có duy trì thấp hơn không?")

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
                title="HĐ/ngày (TB)",
                legend=alt.Legend(format=".0f"),
            ),
            tooltip=[
                alt.Tooltip("ngay_trong_thang:O", title="Ngày"),
                alt.Tooltip("ky:O", title="Kỳ"),
                alt.Tooltip("avg_gcn:Q", title="Số HĐ trung bình/ngày", format=",.0f"),
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
                title="Duy trì đóng phí TB (%)",
                legend=alt.Legend(format=".2f"),
            ),
            tooltip=[
                alt.Tooltip("ngay_trong_thang:O", title="Ngày"),
                alt.Tooltip("ky:O", title="Kỳ"),
                alt.Tooltip("avg_retention:Q", title="Duy trì đóng phí TB (%)", format=".1f"),
                alt.Tooltip("avg_gcn:Q", title="Số HĐ trung bình/ngày", format=",.0f"),
            ],
        ).properties(height=300)
        st.altair_chart(ret_chart, use_container_width=True)


# ── Tab 5: Detail Tables ─────────────────────────────────────────────────────

def _render_detail_tables(
    df_ky: pd.DataFrame,
    df_month: pd.DataFrame,
    df_date: pd.DataFrame,
    products: list[str],
) -> None:

    # ── Bảng 1: Tháng hiệu lực × Kỳ (df_ky) ────────────────────────────────
    st.markdown("#### Tỉ lệ thu phí theo tháng hiệu lực × kỳ")

    b1c1, b1c2, b1c3 = st.columns([2, 2, 2])
    with b1c1:
        ky_products = st.multiselect(
            "Sản phẩm",
            options=products,
            default=products,
            key="dt_ky_products",
        )
    with b1c2:
        all_cohorts = sorted(df_ky["cohort_month"].dt.strftime("%Y-%m").unique())
        ky_cohorts = st.multiselect(
            "Tháng bắt đầu hiệu lực",
            options=all_cohorts,
            default=all_cohorts[-6:] if len(all_cohorts) >= 6 else all_cohorts,
            key="dt_ky_cohorts",
        )
    with b1c3:
        ky_ky = st.multiselect(
            "Kỳ",
            options=list(range(2, 13)),
            default=list(range(2, 13)),
            key="dt_ky_ky",
            format_func=lambda k: f"Kỳ {k}",
        )

    df_ky_f = df_ky[
        df_ky["san_pham"].isin(ky_products)
        & df_ky["cohort_month"].dt.strftime("%Y-%m").isin(ky_cohorts)
        & df_ky["ky"].isin(ky_ky)
    ].copy()

    if df_ky_f.empty:
        st.info("Không có dữ liệu.")
    else:
        wide = df_ky_f.pivot_table(
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
        wide["tong"] = wide["da_thu"] + wide["chua_thu_qua_han"]
        wide["ty_le_thu (%)"] = (
            wide["da_thu"] / wide["tong"].replace(0, float("nan")) * 100
        ).round(1)
        wide["cohort_month"] = wide["cohort_month"].dt.strftime("%Y-%m")
        wide = wide.rename(columns={
            "san_pham": "Sản phẩm",
            "cohort_month": "Tháng HĐ hiệu lực",
            "ky": "Kỳ",
            "da_thu": "Đã thu",
            "chua_thu_qua_han": "Quá hạn chưa thu",
            "tong": "Tổng",
        }).sort_values(["Sản phẩm", "Tháng HĐ hiệu lực", "Kỳ"])
        st.dataframe(wide, use_container_width=True, hide_index=True)

    st.divider()

    # ── Bảng 2: Duy trì đóng phí theo tháng (df_month) ──────────────────────
    st.markdown("#### Duy trì đóng phí tháng-qua-tháng")

    b2c1, b2c2, b2c3 = st.columns([2, 2, 2])
    with b2c1:
        mo_products = st.multiselect(
            "Sản phẩm",
            options=products,
            default=products,
            key="dt_mo_products",
        )
    with b2c2:
        mo_min, mo_max = (
            df_month["thang_tra_ky_k"].min().date(),
            df_month["thang_tra_ky_k"].max().date(),
        )
        mo_range = st.date_input(
            "Khoảng tháng",
            value=(mo_min, mo_max),
            min_value=mo_min,
            max_value=mo_max,
            key="dt_mo_range",
        )
    with b2c3:
        mo_ky = st.multiselect(
            "Kỳ",
            options=list(range(2, 12)),
            default=list(range(2, 12)),
            key="dt_mo_ky",
            format_func=lambda k: f"Kỳ {k}→{k+1}",
        )

    df_month_f = df_month[df_month["san_pham"].isin(mo_products) & df_month["ky"].isin(mo_ky)].copy()
    if isinstance(mo_range, (list, tuple)) and len(mo_range) == 2:
        df_month_f = df_month_f[
            df_month_f["thang_tra_ky_k"].between(
                pd.Timestamp(mo_range[0]), pd.Timestamp(mo_range[1])
            )
        ]

    if df_month_f.empty:
        st.info("Không có dữ liệu.")
    else:
        out = df_month_f.copy()
        out["thang_tra_ky_k"] = out["thang_tra_ky_k"].dt.strftime("%Y-%m")
        out = out.rename(columns={
            "san_pham": "Sản phẩm",
            "thang_tra_ky_k": "Tháng thu kỳ k",
            "ky": "Kỳ k",
            "so_gcn": "Số HĐ trả kỳ k",
            "ty_le_giu_chan_pct": "Duy trì đóng phí (%)",
        }).sort_values(["Sản phẩm", "Tháng thu kỳ k", "Kỳ k"])
        st.dataframe(out, use_container_width=True, hide_index=True)

    st.divider()

    # ── Bảng 3: Duy trì đóng phí theo ngày (df_date) ────────────────────────
    st.markdown("#### Duy trì đóng phí theo ngày")

    b3c1, b3c2, b3c3 = st.columns([2, 2, 2])
    with b3c1:
        da_products = st.multiselect(
            "Sản phẩm",
            options=products,
            default=products,
            key="dt_da_products",
        )
    with b3c2:
        da_min, da_max = (
            df_date["ngay_tra_ky_k"].min().date(),
            df_date["ngay_tra_ky_k"].max().date(),
        )
        da_range = st.date_input(
            "Khoảng ngày",
            value=(da_min, da_max),
            min_value=da_min,
            max_value=da_max,
            key="dt_da_range",
        )
    with b3c3:
        da_ky = st.multiselect(
            "Kỳ",
            options=list(range(2, 12)),
            default=list(range(2, 12)),
            key="dt_da_ky",
            format_func=lambda k: f"Kỳ {k}→{k+1}",
        )

    df_date_f = df_date[df_date["san_pham"].isin(da_products) & df_date["ky"].isin(da_ky)].copy()
    if isinstance(da_range, (list, tuple)) and len(da_range) == 2:
        df_date_f = df_date_f[
            df_date_f["ngay_tra_ky_k"].between(
                pd.Timestamp(da_range[0]), pd.Timestamp(da_range[1])
            )
        ]

    if df_date_f.empty:
        st.info("Không có dữ liệu.")
    else:
        out = df_date_f.copy()
        out["ngay_tra_ky_k"] = out["ngay_tra_ky_k"].dt.strftime("%d/%m/%Y")
        out = out.rename(columns={
            "san_pham": "Sản phẩm",
            "ngay_tra_ky_k": "Ngày thu kỳ k",
            "ky": "Kỳ k",
            "so_gcn": "Số HĐ trả kỳ k",
            "ty_le_giu_chan_pct": "Duy trì đóng phí (%)",
        }).sort_values(["Sản phẩm", "Ngày thu kỳ k", "Kỳ k"])
        st.dataframe(out, use_container_width=True, hide_index=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render_payment_retention_page():
    st.markdown(
        '<h1 style="font-size:1.4rem;font-weight:700;margin-bottom:0.5rem;">'
        "PHÂN TÍCH THU PHÍ VÀ DUY TRÌ ĐÓNG PHÍ THEO KỲ</h1>",
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        df_ky, df_month, df_date = load_all_payment_tracking()
        df_health = load_portfolio_health()
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

    # ── 4 tabs ────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Hiệu quả thu trong kỳ",
        "Sức khỏe danh mục",
        "Bản đồ thu phí",
        "Duy trì đóng phí theo kỳ",
        "Xu hướng theo ngày",
        "Phân bố ngày trong tháng",
        "Dữ liệu chi tiết",
    ])

    with tab1:
        _render_q1_tab(df_ky, selected_products)

    with tab2:
        _render_q2_tab(df_health, selected_products)

    with tab3:
        _render_cohort_heatmap(df_ky, selected_products)

    with tab4:
        _render_retention_curve(df_month, selected_products, min_gcn)

    with tab5:
        _render_rolling_trend(df_date, selected_products, min_gcn)

    with tab6:
        _render_dom_heatmap(df_date, selected_products, min_gcn)

    with tab7:
        _render_detail_tables(df_ky, df_month, df_date, selected_products)
