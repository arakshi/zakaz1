# COMSOL 6.1: Лазерный нагрев сосудов в коже (Java API)

Проект автоматически собирает и считает модель нагрева сосуда в коже для двух спектральных режимов:
- `578` (лазер на парах меди 578 нм)
- `578_511` (суммарный источник 578 + 511 нм)

Реализованы **обе геометрии**:
- `src/build_model_3d.java` — 3D приоритетная модель (параллелепипед кожи + цилиндрический сосуд вдоль оси Y).
- `src/build_model_2d_axi.java` — fallback 2D axisymmetric модель (r-z).

`src/run_sweeps.java` читает `data/sweeps.csv`, строит/считает кейсы, сохраняет `.mph` и собирает метрики в `results/metrics.csv`.

---

## Требования

- COMSOL Multiphysics **6.1**.
- Java API COMSOL (стандартно доступен через `comsol batch` и/или `comsolcompile`).
- Без сторонних Java-библиотек.

---

## Структура

- `params/baseline.json` — базовый кейс для экспорта графики.
- `data/sweeps.csv` — наборы параметров для параметрических прогонов.
- `src/build_model_3d.java` — построение 3D модели.
- `src/build_model_2d_axi.java` — построение 2D axisymmetric модели.
- `src/postprocess.java` — метрики и экспорт графики.
- `src/run_sweeps.java` — оркестратор sweep.
- `results/models/` — сохраненные `.mph`.
- `results/figures/` — PNG графики базового кейса.
- `results/metrics.csv` — итоговые метрики.

---

## Запуск

> Ниже даны типовые схемы для COMSOL 6.x. В разных установках имена скриптов (`comsolcompile`, `comsolbatch`) могут немного отличаться.

### Linux

```bash
mkdir -p build results/models results/figures
comsol compile -inputfile src/build_model_3d.java -outputfile build/
comsol compile -inputfile src/build_model_2d_axi.java -outputfile build/
comsol compile -inputfile src/postprocess.java -outputfile build/
comsol compile -inputfile src/run_sweeps.java -outputfile build/
comsol batch -classpath build -inputfile src/run_sweeps.java -outputfile results/log.txt
```

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force build,results\models,results\figures | Out-Null
comsol compile -inputfile src\build_model_3d.java -outputfile build\
comsol compile -inputfile src\build_model_2d_axi.java -outputfile build\
comsol compile -inputfile src\postprocess.java -outputfile build\
comsol compile -inputfile src\run_sweeps.java -outputfile build\
comsol batch -classpath build -inputfile src\run_sweeps.java -outputfile results\log.txt
```

Если ваша сборка COMSOL требует `comsolbatch`/`comsolcompile`, замените команды эквивалентно.

---


## Запуск через Python (удобно для PyCharm, COMSOL 6.2)

Если не хотите руками вводить длинные команды в терминале, используйте:
- `scripts/run_comsol_from_python.py`

Шаги (Windows + PyCharm):
1. Откройте проект в PyCharm.
2. Откройте `scripts/run_comsol_from_python.py`.
3. Запустите файл (Run). Скрипт сам попробует определить корень проекта (даже если Working Directory = `scripts`).
4. Если COMSOL не находится автоматически, передайте путь к `comsol.exe`:
   - Run/Debug Configuration -> Parameters:
   - `--comsol "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe"`

CLI-эквивалент:

```powershell
python scripts/run_comsol_from_python.py
```

или с явным путём к COMSOL:

```powershell
python scripts/run_comsol_from_python.py --comsol "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe"
```


Если удобнее, можно один раз задать переменную окружения и не передавать путь каждый запуск:

```powershell
$env:COMSOL_EXE = "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe"
python scripts/run_comsol_from_python.py
```

Скрипт автоматически:
- создаст `build/`, `results/models/`, `results/figures/`;
- выполнит `comsol compile` для Java-файлов;
- выполнит `comsol batch` для `src/run_sweeps.java`.

---


### Если COMSOL открылся, но папки результатов пустые


Важно для Windows: если при запуске открывается GUI COMSOL и «ничего не происходит»,
лаунчер теперь автоматически пытается использовать `comsolcompile.exe` и `comsolbatch.exe`
из той же папки, что и `comsol.exe` (это правильный режим для автосборки без ручных команд).

Рекомендуемые параметры в PyCharm (Run Configuration -> Parameters):

```text
--comsol "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe"
```

Новая версия лаунчера дополнительно:
- печатает `Project dir` и реальный путь до COMSOL;
- очищает старые результаты перед запуском;
- проверяет, что созданы **новые** `.mph` и `metrics.csv` именно в текущем запуске;
- на Windows пытается найти `comsolcompile.*` / `comsolbatch.*` рядом с `comsol.exe`.

Если видите в выводе предупреждение про fallback на `comsol.exe compile/batch`,
значит direct-tools не найдены и нужно проверить установку COMSOL в `.../bin/win64/`.

Это обычно значит, что внутри COMSOL была ошибка (лицензия/модуль/тег API), но Python-скрипт раньше не валился.
Теперь лаунчер проверяет наличие результатов и выдаёт явную ошибку, если `.mph` и `metrics.csv` не создались.


Если в выводе были строки вида `Input filename is not specified` от `comsolcompile`,
лаунчер теперь автоматически пробует альтернативный формат запуска `comsolcompile <file.java>`
и несколько вариантов запуска `comsolbatch` для класса `run_sweeps`.


Также лаунчер компилирует Java-файлы одним вызовом `comsolcompile` (а не по одному файлу),
чтобы корректно разрешались ссылки между классами (`run_sweeps`, `build_model_*`, `postprocess`).

Если ошибка повторяется, приложите:
- `results/log.txt`
- `C:/Users/<USER>/.comsol/v62/logs/compile*.log`

Что делать:
1. Откройте `results/log.txt` и найдите первую ошибку COMSOL.
2. Если нужна диагностика без падения скрипта, запустите с флагом:

```powershell
python scripts/run_comsol_from_python.py --comsol "D:/COMSOL62/Multiphysics/bin/win64/comsol.exe" --skip-output-check
```

3. Проверьте, что в `results/models/` есть `*.mph`, а в `results/` есть `metrics.csv`.

## Переключение 3D / 2D

В `data/sweeps.csv` есть поле `geometry`:
- `3d` — использовать `build_model_3d`
- `2d` — использовать `build_model_2d_axi`

Если 3D слишком тяжелая:
1. В `data/sweeps.csv` выставьте `geometry=2d` для всех строк.
2. Либо удалите/закомментируйте 3D-кейсы.

---

## Bioheat vs Heat Transfer in Solids

В коде есть параметр `useBioheat` (0/1):
- `1`: попытка использовать Bioheat интерфейс (`bioheat`) если доступен.
- `0`: Heat Transfer in Solids + пользовательский объемный источник:
  \[
  Q = Q_{laser} - w_b c_b (T - T_{blood})
  \]

Если Bioheat интерфейс в вашей лицензии недоступен, ставьте `useBioheat=0` (в baseline/sweep).

---

## Временной диапазон и шаг

- `t_end = Npulses/f + extra_cool`
- Решатель: time-dependent, BDF, автоматические шаги.
- Рекомендуемый максимум шага: `maxstep = tp/10` (устанавливается в модели через параметр `dtmax`).

---

## Метрики равномерности

Для домена сосуда (`vessel`) считаются:
- `Tmax_vessel`
- `Tmin_vessel`
- `Tmean_vessel`
- `Std_vessel = sqrt(<(T-Tmean)^2>)`
- `UniformityIndex = (Tmax - Tmin)/Tmean`

Метрики рассчитываются на:
- конце последнего импульса (`t_eval = Npulses/f`),
- и дополнительно может быть использован момент пика (см. `postprocess.java`, выборкой по time grid).

CSV с результатами: `results/metrics.csv`.

---

## Экспорт графики

Для базового кейса из `params/baseline.json` экспортируются PNG в `results/figures/`:
1. Температурное поле (slice/cut) в момент `t_eval`.
2. `T(t)` в центре сосуда и на стенке.

Чтобы отключить экспорт (ускорение sweep), установите `exportFigures=0` в baseline.

---

## Где менять параметры

- Базовый кейс: `params/baseline.json`
- Sweep-сетка: `data/sweeps.csv`
- Формулы источника и перфузии: `src/build_model_3d.java`, `src/build_model_2d_axi.java`

Все ключевые коэффициенты заданы параметрами COMSOL (`A_578`, `A_511`, `mu_eff_578`, `mu_eff_511`, `p578`, `p511`, `w0`, `tp`, `f`, и т.д.).
