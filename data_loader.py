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
