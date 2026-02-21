from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.sweep import run_sweep

st.title("Sweep")
default = pd.read_csv("data/sweeps.csv")
edited = st.data_editor(default, num_rows="dynamic", use_container_width=True)
workers = st.slider("Workers", 1, 8, 2)

if st.button("Run Sweep"):
    progress = st.progress(0.0)
    try:
        out = run_sweep(
            edited,
            max_workers=workers,
            progress_cb=lambda x: progress.progress(float(x)),
        )
    except Exception as exc:
        st.error(str(exc))
    else:
        st.success("Sweep complete")
        st.dataframe(out, use_container_width=True)

        heat = out.pivot_table(
            index="vessel_diameter",
            columns="vessel_depth",
            values="UniformityIndex",
            aggfunc="mean",
        )
        fig_h = px.imshow(
            heat,
            labels={"color": "UniformityIndex"},
            title="Uniformity heatmap D vs depth",
        )
        st.plotly_chart(fig_h, use_container_width=True)

        fig_3d = px.scatter_3d(
            out, x="laser.tp", y="laser.f", z="UniformityIndex", color="Tmax_vessel"
        )
        st.plotly_chart(fig_3d, use_container_width=True)

        fig_p = px.scatter(
            out,
            x="UniformityIndex",
            y="Tmax_vessel",
            hover_data=["vessel_diameter", "vessel_depth"],
        )
        st.plotly_chart(fig_p, use_container_width=True)

        Path("results").mkdir(exist_ok=True)
        out.to_csv("results/sweep_results.csv", index=False)
        st.download_button("Download sweep CSV", out.to_csv(index=False), "sweep_results.csv")
