import csv
import os
from datetime import datetime
from typing import Dict

import streamlit as st

from core.constants import MODEL_DATA_FILES, MONTH_ORDER, get_data_file_for_model
from tournaments.groups import compute_final_classification_from_round5
from tournaments.updown import compute_final_classification_from_updown


def _pt_month_name(m: int) -> str:
    return MONTH_ORDER[m - 1] if 1 <= m <= 12 else str(m)


def append_final_table_to_csv_if_applicable(t: Dict):
    model = t.get("model")
    data_file = get_data_file_for_model(model)
    if not data_file or model not in MODEL_DATA_FILES:
        return

    if t.get("tipo") == "UPDOWN":
        df_final = compute_final_classification_from_updown(t)
    else:
        df_final = compute_final_classification_from_round5(t)

    if df_final.empty:
        return

    dy = int(t.get("date", {}).get("year", datetime.now().year))
    dm = int(t.get("date", {}).get("month", datetime.now().month))
    dd = int(t.get("date", {}).get("day", datetime.now().day))
    mname = _pt_month_name(dm)

    rows = []
    for _, r in df_final.iterrows():
        rows.append(
            {
                "Year": dy,
                "Month": mname,
                "Day": dd,
                "Position": int(r["Pos"]),
                "Team": str(r["Dupla / Equipa"]),
            }
        )

    file_exists = data_file.exists()

    if file_exists:
        with data_file.open("rb") as fh_check:
            fh_check.seek(0, os.SEEK_END)
            size = fh_check.tell()
            if size > 0:
                fh_check.seek(-1, os.SEEK_END)
                last_byte = fh_check.read(1)
            else:
                last_byte = b"\n"
        if last_byte not in (b"\n", b"\r"):
            with data_file.open("a", encoding="utf-8", newline="") as fh_fix:
                fh_fix.write("\n")

    with data_file.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Year", "Month", "Day", "Position", "Team"])
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)

    st.cache_data.clear()
