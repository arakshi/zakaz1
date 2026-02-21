"""Точка входа Streamlit для LaserVesselHeatLab."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _relaunch_via_streamlit() -> None:
    """Перезапустить текущий файл через `python -m streamlit run ...`."""
    script_path = Path(__file__).resolve()
    cmd = [sys.executable, "-m", "streamlit", "run", str(script_path)]
    try:
        subprocess.run(cmd, check=False)
    except Exception as exc:  # noqa: BLE001
        print(
            "Не удалось автоматически запустить Streamlit. "
            "Запустите вручную:\n"
            f"  streamlit run {script_path}\n"
            f"Причина: {exc}"
        )
    sys.exit(0)


def main() -> None:
    """Запустить приложение в корректном режиме Streamlit."""
    if importlib.util.find_spec("streamlit") is None:
        print("Не найден пакет streamlit. Установите зависимости: pip install -e .")
        sys.exit(1)

    from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

    if __name__ == "__main__" and get_script_run_ctx() is None:
        print("Обнаружен запуск через `python app/main.py` (например, из PyCharm).")
        print("Автоматически переключаюсь на корректный режим Streamlit...")
        _relaunch_via_streamlit()

    import streamlit as st

    from core.storage import Storage

    st.set_page_config(page_title="LaserVesselHeatLab", layout="wide")
    st.title("LaserVesselHeatLab")
    st.caption(
        "2D осесимметричная модель биотеплопереноса "
        "для импульсного лазерного нагрева сосудов"
    )

    store = Storage()
    df = store.list_runs(limit=20)

    col1, col2, col3 = st.columns(3)
    col1.metric("Всего прогонов", int(df.shape[0]))
    if not df.empty:
        col2.metric("Лучший UniformityIndex", f"{df['uniformity'].min():.4f}")
        col3.metric("Худший UniformityIndex", f"{df['uniformity'].max():.4f}")

    st.subheader("Последние прогоны")
    if df.empty:
        st.info("Пока нет прогонов. Перейдите на страницу «Одиночный расчет».")
    else:
        st.dataframe(
            df[["id", "name", "created_at", "uniformity", "tmax"]],
            use_container_width=True,
        )

    st.markdown(
        "Используйте боковое меню: **Одиночный расчет**, **Пакетный расчет**, "
        "**Сравнение**, **Оптимизация**, **Отчет**."
    )


if __name__ == "__main__":
    main()
