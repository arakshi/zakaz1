from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.storage import Storage

st.title("Сравнение прогонов")
store = Storage()
df = store.list_runs(limit=200)

if df.empty:
    st.info("Нет прогонов для сравнения")
    st.stop()

choices = st.multiselect("Выберите прогоны", df["id"].tolist(), default=df["id"].tolist()[:2])
if len(choices) < 2:
    st.warning("Нужно выбрать минимум 2 прогона")
    st.stop()

fig = go.Figure()
for run_id in choices:
    run = store.get_run(int(run_id))
    run_dir = Path(run["run_dir"])
    if not run_dir.exists():
        continue
    import pandas as pd

    s = pd.read_csv(run_dir / "series.csv")
    fig.add_trace(go.Scatter(x=s["time_s"], y=s["center_K"], name=f"Прогон {run_id}: центр"))
fig.update_layout(title="Сравнение T(t) в центре сосуда", xaxis_title="t [с]", yaxis_title="T [K]")
st.plotly_chart(fig, use_container_width=True)

mrows = []
for run_id in choices:
    run = store.get_run(int(run_id))
    mrows.append({"id": run_id, **run["metrics"]})
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
    fig_d.update_layout(title=f"Разностная карта: прогон {r1} - прогон {r2}")
    st.plotly_chart(fig_d, use_container_width=True)
