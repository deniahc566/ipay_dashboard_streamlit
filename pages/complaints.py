import html
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

from data_loader import load_complaints_data

_PRODUCT_ORDER = ["Tapcare", "i-Safe", "Cyber Risk", "HomeSaving", "Sản phẩm khác"]
_BAR_COLOR = "#456882"

def _expand(df: pd.DataFrame) -> pd.DataFrame:
    """Replicate Power BI M transform: cross-expand products × complaint_types per email."""
    df = df.copy()
    df["products"] = df["products"].fillna("").str.split(";")
    df = df.explode("products")
    df["complaint_types"] = df["complaint_types"].fillna("").str.split(";")
    df = df.explode("complaint_types")
    df["products"] = df["products"].str.strip()
    df["complaint_types"] = df["complaint_types"].str.strip()
    df = df[(df["products"] != "") & (df["complaint_types"] != "")]
    df["Sản phẩm - Loại khiếu nại"] = df["products"] + " - " + df["complaint_types"]
    return df


def _bar_with_label(data, x_field, y_field, height=220, x_sort=None, label_format=","):
    max_val = data[y_field].max() if not data.empty else 1
    bar = (
        alt.Chart(data)
        .mark_bar(color=_BAR_COLOR)
        .encode(
            x=alt.X(
                f"{x_field}:N",
                sort=x_sort or alt.EncodingSortField(field=y_field, order="descending"),
                axis=alt.Axis(title=None, labelAngle=-20, labelLimit=100, grid=False),
            ),
            y=alt.Y(
                f"{y_field}:Q",
                scale=alt.Scale(domainMax=max_val * 1.18),
                axis=alt.Axis(title=None, grid=False),
            ),
            tooltip=[f"{x_field}:N", alt.Tooltip(f"{y_field}:Q", title="Số KN")],
        )
        .properties(height=height)
    )
    label = bar.mark_text(
        align="center", dy=-6, fontSize=11, fontWeight="normal", clip=False
    ).encode(text=alt.Text(f"{y_field}:Q", format=label_format))
    return bar + label


def _safe(val):
    return html.escape(str(val)) if pd.notna(val) and str(val).strip() else ""


def _title_attr(val):
    if not pd.notna(val) or not str(val).strip():
        return ""
    return html.escape(str(val).replace("\n", " ").replace("\r", ""), quote=True)


def render_complaints_page():
    st.markdown(
        '<style>section[data-testid="stMain"]{zoom:1;}</style>',
        unsafe_allow_html=True,
    )

    # ── Title + refresh ───────────────────────────────────────────────────────
    col_title, col_refresh = st.columns([9, 1])
    with col_title:
        st.markdown(
            '<h1 style="font-size:1.4rem;font-weight:700;margin-bottom:0.25rem;">'
            "BÁO CÁO KHIẾU NẠI BẢO HIỂM VBI QUA KÊNH IPAY</h1>",
            unsafe_allow_html=True,
        )
    with col_refresh:
        if st.button(
            "⟳ Làm mới",
            width="stretch",
            help="Xóa cache và tải lại dữ liệu mới nhất từ MotherDuck",
        ):
            load_complaints_data.clear()
            st.rerun()

    try:
        raw_df = load_complaints_data()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    if raw_df.empty:
        st.warning("Không có dữ liệu khiếu nại.")
        return

    last_updated = raw_df["received_date_time"].max()
    if pd.notna(last_updated):
        st.markdown(
            f'<p style="font-size:0.75rem;color:#666;margin:0 0 0.8rem;">'
            f'Cập nhật lần cuối: {last_updated.strftime("%d/%m/%Y %I:%M:%S %p")}</p>',
            unsafe_allow_html=True,
        )

    # ── Date range filter ────────────────────────────────────────────────────
    min_date = raw_df["received_date_time"].min().date()
    max_date = raw_df["received_date_time"].max().date()

    col_d1, col_d2, _ = st.columns([1, 1, 5])
    with col_d1:
        start_date = st.date_input(
            "Ngày nhận khiếu nại (từ)",
            value=min_date, min_value=min_date, max_value=max_date, key="kn_start",
        )
    with col_d2:
        end_date = st.date_input(
            "Đến ngày",
            value=max_date, min_value=min_date, max_value=max_date, key="kn_end",
        )

    # ── Sender + Priority filters ─────────────────────────────────────────────
    has_sender_col = "sender" in raw_df.columns
    has_priority_col = "priority" in raw_df.columns

    col_f1, col_f2, _ = st.columns([1, 1, 5])
    with col_f1:
        all_senders = sorted(raw_df["sender"].dropna().unique().tolist()) if has_sender_col else []
        sel_senders = st.multiselect(
            "Đơn vị tiếp nhận",
            options=all_senders,
            default=[],
            placeholder="Tất cả",
            key="kn_sender",
        )
    with col_f2:
        all_priorities = sorted(raw_df["priority"].dropna().unique().tolist()) if has_priority_col else []
        sel_priorities = st.multiselect(
            "Mức độ ưu tiên",
            options=all_priorities,
            default=[],
            placeholder="Tất cả",
            key="kn_priority",
        )

    mask = (raw_df["received_date_time"].dt.date >= start_date) & (
        raw_df["received_date_time"].dt.date <= end_date
    )
    filtered = raw_df[mask]
    if sel_senders:
        filtered = filtered[filtered["sender"].isin(sel_senders)]
    if sel_priorities:
        filtered = filtered[filtered["priority"].isin(sel_priorities)]
    df = _expand(filtered)

    # ── KPI cards ────────────────────────────────────────────────────────────
    total_kn = len(df)

    # "Cao" priority count — match any value containing "cao" (case-insensitive)
    if has_priority_col:
        kn_cao = df["priority"].str.lower().str.contains("cao", na=False).sum()
    else:
        kn_cao = 0

    all_df = _expand(raw_df)
    all_days = max(
        (raw_df["received_date_time"].max().date() - raw_df["received_date_time"].min().date()).days, 1
    )
    alltime_avg = len(all_df) / all_days

    yesterday = date.today() - timedelta(days=1)

    def _kpi(label, value, accent="#456882"):
        return (
            f'<div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;'
            f'padding:16px 14px 13px 10px;box-shadow:0 2px 6px rgba(0,0,0,0.05);'
            f'display:flex;gap:8px;align-items:stretch;min-height:90px;">'
            f'<div style="width:4px;border-radius:3px;background:{accent};flex-shrink:0;"></div>'
            f'<div style="flex:1;">'
            f'<div style="font-size:2rem;font-weight:700;color:#1a1a2e;">{value}</div>'
            f'<div style="font-size:0.68rem;color:#666;margin-top:4px;">{label}</div>'
            f'</div></div>'
        )

    c1, c2, c3 = st.columns(3)
    c1.markdown(_kpi("Tổng số khiếu nại", f"{total_kn:,}"), unsafe_allow_html=True)
    c2.markdown(_kpi("Số khiếu nại Mức độ ưu tiên cao", f"{kn_cao:,}", accent="#c0392b"), unsafe_allow_html=True)
    c3.markdown(_kpi("Số khiếu nại trung bình một ngày", f"{alltime_avg:.2f}"), unsafe_allow_html=True)

    # ── Expander: chi tiết hôm qua ────────────────────────────────────────────
    st.markdown('<div style="margin-top:12px;"></div>', unsafe_allow_html=True)
    df_yesterday = _expand(raw_df[raw_df["received_date_time"].dt.date == yesterday])
    with st.expander(f"↕ Chi tiết theo Sản phẩm - Loại khiếu nại — ngày {yesterday.strftime('%d/%m/%Y')}"):
        if has_priority_col and not df_yesterday.empty:
            _PRIORITY_ORDER = ["Cao", "Trung bình", "Thấp"]
            _all_pris = df_yesterday["priority"].dropna().unique().tolist()
            priority_vals_y = [p for p in _PRIORITY_ORDER if p in _all_pris] + \
                              sorted(p for p in _all_pris if p not in _PRIORITY_ORDER)
            pivot_y = (
                df_yesterday.groupby(["Sản phẩm - Loại khiếu nại", "priority"])
                .size()
                .reset_index(name="count")
                .pivot(index="Sản phẩm - Loại khiếu nại", columns="priority", values="count")
                .fillna(0)
                .astype(int)
            )
            pivot_y = pivot_y.reindex(columns=priority_vals_y, fill_value=0)
            pivot_y["Tổng"] = pivot_y.sum(axis=1)
            pivot_y.columns.name = None
            pivot_y = pivot_y.sort_values("Tổng", ascending=False)

            _cao_cols_y = [c for c in priority_vals_y if "cao" in str(c).lower()]

            def _colour_y(val):
                if isinstance(val, (int, float)) and val > 0:
                    return "color:#c62828;font-weight:600"
                return "color:#999999"

            styled_y = pivot_y.style.format("{:,}")
            if _cao_cols_y:
                styled_y = styled_y.map(_colour_y, subset=_cao_cols_y)
            styled_y = styled_y.map(
                lambda v: "font-weight:700" if isinstance(v, (int, float)) else "",
                subset=["Tổng"],
            )
            st.dataframe(styled_y, width="stretch")
        elif df_yesterday.empty:
            st.info(f"Không có khiếu nại nào vào ngày {yesterday.strftime('%d/%m/%Y')}.")
        else:
            st.info("Không có dữ liệu mức độ ưu tiên.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Row 1: 4 bar charts ──────────────────────────────────────────────────
    num_days = max((end_date - start_date).days, 1)
    r1c0, r1c1, r1c2, r1c3 = st.columns(4)

    with r1c0:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại theo mức độ ưu tiên</p>",
            unsafe_allow_html=True,
        )
        if has_priority_col and not df.empty:
            pri_count = df.groupby("priority").size().reset_index(name="count").sort_values("count", ascending=False)
            st.altair_chart(_bar_with_label(pri_count, "priority", "count", height=220), width="stretch")
        else:
            st.info("Không có dữ liệu mức độ ưu tiên.")

    with r1c1:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại trung bình/ngày theo sản phẩm</p>",
            unsafe_allow_html=True,
        )
        prod_avg = df.groupby("products").size().reset_index(name="count")
        prod_avg["avg"] = prod_avg["count"] / num_days
        prod_avg["products"] = pd.Categorical(prod_avg["products"], categories=_PRODUCT_ORDER, ordered=True)
        prod_avg = prod_avg.dropna(subset=["products"]).sort_values("products")
        max_avg = prod_avg["avg"].max() if not prod_avg.empty else 1
        bar1 = (
            alt.Chart(prod_avg).mark_bar(color=_BAR_COLOR)
            .encode(
                x=alt.X("products:N", sort=_PRODUCT_ORDER,
                        axis=alt.Axis(title=None, labelAngle=-20, labelLimit=100, grid=False)),
                y=alt.Y("avg:Q", scale=alt.Scale(domainMax=max_avg * 1.18),
                        axis=alt.Axis(title=None, grid=False)),
                tooltip=["products:N", alt.Tooltip("avg:Q", format=".2f", title="TB/ngày")],
            ).properties(height=220)
        )
        lbl1 = bar1.mark_text(align="center", dy=-6, fontSize=11, fontWeight="normal", clip=False).encode(
            text=alt.Text("avg:Q", format=".2f")
        )
        st.altair_chart(bar1 + lbl1, width="stretch")

    with r1c2:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại theo sản phẩm</p>", unsafe_allow_html=True,
        )
        prod_count = df.groupby("products").size().reset_index(name="count").sort_values("count", ascending=False)
        st.altair_chart(_bar_with_label(prod_count, "products", "count", height=220), width="stretch")

    with r1c3:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại theo loại khiếu nại</p>", unsafe_allow_html=True,
        )
        type_count = df.groupby("complaint_types").size().reset_index(name="count").sort_values("count", ascending=False)
        st.altair_chart(_bar_with_label(type_count, "complaint_types", "count", height=220), width="stretch")

    # ── Row 2: horizontal bar + line chart (monthly, last 12 months) ─────────
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại theo Sản phẩm - Loại khiếu nại</p>", unsafe_allow_html=True,
        )
        pair_count = (
            df.groupby("Sản phẩm - Loại khiếu nại").size().reset_index(name="count")
            .nlargest(10, "count").sort_values("count", ascending=False)
        )
        h_bar = (
            alt.Chart(pair_count).mark_bar(color=_BAR_COLOR)
            .encode(
                y=alt.Y("Sản phẩm - Loại khiếu nại:N",
                        sort=alt.EncodingSortField(field="count", order="descending"),
                        axis=alt.Axis(title=None, labelLimit=200, grid=False)),
                x=alt.X("count:Q", axis=alt.Axis(title=None, grid=False)),
                tooltip=["Sản phẩm - Loại khiếu nại:N", alt.Tooltip("count:Q", title="Số KN")],
            ).properties(height=320)
        )
        h_label = h_bar.mark_text(align="left", dx=4, fontSize=11, clip=False).encode(
            text=alt.Text("count:Q", format=",")
        )
        st.altair_chart(h_bar + h_label, width="stretch")

    with r2c2:
        st.markdown(
            '<p style="font-weight:600;font-size:0.85rem;margin-bottom:4px;">'
            "Số khiếu nại theo thời gian (12 tháng gần nhất)</p>", unsafe_allow_html=True,
        )
        _latest = df["received_date_time"].max() if not df.empty else pd.Timestamp.now()
        _cutoff = (_latest - pd.DateOffset(months=11)).replace(day=1)
        df_time = df[df["received_date_time"] >= _cutoff].copy()
        df_time["Tháng"] = df_time["received_date_time"].dt.to_period("M").astype(str)
        monthly = df_time.groupby("Tháng").size().reset_index(name="Số KN")

        line = (
            alt.Chart(monthly)
            .mark_line(color=_BAR_COLOR, strokeWidth=2.5,
                       point=alt.OverlayMarkDef(color=_BAR_COLOR, size=60))
            .encode(
                x=alt.X("Tháng:O", axis=alt.Axis(title=None, labelAngle=-30, grid=False)),
                y=alt.Y("Số KN:Q", scale=alt.Scale(zero=False),
                        axis=alt.Axis(title=None, grid=False)),
                tooltip=["Tháng:O", alt.Tooltip("Số KN:Q", title="Số KN")],
            ).properties(height=320)
        )
        lbl_line = line.mark_text(align="center", dy=-12, fontSize=10, fontWeight="normal").encode(
            text=alt.Text("Số KN:Q", format=",")
        )
        st.altair_chart(line + lbl_line, width="stretch")


    # ── Detail table with hover tooltip ──────────────────────────────────────
    st.markdown(
        '<p style="font-weight:600;font-size:0.85rem;margin-top:16px;margin-bottom:4px;">'
        "Chi tiết khiếu nại</p>",
        unsafe_allow_html=True,
    )

    df_detail = df.copy()

    has_request = "customer_request" in df_detail.columns
    has_cause = "cause" in df_detail.columns

    detail_src_cols = ["received_date_time", "Sản phẩm - Loại khiếu nại"]
    if has_priority_col:
        detail_src_cols.append("priority")
    detail_src_cols.append("subject")
    if has_request:
        detail_src_cols.append("customer_request")
    if has_cause:
        detail_src_cols.append("cause")

    detail = df_detail[detail_src_cols].sort_values("received_date_time", ascending=False).copy()
    detail["received_date_time"] = detail["received_date_time"].dt.strftime("%d/%m/%Y %I:%M:%S %p")

    # ── Pagination ────────────────────────────────────────────────────────────
    PAGE_SIZE = 15
    total_rows = len(detail)
    total_pages = max(1, -(-total_rows // PAGE_SIZE))  # ceiling division

    # Reset page when filters or date range change
    _filter_key = (str(start_date), str(end_date), str(sorted(sel_senders)), str(sorted(sel_priorities)))
    if st.session_state.get("_kn_filter_key") != _filter_key:
        st.session_state["_kn_filter_key"] = _filter_key
        st.session_state["kn_page"] = 1

    current_page = st.session_state.get("kn_page", 1)
    current_page = max(1, min(current_page, total_pages))

    page_start = (current_page - 1) * PAGE_SIZE
    page_end = page_start + PAGE_SIZE
    detail_page = detail.iloc[page_start:page_end]

    _DT_TH = "background:#456882;color:#fff;padding:8px 10px;text-align:left;font-weight:600;white-space:nowrap;"
    _DT_TD = "padding:7px 10px;border-bottom:1px solid #f0f0f0;vertical-align:top;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"

    header_cells = (
        f'<th style="{_DT_TH}">Thời gian nhận khiếu nại</th>'
        f'<th style="{_DT_TH}">Sản phẩm - Loại khiếu nại</th>'
        + (f'<th style="{_DT_TH}">Mức độ ưu tiên</th>' if has_priority_col else "")
        + f'<th style="{_DT_TH}">Tiêu đề</th>'
    )

    rows_html = []
    for _, row in detail_page.iterrows():
        tooltip_parts = []
        if has_request:
            v = _title_attr(row.get("customer_request", ""))
            if v:
                tooltip_parts.append(f"Yêu cầu KH: {v}")
        if has_cause:
            v = _title_attr(row.get("cause", ""))
            if v:
                tooltip_parts.append(f"Nguyên nhân tổn thất: {v}")
        title_attr = " | ".join(tooltip_parts)

        cells = (
            f'<td style="{_DT_TD}">{_safe(row["received_date_time"])}</td>'
            f'<td style="{_DT_TD}">{_safe(row["Sản phẩm - Loại khiếu nại"])}</td>'
            + (f'<td style="{_DT_TD}">{_safe(row["priority"])}</td>' if has_priority_col else "")
            + f'<td style="{_DT_TD}">{_safe(row["subject"])}</td>'
        )
        rows_html.append(f'<tr title="{title_attr}" style="cursor:default;">{cells}</tr>')

    table_html = (
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.8rem;">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f'<tbody>{"".join(rows_html)}</tbody>'
        "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Pagination controls ───────────────────────────────────────────────────
    pc_first, pc_prev, pc_mid, pc_next, pc_last = st.columns([1, 1, 3, 1, 1])
    with pc_first:
        if st.button("⏮ Đầu", disabled=current_page <= 1, key="kn_first", width="stretch"):
            st.session_state["kn_page"] = 1
            st.rerun()
    with pc_prev:
        if st.button("← Trước", disabled=current_page <= 1, key="kn_prev", width="stretch"):
            st.session_state["kn_page"] = current_page - 1
            st.rerun()
    with pc_mid:
        st.markdown(
            f'<p style="text-align:center;font-size:0.8rem;color:#666;margin:6px 0 0;">'
            f'Trang {current_page} / {total_pages} &nbsp;·&nbsp; {total_rows:,} bản ghi</p>',
            unsafe_allow_html=True,
        )
    with pc_next:
        if st.button("Tiếp →", disabled=current_page >= total_pages, key="kn_next", width="stretch"):
            st.session_state["kn_page"] = current_page + 1
            st.rerun()
    with pc_last:
        if st.button("Cuối ⏭", disabled=current_page >= total_pages, key="kn_last", width="stretch"):
            st.session_state["kn_page"] = total_pages
            st.rerun()
