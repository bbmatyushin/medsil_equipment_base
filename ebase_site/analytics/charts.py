"""Спецификации графиков для `charts.js`.

View собирает спецификацию через `chart_spec()`, шаблон выводит её через
`json_script` (см. `includes/chart.html`), а `static/analytics/js/charts.js`
строит по ней график Chart.js. Спецификация — обычный dict из строк, чисел
и списков, без Decimal и дат.
"""

import math

KINDS = ("bar", "line", "scatter")
FORMATS = ("money", "count", "percent")
AXES = ("y", "y2")

# Радиус пузырька scatter, px
BUBBLE_MIN_RADIUS = 4
BUBBLE_MAX_RADIUS = 20


def to_float(value) -> float:
    """Число для графика: None -> 0.0, Decimal/int -> float с точностью до копеек."""
    if value is None:
        return 0.0
    return round(float(value), 2)


def bubble_radius(value, full_scale) -> float:
    """Радиус пузырька по модулю значения, знак не важен.

    0 — минимальный радиус, |value| ≥ `full_scale` — максимальный. Радиус
    растёт как корень из доли шкалы, чтобы площадь пузырька росла примерно
    пропорционально значению.
    """
    share = min(abs(to_float(value)) / full_scale, 1.0)
    radius = BUBBLE_MIN_RADIUS + (BUBBLE_MAX_RADIUS - BUBBLE_MIN_RADIUS) * math.sqrt(
        share
    )
    return round(radius, 1)


def _point(point: dict) -> dict:
    """Точка scatter: координаты в float, подпись и ссылка — строки.

    Необязательный `r` — радиус пузырька в px (см. `bubble_radius`).
    """
    result = {
        "x": to_float(point.get("x")),
        "y": to_float(point.get("y")),
        "label": str(point.get("label") or ""),
        "url": point.get("url") or None,
    }
    if point.get("r") is not None:
        result["r"] = to_float(point["r"])
    return result


def _dataset(dataset: dict, chart_kind: str) -> dict:
    """Серия графика с проверенными необязательными ключами."""
    kind = dataset.get("kind") or chart_kind
    axis = dataset.get("axis") or "y"
    fmt = dataset.get("fmt")
    if kind not in KINDS:
        raise ValueError(f"Неизвестный тип серии: {kind!r}")
    if axis not in AXES:
        raise ValueError(f"Неизвестная ось серии: {axis!r}")
    if fmt is not None and fmt not in FORMATS:
        raise ValueError(f"Неизвестный формат серии: {fmt!r}")
    convert = _point if kind == "scatter" else to_float
    return {
        "label": str(dataset.get("label", "")),
        "data": [convert(value) for value in dataset.get("data", [])],
        "kind": kind,
        "axis": axis,
        "sign_colors": bool(dataset.get("sign_colors", False)),
        "fmt": fmt,
    }


def _is_empty(kind: str, labels: list, datasets: list[dict]) -> bool:
    """Нечего рисовать: нет точек (scatter), нет меток или все значения нулевые."""
    if kind == "scatter":
        return not any(dataset["data"] for dataset in datasets)
    if not labels:
        return True
    return all(value == 0 for dataset in datasets for value in dataset["data"])


def chart_spec(
    kind: str,
    labels: list[str],
    datasets: list[dict],
    *,
    fmt: str = "money",
    x_fmt: str = "money",
    horizontal: bool = False,
    stacked: bool = False,
    links: list[str | None] | None = None,
) -> dict:
    """JSON-совместимая спецификация графика.

    - `kind`: "bar" | "line" | "scatter".
    - `datasets`: серии `{"label", "data", "kind"?, "axis"?, "sign_colors"?, "fmt"?}`.
      `kind` серии задаёт смешанный график (линия поверх столбцов),
      `axis="y2"` — вторая шкала справа (только у вертикальных графиков:
      при `horizontal=True` — ValueError), `sign_colors` — окраска столбцов по знаку.
      `fmt` серии (один из форматов ниже) — формат её значений в подсказке
      и, при `axis="y2"`, правой шкалы. Без `fmt` серия на y2 — проценты
      со шкалой 0–100 %, остальные серии — в формате графика (`fmt`).
      Пример: «Накопительно» поверх столбцов — `axis="y2", fmt="money"`
      (правая шкала денег подстраивается под данные и не сплющивает столбцы).
      У scatter `data` — точки `{"x", "y", "label", "url", "r"?}`; `sign_colors`
      у scatter красит точки по знаку `y`.
    - `fmt`: формат значений ("money" | "count" | "percent"); у scatter — ось Y.
    - `x_fmt`: формат оси X у scatter (по умолчанию деньги), у остальных не используется.
    - `links[i]`: куда ведёт клик по i-й метке (None — никуда).
    """
    if kind not in KINDS:
        raise ValueError(f"Неизвестный тип графика: {kind!r}")
    for value in (fmt, x_fmt):
        if value not in FORMATS:
            raise ValueError(f"Неизвестный формат: {value!r}")
    labels = [str(label) for label in labels]
    if links is not None and len(links) != len(labels):
        raise ValueError("Число ссылок не совпадает с числом меток")
    series = [_dataset(dataset, kind) for dataset in datasets]
    if horizontal and any(dataset["axis"] == "y2" for dataset in series):
        # charts.js рисует правую шкалу только у вертикальных графиков:
        # у горизонтального серия легла бы на ось значений графика
        raise ValueError("Правая ось y2 недоступна у горизонтального графика")
    return {
        "kind": kind,
        "labels": labels,
        "datasets": series,
        "format": fmt,
        "x_format": x_fmt,
        "horizontal": horizontal,
        "stacked": stacked,
        "links": list(links or []),
        "empty": _is_empty(kind, labels, series),
    }
