"""
Báo cáo Excel: Tổng Tiền thực thu (Không bao gồm VAT) — bản dùng cho dashboard.

Bản sao logic của Scripts/reports/excel_revenue_report.py (repo dashboard deploy
độc lập, không có Scripts/ và config/). Khi sửa logic báo cáo, cập nhật cả hai file.
"""

import io
import os
import logging

import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

logger = logging.getLogger(__name__)

# ─── Cấu hình sản phẩm ────────────────────────────────────────────────────────

_BAN_LE_PRODUCTS = [
    ("XE",      "Bảo hiểm ô tô"),
    ("CN.6",    "Bảo hiểm sức khỏe"),
    ("XC.1.1",  "Bảo hiểm xe máy"),
    ("CN.4.1SA","Du lịch quốc tế bán lẻ"),
    ("CN.4.3SA","Du lịch trong nước bán lẻ"),
    ("UTV",     "Ung thư vú"),
]

_BAN_KEM_PRODUCTS = [
    ("MIX_01",         "Cyber Risk"),
    ("CN.4.1IPAY",     "Du lịch quốc tế bán kèm"),
    ("CN.4.3IPAY",     "Du lịch trong nước bán kèm"),
    ("VTB_HOMESAVING", "HomeSaving"),
    ("ISAFE_CYBER",    "I-Safe"),
    ("TAPCARE",        "TapCare"),
]

# ─── Màu sắc ──────────────────────────────────────────────────────────────────

_COLOR_TITLE_BG        = "FFE0E0"   # hồng nhạt – tiêu đề và header nhóm
_COLOR_TOTAL_BG        = "E2EFDA"   # xanh nhạt – dòng tổng
_COLOR_HEADER_BG       = "F2F2F2"   # xám nhạt – hàng cột header
_COLOR_GROWTH_POS_BG   = "C6EFCE"   # xanh – tăng trưởng dương
_COLOR_GROWTH_POS_FONT = "276221"
_COLOR_GROWTH_NEG_BG   = "FFC7CE"   # đỏ – tăng trưởng âm
_COLOR_GROWTH_NEG_FONT = "9C0006"
_COLOR_GROWTH_ZERO_BG  = "FFFFFF"

_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


# ─── Tải dữ liệu từ MotherDuck ────────────────────────────────────────────────

def load_data(token: str) -> pd.DataFrame:
    logger.info("Kết nối MotherDuck...")
    con = duckdb.connect(f"md:ipay_data?motherduck_token={token}")
    df = con.execute("SELECT * FROM gold.ipay_quantity_rev_data").df()
    con.close()
    df["Tiền thực thu"] = pd.to_numeric(df["Tiền thực thu"], errors="coerce").fillna(0)
    df["Tháng"] = pd.to_numeric(df["Tháng"], errors="coerce")
    df["Năm"]   = pd.to_numeric(df["Năm"],   errors="coerce")
    # Cyber Risk (MIX_01): doanh thu trong DuckDB bao gồm VAT 10%; chỉ lấy phần phí doanh thu
    df.loc[df["PROD_CODE"] == "MIX_01", "Tiền thực thu"] *= 2727 / 3000
    logger.info("Tải xong %d dòng.", len(df))
    return df


def aggregate_by_month(df: pd.DataFrame, month: int, year: int, metric: str = "Tiền thực thu") -> dict[str, float]:
    """Tổng metric cho tháng cụ thể, theo từng PROD_CODE."""
    filtered = df[(df["Tháng"] == month) & (df["Năm"] == year)]
    return filtered.groupby("PROD_CODE")[metric].sum().to_dict()


def aggregate_ytd(df: pd.DataFrame, month: int, year: int, metric: str = "Tiền thực thu") -> dict[str, float]:
    """Tổng metric lũy kế từ tháng 1 đến tháng `month` trong năm `year`."""
    filtered = df[(df["Tháng"] <= month) & (df["Năm"] == year)]
    return filtered.groupby("PROD_CODE")[metric].sum().to_dict()


# ─── Tính toán tăng trưởng ────────────────────────────────────────────────────

def _growth(current: float, previous: float) -> tuple[float | None, float | None]:
    """Trả về (tăng_trưởng_%, tăng_trưởng_VND). None nếu kỳ trước = 0."""
    delta = current - previous
    pct = (delta / previous) if previous != 0 else None
    return pct, delta


def build_report_rows(
    df: pd.DataFrame,
    month: int,
    year: int,
    metric: str = "Tiền thực thu",
) -> tuple[list, list, dict]:
    """
    Trả về:
      ban_le_rows   – list of (display_name, current, prev, pct, delta, ytd, ytd_pct, ytd_delta)
      ban_kem_rows  – list of (display_name, current, prev, pct, delta, ytd, ytd_pct, ytd_delta)
      totals        – dict: ban_le_current, ban_le_prev, ban_kem_current, ban_kem_prev,
                           total_current, total_prev, ban_le_ytd, ban_kem_ytd, total_ytd,
                           ban_le_ytd_prev, ban_kem_ytd_prev, total_ytd_prev
    """
    cur      = aggregate_by_month(df, month, year, metric)
    prev     = aggregate_by_month(df, month, year - 1, metric)
    ytd      = aggregate_ytd(df, month, year, metric)
    ytd_prev = aggregate_ytd(df, month, year - 1, metric)

    def row(prod_code: str, display_name: str):
        c  = cur.get(prod_code, 0.0)
        p  = prev.get(prod_code, 0.0)
        y  = ytd.get(prod_code, 0.0)
        yp = ytd_prev.get(prod_code, 0.0)
        pct, delta = _growth(c, p)
        ytd_pct, ytd_delta = _growth(y, yp)
        return display_name, c, p, pct, delta, y, ytd_pct, ytd_delta

    ban_le_rows  = [row(code, name) for code, name in _BAN_LE_PRODUCTS]
    ban_kem_rows = [row(code, name) for code, name in _BAN_KEM_PRODUCTS]

    ban_le_cur   = sum(r[1] for r in ban_le_rows)
    ban_le_prev  = sum(prev.get(code, 0.0) for code, _ in _BAN_LE_PRODUCTS)
    ban_kem_cur  = sum(r[1] for r in ban_kem_rows)
    ban_kem_prev = sum(prev.get(code, 0.0) for code, _ in _BAN_KEM_PRODUCTS)
    total_cur    = ban_le_cur + ban_kem_cur
    total_prev   = ban_le_prev + ban_kem_prev

    ban_le_ytd       = sum(ytd.get(code, 0.0)      for code, _ in _BAN_LE_PRODUCTS)
    ban_kem_ytd      = sum(ytd.get(code, 0.0)      for code, _ in _BAN_KEM_PRODUCTS)
    total_ytd        = ban_le_ytd + ban_kem_ytd
    ban_le_ytd_prev  = sum(ytd_prev.get(code, 0.0) for code, _ in _BAN_LE_PRODUCTS)
    ban_kem_ytd_prev = sum(ytd_prev.get(code, 0.0) for code, _ in _BAN_KEM_PRODUCTS)
    total_ytd_prev   = ban_le_ytd_prev + ban_kem_ytd_prev

    totals = {
        "ban_le_cur":        ban_le_cur,       "ban_le_prev":        ban_le_prev,
        "ban_kem_cur":       ban_kem_cur,      "ban_kem_prev":       ban_kem_prev,
        "total_cur":         total_cur,        "total_prev":         total_prev,
        "ban_le_ytd":        ban_le_ytd,       "ban_le_ytd_prev":    ban_le_ytd_prev,
        "ban_kem_ytd":       ban_kem_ytd,      "ban_kem_ytd_prev":   ban_kem_ytd_prev,
        "total_ytd":         total_ytd,        "total_ytd_prev":     total_ytd_prev,
    }
    return ban_le_rows, ban_kem_rows, totals


# ─── Định dạng số ─────────────────────────────────────────────────────────────

def fmt_vnd(value: float) -> str:
    """1234567 → '1,234,567'; âm → '(1,234,567)'"""
    if value < 0:
        return f"({abs(value):,.0f})"
    return f"{value:,.0f}"


def fmt_pct(value: float | None) -> str:
    """0.1234 → '12.34%'; None → '—'"""
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


# ─── Tạo file Excel ────────────────────────────────────────────────────────────

def _fill(hex_color: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=hex_color)


def _font(bold: bool = False, color: str = "000000", size: int = 11) -> Font:
    return Font(bold=bold, color=color, size=size, name="Calibri")


def _center() -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def _right() -> Alignment:
    return Alignment(horizontal="right", vertical="center")


def _left() -> Alignment:
    return Alignment(horizontal="left", vertical="center", indent=1)


def _left_indent(level: int = 0) -> Alignment:
    return Alignment(horizontal="left", vertical="center", indent=2 + level * 2)


def _apply_growth_style(cell, pct: float | None) -> None:
    """Tô màu ô tăng trưởng theo dương/âm/zero."""
    if pct is None or pct == 0:
        cell.fill = _fill(_COLOR_GROWTH_ZERO_BG)
        cell.font = _font()
    elif pct > 0:
        cell.fill = _fill(_COLOR_GROWTH_POS_BG)
        cell.font = _font(color=_COLOR_GROWTH_POS_FONT)
    else:
        cell.fill = _fill(_COLOR_GROWTH_NEG_BG)
        cell.font = _font(color=_COLOR_GROWTH_NEG_FONT)
    cell.alignment = _center()
    cell.border = _THIN_BORDER


def _apply_vnd_style(cell, delta: float | None) -> None:
    """Tô màu ô delta VND theo dương/âm."""
    if delta is None or delta == 0:
        cell.fill = _fill(_COLOR_GROWTH_ZERO_BG)
        cell.font = _font()
    elif delta > 0:
        cell.fill = _fill(_COLOR_GROWTH_POS_BG)
        cell.font = _font(color=_COLOR_GROWTH_POS_FONT)
    else:
        cell.fill = _fill(_COLOR_GROWTH_NEG_BG)
        cell.font = _font(color=_COLOR_GROWTH_NEG_FONT)
    cell.alignment = _right()
    cell.border = _THIN_BORDER


def _write_metric_sheet(
    ws,
    ban_le_rows: list,
    ban_kem_rows: list,
    totals: dict,
    month: int,
    year: int,
    report_title: str,
    number_fmt: str,
    delta_col_header: str,
) -> None:
    """Ghi dữ liệu một metric vào worksheet `ws`."""
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 22
    ws.column_dimensions["F"].width = 22
    ws.column_dimensions["G"].width = 22
    ws.column_dimensions["H"].width = 22

    month_label      = f"Tháng {month} {year}"
    prev_month_label = f"Tháng {month} {year - 1}"
    ytd_label        = f"Lũy kế T1-T{month}\n{year}"

    # ── Hàng 1: Tiêu đề ──────────────────────────────────────────────────────
    ws.merge_cells("A1:H1")
    title_cell = ws["A1"]
    title_cell.value = report_title
    title_cell.font = _font(bold=True, size=13)
    title_cell.fill = _fill(_COLOR_TITLE_BG)
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    # ── Hàng 2: Header cột ───────────────────────────────────────────────────
    headers = [
        "",
        month_label,
        prev_month_label,
        "Tăng trưởng so với\ncùng kỳ (%)",
        delta_col_header,
        ytd_label,
        f"Tăng trưởng lũy kế\nso với {year - 1} (%)",
        f"Tăng trưởng lũy kế\nso với {year - 1} (VNĐ)",
    ]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = _font(bold=True)
        cell.fill = _fill(_COLOR_HEADER_BG)
        cell.alignment = _center()
        cell.border = _THIN_BORDER
    ws.row_dimensions[2].height = 36

    current_row = 3

    def write_group_header(label: str, cur: float, prev: float, ytd: float, ytd_prev: float) -> None:
        nonlocal current_row
        pct, delta = _growth(cur, prev)
        ytd_pct, ytd_delta = _growth(ytd, ytd_prev)

        name_cell = ws.cell(row=current_row, column=1, value=label)
        name_cell.font = _font(bold=True)
        name_cell.fill = _fill(_COLOR_TITLE_BG)
        name_cell.alignment = _left()
        name_cell.border = _THIN_BORDER

        cur_cell = ws.cell(row=current_row, column=2, value=cur)
        cur_cell.number_format = number_fmt
        cur_cell.font = _font(bold=True)
        cur_cell.fill = _fill(_COLOR_TITLE_BG)
        cur_cell.alignment = _right()
        cur_cell.border = _THIN_BORDER

        prev_cell = ws.cell(row=current_row, column=3, value=prev)
        prev_cell.number_format = number_fmt
        prev_cell.font = _font(bold=True)
        prev_cell.fill = _fill(_COLOR_TITLE_BG)
        prev_cell.alignment = _right()
        prev_cell.border = _THIN_BORDER

        pct_cell = ws.cell(row=current_row, column=4, value=pct if pct is not None else "N/A")
        if pct is not None:
            pct_cell.number_format = '0.00%'
        _apply_growth_style(pct_cell, pct)
        pct_cell.font = _font(bold=True, color=pct_cell.font.color.rgb if pct_cell.font.color else "000000")

        delta_cell = ws.cell(row=current_row, column=5, value=delta if delta is not None else "N/A")
        if delta is not None:
            delta_cell.number_format = number_fmt
        _apply_vnd_style(delta_cell, delta)
        delta_cell.font = _font(bold=True, color=delta_cell.font.color.rgb if delta_cell.font.color else "000000")

        ytd_cell = ws.cell(row=current_row, column=6, value=ytd)
        ytd_cell.number_format = number_fmt
        ytd_cell.font = _font(bold=True)
        ytd_cell.fill = _fill(_COLOR_TITLE_BG)
        ytd_cell.alignment = _right()
        ytd_cell.border = _THIN_BORDER

        ytd_pct_cell = ws.cell(row=current_row, column=7, value=ytd_pct if ytd_pct is not None else "N/A")
        if ytd_pct is not None:
            ytd_pct_cell.number_format = '0.00%'
        _apply_growth_style(ytd_pct_cell, ytd_pct)
        ytd_pct_cell.font = _font(bold=True, color=ytd_pct_cell.font.color.rgb if ytd_pct_cell.font.color else "000000")

        ytd_delta_cell = ws.cell(row=current_row, column=8, value=ytd_delta if ytd_delta is not None else "N/A")
        if ytd_delta is not None:
            ytd_delta_cell.number_format = number_fmt
        _apply_vnd_style(ytd_delta_cell, ytd_delta)
        ytd_delta_cell.font = _font(bold=True, color=ytd_delta_cell.font.color.rgb if ytd_delta_cell.font.color else "000000")

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    def write_product_row(display_name: str, cur: float, prev: float, pct: float | None, delta: float | None, ytd: float, ytd_pct: float | None, ytd_delta: float | None) -> None:
        nonlocal current_row

        name_cell = ws.cell(row=current_row, column=1, value=display_name)
        name_cell.font = _font()
        name_cell.alignment = _left_indent(level=1)
        name_cell.border = _THIN_BORDER

        cur_cell = ws.cell(row=current_row, column=2, value=cur)
        cur_cell.number_format = number_fmt
        cur_cell.font = _font()
        cur_cell.alignment = _right()
        cur_cell.border = _THIN_BORDER

        prev_cell = ws.cell(row=current_row, column=3, value=prev)
        prev_cell.number_format = number_fmt
        prev_cell.font = _font()
        prev_cell.alignment = _right()
        prev_cell.border = _THIN_BORDER

        pct_cell = ws.cell(row=current_row, column=4, value=pct if pct is not None else "N/A")
        if pct is not None:
            pct_cell.number_format = '0.00%'
        _apply_growth_style(pct_cell, pct)

        delta_cell = ws.cell(row=current_row, column=5, value=delta if delta is not None else "N/A")
        if delta is not None:
            delta_cell.number_format = number_fmt
        _apply_vnd_style(delta_cell, delta)

        ytd_cell = ws.cell(row=current_row, column=6, value=ytd)
        ytd_cell.number_format = number_fmt
        ytd_cell.font = _font()
        ytd_cell.alignment = _right()
        ytd_cell.border = _THIN_BORDER

        ytd_pct_cell = ws.cell(row=current_row, column=7, value=ytd_pct if ytd_pct is not None else "N/A")
        if ytd_pct is not None:
            ytd_pct_cell.number_format = '0.00%'
        _apply_growth_style(ytd_pct_cell, ytd_pct)

        ytd_delta_cell = ws.cell(row=current_row, column=8, value=ytd_delta if ytd_delta is not None else "N/A")
        if ytd_delta is not None:
            ytd_delta_cell.number_format = number_fmt
        _apply_vnd_style(ytd_delta_cell, ytd_delta)

        ws.row_dimensions[current_row].height = 18
        current_row += 1

    def write_total_row(label: str, cur: float, prev: float, ytd: float, ytd_prev: float) -> None:
        nonlocal current_row
        pct, delta = _growth(cur, prev)
        ytd_pct, ytd_delta = _growth(ytd, ytd_prev)

        name_cell = ws.cell(row=current_row, column=1, value=label)
        name_cell.font = _font(bold=True)
        name_cell.fill = _fill(_COLOR_TOTAL_BG)
        name_cell.alignment = _left()
        name_cell.border = _THIN_BORDER

        cur_cell = ws.cell(row=current_row, column=2, value=cur)
        cur_cell.number_format = number_fmt
        cur_cell.font = _font(bold=True)
        cur_cell.fill = _fill(_COLOR_TOTAL_BG)
        cur_cell.alignment = _right()
        cur_cell.border = _THIN_BORDER

        prev_cell = ws.cell(row=current_row, column=3, value=prev)
        prev_cell.number_format = number_fmt
        prev_cell.font = _font(bold=True)
        prev_cell.fill = _fill(_COLOR_TOTAL_BG)
        prev_cell.alignment = _right()
        prev_cell.border = _THIN_BORDER

        pct_cell = ws.cell(row=current_row, column=4, value=pct if pct is not None else "N/A")
        if pct is not None:
            pct_cell.number_format = '0.00%'
        _apply_growth_style(pct_cell, pct)
        pct_cell.fill = _fill(_COLOR_TOTAL_BG)
        pct_cell.font = _font(bold=True, color=pct_cell.font.color.rgb if pct_cell.font.color else "000000")

        delta_cell = ws.cell(row=current_row, column=5, value=delta if delta is not None else "N/A")
        if delta is not None:
            delta_cell.number_format = number_fmt
        _apply_vnd_style(delta_cell, delta)
        delta_cell.fill = _fill(_COLOR_TOTAL_BG)
        delta_cell.font = _font(bold=True, color=delta_cell.font.color.rgb if delta_cell.font.color else "000000")

        ytd_cell = ws.cell(row=current_row, column=6, value=ytd)
        ytd_cell.number_format = number_fmt
        ytd_cell.font = _font(bold=True)
        ytd_cell.fill = _fill(_COLOR_TOTAL_BG)
        ytd_cell.alignment = _right()
        ytd_cell.border = _THIN_BORDER

        ytd_pct_cell = ws.cell(row=current_row, column=7, value=ytd_pct if ytd_pct is not None else "N/A")
        if ytd_pct is not None:
            ytd_pct_cell.number_format = '0.00%'
        _apply_growth_style(ytd_pct_cell, ytd_pct)
        ytd_pct_cell.fill = _fill(_COLOR_TOTAL_BG)
        ytd_pct_cell.font = _font(bold=True, color=ytd_pct_cell.font.color.rgb if ytd_pct_cell.font.color else "000000")

        ytd_delta_cell = ws.cell(row=current_row, column=8, value=ytd_delta if ytd_delta is not None else "N/A")
        if ytd_delta is not None:
            ytd_delta_cell.number_format = number_fmt
        _apply_vnd_style(ytd_delta_cell, ytd_delta)
        ytd_delta_cell.fill = _fill(_COLOR_TOTAL_BG)
        ytd_delta_cell.font = _font(bold=True, color=ytd_delta_cell.font.color.rgb if ytd_delta_cell.font.color else "000000")

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    write_group_header(
        "Bảo hiểm bán độc lập",
        totals["ban_le_cur"],
        totals["ban_le_prev"],
        totals["ban_le_ytd"],
        totals["ban_le_ytd_prev"],
    )
    for name, cur, prev, pct, delta, ytd, ytd_pct, ytd_delta in ban_le_rows:
        write_product_row(name, cur, prev, pct, delta, ytd, ytd_pct, ytd_delta)

    write_group_header(
        "Bảo hiểm gắn kèm",
        totals["ban_kem_cur"],
        totals["ban_kem_prev"],
        totals["ban_kem_ytd"],
        totals["ban_kem_ytd_prev"],
    )
    for name, cur, prev, pct, delta, ytd, ytd_pct, ytd_delta in ban_kem_rows:
        write_product_row(name, cur, prev, pct, delta, ytd, ytd_pct, ytd_delta)

    write_total_row(
        "Tổng lũy kế",
        totals["total_cur"],
        totals["total_prev"],
        totals["total_ytd"],
        totals["total_ytd_prev"],
    )


def build_report_bytes(df: pd.DataFrame, month: int, year: int) -> bytes:
    """Tạo báo cáo dạng bytes (dùng cho nút tải xuống trên Streamlit)."""
    buf = io.BytesIO()
    build_workbook(df, month, year).save(buf)
    return buf.getvalue()


def build_workbook(df: pd.DataFrame, month: int, year: int) -> Workbook:
    wb = Workbook()

    # ── Sheet 1: Doanh thu ────────────────────────────────────────────────────
    rev_le, rev_kem, rev_totals = build_report_rows(df, month, year, "Tiền thực thu")
    ws1 = wb.active
    ws1.title = f"T{month:02d}_{year}"
    _write_metric_sheet(
        ws1, rev_le, rev_kem, rev_totals, month, year,
        "Tổng Tiền thực thu (Không bao gồm VAT)",
        '#,##0;(#,##0)',
        "Tăng trưởng so với\ncùng kỳ (VNĐ)",
    )

    # ── Sheet 2: Số đơn cấp mới ───────────────────────────────────────────────
    don_le, don_kem, don_totals = build_report_rows(df, month, year, "Số đơn cấp mới")
    ws2 = wb.create_sheet(f"Don_T{month:02d}_{year}")
    _write_metric_sheet(
        ws2, don_le, don_kem, don_totals, month, year,
        "Số Đơn Cấp Mới",
        '#,##0',
        "Tăng trưởng so với\ncùng kỳ (Đơn)",
    )
    return wb


def load_report_data() -> pd.DataFrame:
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise EnvironmentError("MOTHERDUCK_TOKEN chưa được đặt trong biến môi trường.")
    return load_data(token)
