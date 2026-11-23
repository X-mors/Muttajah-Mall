# -*- coding: utf-8 -*-
"""تنسيق إكسل مشترك لبندَي الردم والعزل (نفس ألوان حصر العناصر الرأسية)."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

NAVY, LT, GRN, GREY, YEL, RED = "1F3864", "D9E1F2", "E2EFDA", "F2F2F2", "FFF2CC", "FCE4D6"
_bd = Border(*[Side(style="thin", color="BFBFBF")] * 4)


def st(c, *, b=False, sz=11, color="000000", fill=None, ha="center", wrap=False, fmt=None):
    c.font = Font(bold=b, size=sz, color=color)
    c.alignment = Alignment(horizontal=ha, vertical="center", wrap_text=wrap)
    if fill: c.fill = PatternFill("solid", fgColor=fill)
    c.border = _bd
    if fmt: c.number_format = fmt
    return c


class Sheet:
    """ورقة RTL بتكتب صفوف بالتتابع."""

    def __init__(self, wb, title, widths, first=False):
        self.ws = wb.active if first else wb.create_sheet(title)
        self.ws.title = title; self.ws.sheet_view.rightToLeft = True
        self.n = len(widths); self.r = 1
        for j, w in enumerate(widths, 1):
            self.ws.column_dimensions[get_column_letter(j)].width = w

    def title(self, text, sz=13):
        self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=self.n)
        st(self.ws.cell(self.r, 1, text), b=True, sz=sz, color="FFFFFF", fill=NAVY); self.r += 1

    def note(self, text, fill=GRN, h=None):
        self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=self.n)
        st(self.ws.cell(self.r, 1, text), sz=9, fill=fill, ha="right", wrap=True)
        self.ws.row_dimensions[self.r].height = h or max(18, 15 * (1 + len(text) // 120)); self.r += 1

    def head(self, cols):
        for j, h in enumerate(cols, 1):
            st(self.ws.cell(self.r, j, h), b=True, fill=LT, wrap=True)
        self.ws.row_dimensions[self.r].height = 30; self.r += 1

    def row(self, vals, *, b=False, fill=None, fmts=None):
        for j, v in enumerate(vals, 1):
            if isinstance(v, float): v = round(v, 3)
            f = (fmts or {}).get(j) or ("0.000" if isinstance(v, float) else None)
            st(self.ws.cell(self.r, j, v), b=b, fill=fill, ha="right" if isinstance(v, str) else "center", fmt=f,
               wrap=isinstance(v, str) and len(v) > 30)
        self.r += 1

    def total(self, label, val, *, col=None, fill=GRN):
        col = col or self.n
        if col > 2:
            self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=col - 1)
        st(self.ws.cell(self.r, 1, label), b=True, fill=fill, ha="right")
        st(self.ws.cell(self.r, col, round(val, 2)), b=True, fill=fill, fmt="0.00"); self.r += 1

    def gap(self, k=1):
        self.r += k
