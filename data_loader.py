import os
import sys
import duckdb
import pandas as pd
import streamlit as st
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


@st.cache_data(ttl=300)
def load_ipay_data() -> pd.DataFrame:
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")
    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    df = con.execute("""
        SELECT
            PROD_CODE,
            "Năm",
            "Ngày phát sinh",
            "Tiền thực thu",
            "Số đơn cấp mới",
            "Số đơn cấp tái tục",
            "Số đơn tái tục dự kiến",
            "Số đơn có hiệu lực",
            "Số đơn tạm ngưng",
            "Số đơn hủy webview"
        FROM gold.ipay_quantity_rev_data
    """).df()
    con.close()
    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=300)
def load_complaints_data() -> pd.DataFrame:
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")
    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    df = con.execute("SELECT * FROM silver.classified_complaints").df()
    con.close()
    df["received_date_time"] = pd.to_datetime(df["received_date_time"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_all_payment_tracking() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load cả 3 bảng payment tracking trong 1 kết nối MotherDuck duy nhất.

    Returns: (df_ky, df_month, df_date)
      - df_ky   : silver.payment_tracking_by_ky
      - df_month: silver.payment_tracking_by_payment_month
      - df_date : silver.payment_tracking_by_payment_date
    """
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")

    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    try:
        df_ky = con.execute("SELECT * FROM silver.payment_tracking_by_ky").df()

        df_month = con.execute("""
            SELECT san_pham, thang_tra_ky_k, ky, so_gcn, ty_le_giu_chan_pct
            FROM silver.payment_tracking_by_payment_month
        """).df()

        df_date = con.execute("""
            SELECT san_pham, ngay_tra_ky_k, ky, so_gcn, ty_le_giu_chan_pct
            FROM silver.payment_tracking_by_payment_date
        """).df()
    finally:
        con.close()

    df_ky["cohort_month"]       = pd.to_datetime(df_ky["cohort_month"])
    df_month["thang_tra_ky_k"]  = pd.to_datetime(df_month["thang_tra_ky_k"])
    df_date["ngay_tra_ky_k"]    = pd.to_datetime(df_date["ngay_tra_ky_k"])
    return df_ky, df_month, df_date


@st.cache_data(ttl=3600)
def load_portfolio_health() -> pd.DataFrame:
    """
    Q2 — Sức khỏe danh mục: distinct GCN đã trả phí / GCN có hiệu lực theo tháng.

    Columns: san_pham, thang, distinct_gcn, hieu_luc
    Nguồn: bronze.payment_data (numerator) + gold.ipay_quantity_rev_data (denominator).
    Lưu ý: hieu_luc của Cyber Risk bị đóng băng trong API từ 2026-01 trở đi.
    """
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")

    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    try:
        df = con.execute("""
            WITH normalized_payments AS (
                SELECT
                    CASE "Sản phẩm"
                        WHEN 'ISafe'      THEN 'I-Safe'
                        WHEN 'homesaving' THEN 'HomeSaving'
                        ELSE "Sản phẩm"
                    END AS san_pham,
                    "Số hợp đồng VBI"                               AS so_hd,
                    DATE_TRUNC('month', "Ngày thu phí")             AS thang
                FROM bronze.payment_data
                WHERE "Sản phẩm" IN (
                    'Cyber Risk','I-Safe','ISafe',
                    'HomeSaving','homesaving','TapCare'
                )
                  AND "Ngày thu phí" IS NOT NULL
            ),
            gcn_per_month AS (
                SELECT san_pham, thang,
                       COUNT(DISTINCT so_hd) AS distinct_gcn
                FROM normalized_payments
                GROUP BY san_pham, thang
            ),
            hieu_luc_per_month AS (
                SELECT
                    CASE PROD_CODE
                        WHEN 'ISAFE_CYBER'    THEN 'I-Safe'
                        WHEN 'MIX_01'         THEN 'Cyber Risk'
                        WHEN 'TAPCARE'        THEN 'TapCare'
                        WHEN 'VTB_HOMESAVING' THEN 'HomeSaving'
                    END AS san_pham,
                    DATE_TRUNC('month', "Ngày phát sinh") AS thang,
                    MAX("Số đơn có hiệu lực")             AS hieu_luc
                FROM gold.ipay_quantity_rev_data
                WHERE PROD_CODE IN (
                    'ISAFE_CYBER','MIX_01','TAPCARE','VTB_HOMESAVING'
                )
                GROUP BY PROD_CODE, DATE_TRUNC('month', "Ngày phát sinh")
            )
            SELECT g.san_pham, g.thang,
                   g.distinct_gcn,
                   h.hieu_luc
            FROM gcn_per_month g
            LEFT JOIN hieu_luc_per_month h
                   ON h.san_pham = g.san_pham AND h.thang = g.thang
            ORDER BY g.san_pham, g.thang
        """).df()
    finally:
        con.close()

    df["thang"] = pd.to_datetime(df["thang"])
    return df
