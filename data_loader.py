import os
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
    df = con.execute("SELECT * FROM gold.ipay_quantity_rev_data").df()
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
