from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.metrics import compute_metrics, series_dataframe
from core.model import SimulationParams, run_simulation
from core.storage import Storage, save_run_artifacts

st.title("Одиночный расчет")
store = Storage()

if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False


def default_params() -> dict:
    return {
        "r_max": 4e-3,
        "z_max": 3e-3,
        "vessel_diameter": 80e-6,
        "vessel_depth": 0.7e-3,
        "nr": 60,
        "nz": 72,
        "dt": 2e-4,
        "n_pulses": 5,
        "perfusion_on": True,
        "laser": {
            "mode": "578",
            "a578": 5e8,
            "mu578": 1500.0,
            "a511": 4.5e8,
            "mu511": 2200.0,
            "p578": 0.7,
            "p511": 0.3,
            "w0": 0.6e-3,
            "tp": 1.5e-3,
            "f": 10.0,
        },
        "bc": {"outer_r": "insulated", "outer_h": 12.0, "top_h": 22.0, "zmax": "dirichlet"},
    }


with st.sidebar:
    st.subheader("Действия")
    if st.button("Загрузить baseline"):
        st.session_state.loaded_baseline = json.loads(Path("params/baseline.json").read_text())
    if st.button("Стоп"):
        st.session_state.stop_requested = True

base = st.session_state.get("loaded_baseline", default_params())

with st.form("single_run_form"):
    c1, c2, c3 = st.columns(3)
    diameter_um = c1.number_input(
        "Диаметр D (мкм)", 30.0, 250.0, float(base["vessel_diameter"] * 1e6)
    )
    depth_mm = c1.number_input("Глубина (мм)", 0.2, 1.8, float(base["vessel_depth"] * 1e3))
    mode = c1.selectbox(
        "Режим",
        ["578", "578_511"],
        index=0 if base["laser"]["mode"] == "578" else 1,
    )

    tp_ms = c2.number_input(
        "Длительность импульса tp (мс)",
        0.1,
        10.0,
        float(base["laser"]["tp"] * 1e3),
    )
    f_hz = c2.number_input("Частота f (Гц)", 1.0, 80.0, float(base["laser"]["f"]))
    n_pulses = c2.number_input("Количество импульсов", 1, 30, int(base["n_pulses"]))

    w0_mm = c3.number_input("Радиус пучка w0 (мм)", 0.2, 3.0, float(base["laser"]["w0"] * 1e3))
    profile = c3.radio("Профиль расчета", ["Быстрый", "Точный"], horizontal=True)
    perf_on = c3.checkbox("Перфузия включена", value=bool(base["perfusion_on"]))

    a578 = st.number_input("A578", value=float(base["laser"]["a578"]))
    mu578 = st.number_input("mu578 (1/м)", value=float(base["laser"]["mu578"]))
    a511 = st.number_input("A511", value=float(base["laser"]["a511"]))
    mu511 = st.number_input("mu511 (1/м)", value=float(base["laser"]["mu511"]))
    p578 = st.slider("Доля p578", 0.0, 1.0, float(base["laser"]["p578"]))
    p511 = 1.0 - p578

    run_clicked = st.form_submit_button("Запустить")

if run_clicked:
    st.session_state.stop_requested = False
    nr, nz, dt = (52, 60, 4e-4) if profile == "Быстрый" else (88, 100, 1.5e-4)
    params_dict = {
        **base,
        "vessel_diameter": diameter_um * 1e-6,
        "vessel_depth": depth_mm * 1e-3,
        "nr": nr,
        "nz": nz,
        "dt": dt,
        "n_pulses": int(n_pulses),
        "perfusion_on": perf_on,
        "laser": {
            "mode": mode,
            "a578": a578,
            "mu578": mu578,
            "a511": a511,
            "mu511": mu511,
            "p578": p578,
            "p511": p511,
            "w0": w0_mm * 1e-3,
            "tp": tp_ms * 1e-3,
            "f": f_hz,
        },
    }

    try:
        params = SimulationParams(**params_dict)
    except Exception as exc:
        st.error(f"Ошибка параметров: {exc}")
    else:
        progress = st.progress(0.0)
        result = run_simulation(
            params,
            progress_callback=lambda x: progress.progress(min(float(x), 1.0)),
            stop_flag=lambda: st.session_state.stop_requested,
        )
        metrics = compute_metrics(result)
        series = series_dataframe(result)

        run_id = store.add_run("single_run", params.model_dump(), metrics, run_dir="")
        run_dir = save_run_artifacts(
            "results/runs",
            run_id,
            params.model_dump(),
            metrics,
            series,
            result.fields,
            result.times,
        )
        store.update_run_dir(run_id, run_dir)

        st.success(f"Расчет завершен. ID={run_id}")
        st.json(metrics)

        t_index = st.slider("Индекс времени", 0, len(result.times) - 1, len(result.times) - 1)
        fig = go.Figure(
            data=go.Heatmap(
                x=result.z * 1e3,
                y=result.r * 1e3,
                z=result.fields[t_index],
                colorscale="Turbo",
                colorbar_title="K",
            )
        )
        fig.update_layout(title="Тепловая карта T(r,z)", xaxis_title="z [мм]", yaxis_title="r [мм]")
        st.plotly_chart(fig, use_container_width=True)

        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(x=result.times, y=result.center_series, name="Центр сосуда"))
        fig_ts.add_trace(go.Scatter(x=result.times, y=result.wall_series, name="Стенка сосуда"))
        fig_ts.update_layout(
            title="Температура во времени",
            xaxis_title="t [с]",
            yaxis_title="T [K]",
        )
        st.plotly_chart(fig_ts, use_container_width=True)

        center_j = int(np.argmin(np.abs(result.z - params.vessel_depth)))
        prof_r = go.Figure(go.Scatter(x=result.r * 1e3, y=result.fields[t_index][:, center_j]))
        prof_r.update_layout(
            title="Профиль T(r) на глубине сосуда",
            xaxis_title="r [мм]",
            yaxis_title="T [K]",
        )
        st.plotly_chart(prof_r, use_container_width=True)

        center_i = 0
        prof_z = go.Figure(go.Scatter(x=result.z * 1e3, y=result.fields[t_index][center_i, :]))
        prof_z.update_layout(title="Профиль T(z) на оси", xaxis_title="z [мм]", yaxis_title="T [K]")
        st.plotly_chart(prof_z, use_container_width=True)

        frames = [
            go.Frame(
                data=[
                    go.Heatmap(
                        x=result.z * 1e3,
                        y=result.r * 1e3,
                        z=f,
                        colorscale="Turbo",
                    )
                ],
                name=str(i),
            )
            for i, f in enumerate(result.fields)
        ]
        anim = go.Figure(
            data=frames[0].data,
            frames=frames,
            layout=go.Layout(
                title="Анимация тепловой карты",
                updatemenus=[
                    {
                        "type": "buttons",
                        "buttons": [{"label": "▶ Пуск", "method": "animate", "args": [None]}],
                    }
                ],
            ),
        )
        st.plotly_chart(anim, use_container_width=True)

        st.dataframe(series, use_container_width=True)

        st.download_button(
            "Экспорт CSV",
            data=series.to_csv(index=False),
            file_name=f"run_{run_id}_series.csv",
        )

        zip_path = Path(run_dir).with_suffix(".zip")
        with ZipFile(zip_path, "w") as zf:
            for fpath in Path(run_dir).glob("*"):
                zf.write(fpath, arcname=fpath.name)
        st.download_button(
            "Экспорт пакета (zip)",
            data=zip_path.read_bytes(),
            file_name=zip_path.name,
        )
