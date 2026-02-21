from __future__ import annotations

import json
from pathlib import Path

import plotly.express as px
import streamlit as st

from core.optimize import random_search

st.title("Оптимизация")
base = json.loads(Path("params/baseline.json").read_text())
limit = st.number_input("Ограничение Tmax [K]", 320.0, 380.0, 345.15)
n_iter = st.slider("Итерации", 5, 60, 20)

if st.button("Запустить оптимизацию"):
    progress = st.progress(0.0)
    df = random_search(
        base,
        n_iter=n_iter,
        tmax_limit=limit,
        progress_cb=lambda x: progress.progress(float(x)),
    )
    st.dataframe(df.head(10), use_container_width=True)
    fig = px.line(df.reset_index(), x="index", y="score", title="Сходимость оптимизации")
    st.plotly_chart(fig, use_container_width=True)
