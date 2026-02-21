from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.report import generate_html_report
from core.storage import Storage

st.title("Report")
store = Storage()
df = store.list_runs(limit=200)
if df.empty:
    st.info("No runs")
    st.stop()

run_id = st.selectbox("Run", df["id"].tolist())
if st.button("Generate HTML report"):
    payload = store.get_run(int(run_id))
    out = Path("results/reports") / f"run_{run_id:05d}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    generate_html_report(payload, str(out))
    st.success(f"Saved: {out}")
    st.download_button("Download report", out.read_text(encoding="utf-8"), file_name=out.name)
