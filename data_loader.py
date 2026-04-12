import os
import sys
import duckdb
import pandas as pd
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Local DuckDB path — resolve relative to this file's project root
_LOCAL_DB = str(
    Path(__file__).parent.parent / "Data" / "db" / "bhtt_ipay.db"
).replace("\\", "/")

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


@st.cache_data(ttl=300)
def load_payment_tracking_by_ky() -> pd.DataFrame:
    """silver.payment_tracking_by_ky — cohort hiệu lực × kỳ × da_thu/chua_thu_qua_han."""
    con = duckdb.connect(_LOCAL_DB, read_only=True)
    df = con.execute("SELECT * FROM silver.payment_tracking_by_ky").df()
    con.close()
    df["cohort_month"] = pd.to_datetime(df["cohort_month"])
    return df


@st.cache_data(ttl=300)
def load_payment_tracking_by_month() -> pd.DataFrame:
    """silver.payment_tracking_by_payment_month — retention tháng-qua-tháng."""
    con = duckdb.connect(_LOCAL_DB, read_only=True)
    df = con.execute("SELECT * FROM silver.payment_tracking_by_payment_month").df()
    con.close()
    df["thang_tra_ky_k"] = pd.to_datetime(df["thang_tra_ky_k"])
    return df


@st.cache_data(ttl=300)
def load_payment_tracking_by_date() -> pd.DataFrame:
    """silver.payment_tracking_by_payment_date — retention theo ngày."""
    con = duckdb.connect(_LOCAL_DB, read_only=True)
    df = con.execute("SELECT * FROM silver.payment_tracking_by_payment_date").df()
    con.close()
    df["ngay_tra_ky_k"] = pd.to_datetime(df["ngay_tra_ky_k"])
    return df
