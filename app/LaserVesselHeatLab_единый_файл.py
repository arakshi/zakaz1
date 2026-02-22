from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.metrics import compute_metrics, series_dataframe
from core.model import SimulationParams, run_simulation
from core.optimize import random_search
from core.paths import REPORTS_DIR, RESULTS_DIR, RUNS_DIR, data_file, params_file
from core.report import generate_html_report
from core.storage import Storage, save_run_artifacts
from core.sweep import run_sweep

st.set_page_config(page_title="LaserVesselHeatLab", layout="wide")
st.title("LaserVesselHeatLab")

store = Storage()


@st.cache_data
def baseline_dict() -> dict:
    path = params_file("baseline.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_dashboard() -> None:
    st.subheader("Главная")
    df = store.list_runs(limit=50)
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего прогонов", int(df.shape[0]))
    if not df.empty:
        c2.metric("Лучший UniformityIndex", f"{df['uniformity'].min():.4f}")
        c3.metric("Худший UniformityIndex", f"{df['uniformity'].max():.4f}")
        st.dataframe(
            df[["id", "name", "created_at", "uniformity", "tmax"]],
            use_container_width=True,
        )
    else:
        st.info("История пока пустая.")


def render_single() -> None:
    st.subheader("Одиночный расчет")
    base = baseline_dict() or {
        "vessel_diameter": 80e-6,
        "vessel_depth": 0.7e-3,
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
    }

    with st.form("single_form"):
        c1, c2, c3 = st.columns(3)
        d_um = c1.number_input("Диаметр D (мкм)", 30.0, 250.0, float(base["vessel_diameter"] * 1e6))
        depth_mm = c1.number_input("Глубина (мм)", 0.2, 1.8, float(base["vessel_depth"] * 1e3))
        mode = c1.selectbox(
            "Режим",
            ["578", "578_511"],
            index=0 if base["laser"]["mode"] == "578" else 1,
        )

        tp_ms = c2.number_input("tp (мс)", 0.1, 10.0, float(base["laser"]["tp"] * 1e3))
        f_hz = c2.number_input("f (Гц)", 1.0, 80.0, float(base["laser"]["f"]))
        n_pulses = c2.number_input("Импульсов", 1, 30, int(base["n_pulses"]))

        w0_mm = c3.number_input("w0 (мм)", 0.2, 3.0, float(base["laser"]["w0"] * 1e3))
        profile = c3.radio("Профиль", ["Быстрый", "Точный"], horizontal=True)
        perf_on = c3.checkbox("Перфузия", value=bool(base.get("perfusion_on", True)))

        a578 = st.number_input("A578", value=float(base["laser"]["a578"]))
        mu578 = st.number_input("mu578 (1/м)", value=float(base["laser"]["mu578"]))
        a511 = st.number_input("A511", value=float(base["laser"]["a511"]))
        mu511 = st.number_input("mu511 (1/м)", value=float(base["laser"]["mu511"]))
        p578 = st.slider("p578", 0.0, 1.0, float(base["laser"]["p578"]))
        run_clicked = st.form_submit_button("Запустить")

    if not run_clicked:
        return

    nr, nz, dt = (52, 60, 4e-4) if profile == "Быстрый" else (88, 100, 1.5e-4)
    params_dict = {
        "vessel_diameter": d_um * 1e-6,
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
            "p511": 1.0 - p578,
            "w0": w0_mm * 1e-3,
            "tp": tp_ms * 1e-3,
            "f": f_hz,
        },
    }

    try:
        params = SimulationParams(**params_dict)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Ошибка параметров: {exc}")
        return

    progress = st.progress(0.0)
    result = run_simulation(params, progress_callback=lambda x: progress.progress(float(x)))
    metrics = compute_metrics(result)
    series = series_dataframe(result)

    run_id = store.add_run("single_run", params.model_dump(), metrics, run_dir="")
    run_dir = save_run_artifacts(
        str(RUNS_DIR),
        run_id,
        params.model_dump(),
        metrics,
        series,
        result.fields,
        result.times,
    )
    store.update_run_dir(run_id, run_dir)

    st.success(f"Готово. ID={run_id}")
    st.json(metrics)

    t_idx = st.slider(
        "Индекс времени",
        0,
        len(result.times) - 1,
        len(result.times) - 1,
        key="single_t",
    )
    fig = go.Figure(
        go.Heatmap(
            x=result.z * 1e3,
            y=result.r * 1e3,
            z=result.fields[t_idx],
            colorscale="Turbo",
        )
    )
    fig.update_layout(title="Тепловая карта", xaxis_title="z [мм]", yaxis_title="r [мм]")
    st.plotly_chart(fig, use_container_width=True)

    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(x=result.times, y=result.center_series, name="Центр"))
    fig_ts.add_trace(go.Scatter(x=result.times, y=result.wall_series, name="Стенка"))
    st.plotly_chart(fig_ts, use_container_width=True)

    st.download_button(
        "Экспорт CSV",
        series.to_csv(index=False),
        file_name=f"run_{run_id}_series.csv",
    )
    zip_path = Path(run_dir).with_suffix(".zip")
    with ZipFile(zip_path, "w") as zf:
        for fpath in Path(run_dir).glob("*"):
            zf.write(fpath, arcname=fpath.name)
    st.download_button("Экспорт пакета", zip_path.read_bytes(), file_name=zip_path.name)


def render_sweep() -> None:
    st.subheader("Пакетный расчет")
    sweeps_path = data_file("sweeps.csv")
    if not sweeps_path.exists():
        st.error(f"Нет файла: {sweeps_path}")
        return

    default = pd.read_csv(sweeps_path)
    edited = st.data_editor(default, num_rows="dynamic", use_container_width=True)
    workers = st.slider("Процессы", 1, 8, 2, key="sweep_workers")

    if st.button("Запустить sweep"):
        progress = st.progress(0.0)
        out = run_sweep(
            edited,
            max_workers=workers,
            progress_cb=lambda x: progress.progress(float(x)),
        )
        st.dataframe(out, use_container_width=True)
        heat = out.pivot_table(
            index="vessel_diameter",
            columns="vessel_depth",
            values="UniformityIndex",
            aggfunc="mean",
        )
        st.plotly_chart(px.imshow(heat, title="Heatmap D-depth"), use_container_width=True)
        st.plotly_chart(
            px.scatter(out, x="UniformityIndex", y="Tmax_vessel", title="Pareto"),
            use_container_width=True,
        )
        RESULTS_DIR.mkdir(exist_ok=True)
        out.to_csv(RESULTS_DIR / "sweep_results.csv", index=False)


def render_compare() -> None:
    st.subheader("Сравнение")
    df = store.list_runs(limit=200)
    if df.empty:
        st.info("Нет прогонов")
        return
    picks = st.multiselect("Выбираем прогоны", df["id"].tolist(), default=df["id"].tolist()[:2])
    if len(picks) < 2:
        return

    fig = go.Figure()
    for rid in picks:
        run = store.get_run(int(rid))
        run_dir = Path(run["run_dir"])
        if not run_dir.exists():
            continue
        series = pd.read_csv(run_dir / "series.csv")
        fig.add_trace(go.Scatter(x=series["time_s"], y=series["center_K"], name=f"{rid} центр"))
    st.plotly_chart(fig, use_container_width=True)


def render_opt() -> None:
    st.subheader("Оптимизация")
    base_path = params_file("baseline.json")
    if not base_path.exists():
        st.error(f"Нет файла: {base_path}")
        return
    base = json.loads(base_path.read_text(encoding="utf-8"))
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
        st.plotly_chart(
            px.line(df.reset_index(), x="index", y="score", title="Сходимость"),
            use_container_width=True,
        )


def render_report() -> None:
    st.subheader("Отчет")
    df = store.list_runs(limit=200)
    if df.empty:
        st.info("Нет прогонов")
        return
    rid = st.selectbox("Прогон", df["id"].tolist())
    if st.button("Сформировать HTML"):
        payload = store.get_run(int(rid))
        out = REPORTS_DIR / f"run_{rid:05d}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        generate_html_report(payload, str(out))
        st.success(f"Готово: {out}")
        st.download_button("Скачать отчет", out.read_text(encoding="utf-8"), file_name=out.name)


tabs = st.tabs(
    ["Главная", "Одиночный расчет", "Пакетный расчет", "Сравнение", "Оптимизация", "Отчет"]
)
with tabs[0]:
    render_dashboard()
with tabs[1]:
    render_single()
with tabs[2]:
    render_sweep()
with tabs[3]:
    render_compare()
with tabs[4]:
    render_opt()
with tabs[5]:
    render_report()
