"""Streamlit entrypoint for LaserVesselHeatLab."""

from __future__ import annotations

import streamlit as st

from core.storage import Storage

st.set_page_config(page_title="LaserVesselHeatLab", layout="wide")
st.title("LaserVesselHeatLab")
st.caption("2D axisymmetric bioheat simulation for pulsed 578/511 nm vascular heating")

store = Storage()
df = store.list_runs(limit=20)

col1, col2, col3 = st.columns(3)
col1.metric("Total runs", int(df.shape[0]))
if not df.empty:
    col2.metric("Best UniformityIndex", f"{df['uniformity'].min():.4f}")
    col3.metric("Worst UniformityIndex", f"{df['uniformity'].max():.4f}")

st.subheader("Recent runs")
if df.empty:
    st.info("No runs yet. Go to Single Run page to create one.")
else:
    st.dataframe(df[["id", "name", "created_at", "uniformity", "tmax"]], use_container_width=True)

st.markdown(
    "Use the sidebar to open **Single Run**, **Sweep**, **Compare**, "
    "**Optimization**, and **Report** pages."
)
