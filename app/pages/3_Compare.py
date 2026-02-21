from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.storage import Storage

st.title("Compare Runs")
store = Storage()
df = store.list_runs(limit=200)

if df.empty:
    st.info("No runs to compare")
    st.stop()

choices = st.multiselect("Select runs", df["id"].tolist(), default=df["id"].tolist()[:2])
if len(choices) < 2:
    st.warning("Choose at least 2 runs")
    st.stop()

fig = go.Figure()
for run_id in choices:
    run = store.get_run(int(run_id))
    run_dir = Path(run["run_dir"])
    if not run_dir.exists():
        continue
    import pandas as pd

    s = pd.read_csv(run_dir / "series.csv")
    fig.add_trace(go.Scatter(x=s["time_s"], y=s["center_K"], name=f"Run {run_id} center"))
fig.update_layout(title="Center temperature comparison", xaxis_title="t [s]", yaxis_title="T [K]")
st.plotly_chart(fig, use_container_width=True)

mrows = []
for run_id in choices:
    run = store.get_run(int(run_id))
    m = run["metrics"]
    mrows.append({"id": run_id, **m})
st.dataframe(mrows, use_container_width=True)

if len(choices) >= 2:
    r1, r2 = choices[:2]
    run1 = store.get_run(int(r1))
    run2 = store.get_run(int(r2))
    npz1 = np.load(Path(run1["run_dir"]) / "fields.npz")
    npz2 = np.load(Path(run2["run_dir"]) / "fields.npz")
    i = min(len(npz1["fields"]) - 1, len(npz2["fields"]) - 1)
    dmap = npz1["fields"][i] - npz2["fields"][i]
    fig_d = go.Figure(go.Heatmap(z=dmap, colorscale="RdBu", zmid=0.0))
    fig_d.update_layout(title=f"Difference map Run {r1} - Run {r2}")
    st.plotly_chart(fig_d, use_container_width=True)
