/*
 * Раздел «Аналитика»: графики Chart.js 4 и мелкое поведение формы фильтров.
 * Обычный скрипт без сборки и модулей; подключается после chart.umd.min.js.
 *
 * Шаблон analytics/includes/chart.html выводит спецификацию графика
 * (analytics/charts.py: chart_spec) через json_script и <canvas data-chart="id">.
 * Скрипт:
 *  - на DOMContentLoaded строит графики для всех canvas[data-chart];
 *  - берёт цвета из CSS-переменных analytics.css (--an-c1…--an-c6 и др.);
 *  - пересоздаёт графики при смене темы админки (data-theme на <html>)
 *    и системной темы (режим «auto»);
 *  - клик по столбцу ведёт на links[index], по точке scatter — на point.url.
 */
(function () {
    "use strict";

    // --- Числа по-русски --------------------------------------------------------

    const INTEGER = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
    const COMPACT = new Intl.NumberFormat("ru-RU", {
        notation: "compact",
        maximumFractionDigits: 1,
    });
    const PERCENT = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

    // Полное значение для подсказок: деньги без копеек, проценты с одним знаком
    function formatValue(value, fmt) {
        if (typeof value !== "number" || !isFinite(value)) {
            return "—";
        }
        if (fmt === "percent") {
            return PERCENT.format(value) + " %";
        }
        if (fmt === "count") {
            return INTEGER.format(value);
        }
        if (fmt === "money_short") {
            return COMPACT.format(value) + " ₽";
        }
        return INTEGER.format(value) + " ₽";
    }

    // Подпись деления оси: крупные суммы сокращаются («1,5 млн ₽»), иначе ось съедает график
    function formatTick(value, fmt) {
        if (fmt === "money" || fmt === "money_short") {
            return COMPACT.format(value) + " ₽";
        }
        return formatValue(value, fmt);
    }

    // Длинные подписи категорий (названия клиентов) обрезаются, полное имя — в подсказке.
    // На узком графике сильнее: иначе Chart.js срезает подпись краем холста.
    function shortLabel(label, chartWidth) {
        const text = String(label);
        const max = chartWidth < 500 ? 16 : 28;
        return text.length > max ? text.slice(0, max - 1) + "…" : text;
    }

    // --- Цвета из CSS-переменных ------------------------------------------------

    function readTheme() {
        const styles = getComputedStyle(document.documentElement);
        const value = (name) => styles.getPropertyValue(name).trim();
        return {
            series: [1, 2, 3, 4, 5, 6].map((i) => value("--an-c" + i)),
            positive: value("--an-positive"),
            negative: value("--an-negative"),
            grid: value("--an-grid"),
            text: value("--an-text"),
            ink: value("--an-ink"),
            surface: value("--an-surface"),
            font: getComputedStyle(document.body).fontFamily,
        };
    }

    // --- Переходы по клику ------------------------------------------------------

    // Только относительные ссылки сайта (их строит analytics/links.py); «//…» и «/\…» ведут наружу
    function isLocalUrl(url) {
        return typeof url === "string" && /^\/(?![/\\])/.test(url);
    }

    // Ссылка элемента графика: у scatter — url точки, у остальных — links[index]
    function elementUrl(spec, element) {
        if (spec.kind === "scatter") {
            const point = spec.datasets[element.datasetIndex].data[element.index];
            return point ? point.url : null;
        }
        return spec.links[element.index];
    }

    function firstLink(spec, elements) {
        const url = elements.length ? elementUrl(spec, elements[0]) : null;
        return isLocalUrl(url) ? url : null;
    }

    // --- Сборка конфигурации Chart.js -------------------------------------------

    // Формат значений серии: свой fmt серии, иначе на правой оси y2 — проценты,
    // иначе формат графика
    function seriesFormat(spec, dataset) {
        if (dataset.fmt) {
            return dataset.fmt;
        }
        return dataset.axis === "y2" ? "percent" : spec.format;
    }

    function buildDataset(spec, dataset, index, theme) {
        // Цвета серий идут строго по порядку палитры (view не отдаёт больше 6 серий),
        // смысловой цвет серии (dataset.color: positive / negative) — вместо очередного
        const color = dataset.color ? theme[dataset.color] : theme.series[index % theme.series.length];
        const result = {
            label: dataset.label,
            data: dataset.data.slice(),
            type: dataset.kind,
            // Меньший order рисуется выше: линии поверх столбцов
            order: dataset.kind === "line" ? 0 : 1,
        };
        if (dataset.axis === "y2" && !spec.horizontal) {
            result.yAxisID = "y2";
        }
        if (dataset.kind === "bar") {
            result.backgroundColor = dataset.sign_colors
                ? dataset.data.map((v) => (v < 0 ? theme.negative : theme.positive))
                : color;
            result.maxBarThickness = 24;
            if (spec.stacked) {
                // Зазор цвета фона между сегментами вместо рамки
                result.borderColor = theme.surface;
                result.borderWidth = 1;
                result.borderSkipped = false;
            } else {
                // Скругление только у конца столбца, у нуля — прямой угол
                result.borderRadius = 4;
                result.borderSkipped = "start";
            }
        } else if (dataset.kind === "line") {
            Object.assign(result, {
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBorderWidth: 2,
                pointBorderColor: theme.surface,
                fill: false,
            });
            if (spec.stacked) {
                // Линия не складывается со столбцами
                result.stack = "line-" + index;
            }
        } else {
            // Радиус пузырька задаёт сервер (point.r), без него — обычная точка
            const radii = dataset.data.map((point) => point.r || 5);
            Object.assign(result, {
                // Полупрозрачные пузырьки: наложения видны; по знаку — убыточные красные
                backgroundColor: dataset.sign_colors
                    ? dataset.data.map((point) =>
                          withAlpha(point.y < 0 ? theme.negative : theme.positive, 0.7)
                      )
                    : color,
                borderColor: theme.surface,
                borderWidth: 1,
                pointRadius: radii,
                pointHoverRadius: radii.map((radius) => radius + 2),
                // Попасть мышью проще, чем в саму точку
                pointHitRadius: 8,
            });
        }
        return result;
    }

    function buildScales(spec, theme) {
        const border = { color: theme.grid };
        const valueTicks = (fmt) => {
            const ticks = { color: theme.text, callback: (value) => formatTick(value, fmt) };
            if (fmt === "count") {
                ticks.precision = 0; // без делений 0,5 у количеств
            }
            return ticks;
        };
        if (spec.kind === "scatter") {
            // grace — запас по краям, чтобы крайние точки не обрезались рамкой
            return {
                x: {
                    type: "linear",
                    grace: "5%",
                    grid: { color: theme.grid },
                    border: border,
                    ticks: valueTicks(spec.x_format),
                },
                y: {
                    grace: "5%",
                    grid: { color: theme.grid },
                    border: border,
                    ticks: valueTicks(spec.format),
                },
            };
        }
        const valueAxis = spec.horizontal ? "x" : "y";
        const categoryAxis = spec.horizontal ? "y" : "x";
        const scales = {};
        scales[categoryAxis] = {
            stacked: spec.stacked,
            grid: { display: false },
            border: border,
            ticks: {
                color: theme.text,
                callback: function (value) {
                    return shortLabel(this.getLabelForValue(value), this.chart.width);
                },
            },
        };
        scales[valueAxis] = {
            stacked: spec.stacked,
            beginAtZero: true,
            grid: { color: theme.grid },
            border: border,
            ticks: valueTicks(spec.format),
        };
        const y2Series = spec.datasets.find((d) => d.axis === "y2");
        if (!spec.horizontal && y2Series) {
            // Правая шкала в формате своей серии, без своей сетки
            const y2Format = seriesFormat(spec, y2Series);
            scales.y2 = {
                position: "right",
                beginAtZero: true,
                grid: { drawOnChartArea: false },
                border: border,
                ticks: valueTicks(y2Format),
            };
            if (y2Format === "percent") {
                // Накопленная доля (Парето): шкала 0–100 %
                scales.y2.suggestedMax = 100;
            }
        }
        return scales;
    }

    // Цвет с прозрачностью: #rrggbb -> rgba(); другие записи цвета — как есть
    function withAlpha(color, alpha) {
        const match = /^#([0-9a-f]{6})$/i.exec(color);
        if (!match) {
            return color;
        }
        const n = parseInt(match[1], 16);
        return "rgba(" + (n >> 16) + ", " + ((n >> 8) & 255) + ", " + (n & 255) + ", " + alpha + ")";
    }

    // Цвет текста поверх заливки: тёмный или белый — какой контрастнее (WCAG)
    function textOn(color) {
        const match = /^#([0-9a-f]{6})$/i.exec(color);
        if (!match) {
            return "#ffffff";
        }
        const n = parseInt(match[1], 16);
        const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((channel) => {
            const c = channel / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        return (luminance + 0.05) / 0.05 > 1.05 / (luminance + 0.05) ? "#0b0b0b" : "#ffffff";
    }

    // Подписи значений столбцов (spec.value_labels): в формате оси, сокращённо.
    // Помещается в столбец — внутри, контрастным цветом. У горизонтальных графиков
    // не поместившиеся подписи идут справа от конца полосы цветом своей серии;
    // у вертикальных не пишутся — значение остаётся в подсказке.
    const valueLabels = {
        id: "anValueLabels",
        afterDatasetsDraw(chart, args, options) {
            if (!options.enabled) {
                return;
            }
            const ctx = chart.ctx;
            const horizontal = chart.options.indexAxis === "y";
            const ends = new Map(); // индекс полосы -> {end, y}: правый край всей полосы
            const outside = new Map(); // индекс полосы -> [{text, color}] — не поместились
            ctx.save();
            ctx.font = "600 12px " + Chart.defaults.font.family;
            ctx.textBaseline = "middle";
            ctx.textAlign = "center";
            chart.data.datasets.forEach((dataset, datasetIndex) => {
                const meta = chart.getDatasetMeta(datasetIndex);
                if (meta.hidden || meta.type !== "bar") {
                    return;
                }
                meta.data.forEach((bar, index) => {
                    const value = dataset.data[index];
                    if (!value) {
                        return;
                    }
                    const { x, y, base } = bar.getProps(["x", "y", "base"], true);
                    if (horizontal) {
                        const row = ends.get(index) || { end: -Infinity, y: y };
                        row.end = Math.max(row.end, x, base);
                        ends.set(index, row);
                    }
                    const text = options.format(value);
                    const color = keyColor(dataset, index);
                    const room = horizontal ? Math.abs(x - base) : Math.abs(y - base);
                    if (ctx.measureText(text).width + 8 <= room) {
                        ctx.fillStyle = options.whiteOn.includes(color) ? "#ffffff" : textOn(color);
                        ctx.fillText(text, horizontal ? (x + base) / 2 : x, horizontal ? y : (y + base) / 2);
                    } else if (horizontal) {
                        outside.set(index, (outside.get(index) || []).concat({ text: text, color: color }));
                    }
                });
            });
            ctx.textAlign = "left";
            outside.forEach((labels, index) => {
                const row = ends.get(index);
                let left = row.end + 6;
                labels.forEach((label) => {
                    const width = ctx.measureText(label.text).width;
                    if (left + width > chart.chartArea.right) {
                        return;
                    }
                    ctx.fillStyle = label.color;
                    ctx.fillText(label.text, left, row.y);
                    left += width + 10;
                });
            });
            ctx.restore();
        },
    };

    // Цвет ключа серии в подсказке (у столбцов «по знаку» — свой у каждого столбца)
    function keyColor(dataset, index) {
        const color = dataset.backgroundColor;
        return Array.isArray(color) ? color[index] : color;
    }

    function buildTooltip(spec, theme) {
        const callbacks = {
            label: (ctx) => {
                const dataset = spec.datasets[ctx.datasetIndex];
                const value = spec.horizontal ? ctx.parsed.x : ctx.parsed.y;
                return dataset.label + ": " + formatValue(value, seriesFormat(spec, dataset));
            },
            labelColor: (ctx) => {
                const color = keyColor(ctx.dataset, ctx.dataIndex);
                return { borderColor: color, backgroundColor: color, borderWidth: 2 };
            },
            labelPointStyle: () => ({ pointStyle: "line", rotation: 0 }),
        };
        if (spec.kind === "scatter") {
            callbacks.title = (items) => (items.length ? items[0].raw.label : "");
            callbacks.label = (ctx) =>
                formatValue(ctx.raw.x, spec.x_format) + " · " + formatValue(ctx.raw.y, spec.format);
        }
        return {
            backgroundColor: theme.surface,
            borderColor: theme.grid,
            borderWidth: 1,
            titleColor: theme.text,
            bodyColor: theme.ink,
            padding: 10,
            usePointStyle: true,
            // Порядок строк — как у серий, а не как у order
            itemSort: (a, b) => a.datasetIndex - b.datasetIndex,
            callbacks: callbacks,
        };
    }

    function buildLegend(spec, theme) {
        return {
            // Одна серия — легенда не нужна, её называет заголовок карточки
            display: spec.datasets.length > 1,
            position: "top",
            align: "start",
            labels: {
                color: theme.text,
                usePointStyle: true,
                sort: (a, b) => a.datasetIndex - b.datasetIndex,
                // Ключ повторяет форму метки: прямоугольник у столбцов, линия у линий
                generateLabels: (chart) =>
                    Chart.defaults.plugins.legend.labels.generateLabels(chart).map((item) => {
                        const isLine = spec.datasets[item.datasetIndex].kind === "line";
                        item.pointStyle = isLine ? "line" : "rect";
                        item.lineWidth = isLine ? 2 : 0;
                        if (isLine) {
                            // по умолчанию берётся обводка точки (цвет фона) — ключ был бы невидим
                            item.strokeStyle = chart.data.datasets[item.datasetIndex].borderColor;
                        }
                        return item;
                    }),
            },
        };
    }

    function buildConfig(spec, theme, animate) {
        const config = {
            type: spec.kind,
            data: {
                labels: spec.labels.slice(),
                datasets: spec.datasets.map((d, i) => buildDataset(spec, d, i, theme)),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: spec.horizontal ? "y" : "x",
                interaction:
                    spec.kind === "scatter"
                        ? { mode: "nearest", intersect: true }
                        : { mode: "index", intersect: false, axis: spec.horizontal ? "y" : "x" },
                scales: buildScales(spec, theme),
                plugins: {
                    legend: buildLegend(spec, theme),
                    tooltip: buildTooltip(spec, theme),
                    anValueLabels: {
                        enabled: Boolean(spec.value_labels),
                        format: (value) => formatTick(value, spec.format),
                        // на синих полосах — всегда белый текст: тёмный сливается с синим
                        whiteOn: [theme.positive, theme.series[0]],
                    },
                },
                onClick: (event, elements) => {
                    const url = firstLink(spec, elements);
                    if (url) {
                        window.location.href = url;
                    }
                },
                onHover: (event, elements, chart) => {
                    chart.canvas.style.cursor = firstLink(spec, elements) ? "pointer" : "default";
                },
            },
        };
        if (!animate) {
            config.options.animation = false;
        }
        config.plugins = [valueLabels];
        return config;
    }

    // --- Построение и перестроение ----------------------------------------------

    let charts = [];
    let themeKey = "";

    function readSpec(canvas) {
        const script = document.getElementById(canvas.getAttribute("data-chart"));
        if (!script) {
            return null;
        }
        try {
            return JSON.parse(script.textContent);
        } catch (error) {
            console.error("Аналитика: не удалось прочитать данные графика", error);
            return null;
        }
    }

    function buildAll(animate) {
        charts.forEach((chart) => chart.destroy());
        charts = [];
        if (typeof window.Chart === "undefined") {
            return;
        }
        const theme = readTheme();
        themeKey = JSON.stringify(theme);
        Chart.defaults.font.family = theme.font;
        Chart.defaults.color = theme.text;
        document.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
            const spec = readSpec(canvas);
            if (!spec || spec.empty) {
                return;
            }
            try {
                charts.push(new Chart(canvas, buildConfig(spec, theme, animate)));
            } catch (error) {
                // Ошибка одного графика не мешает остальным
                console.error("Аналитика: не удалось построить график", error);
            }
        });
    }

    // Тема админки меняется атрибутом data-theme на <html> (admin/js/theme.js),
    // в режиме «auto» — вслед за системой. Перестраиваем, только если цвета изменились:
    // theme.js при загрузке ставит тот же data-theme ещё раз.
    function watchTheme() {
        const rebuildIfChanged = () => {
            if (JSON.stringify(readTheme()) !== themeKey) {
                buildAll(false);
            }
        };
        new MutationObserver(rebuildIfChanged).observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["data-theme"],
        });
        const media = window.matchMedia("(prefers-color-scheme: dark)");
        if (media.addEventListener) {
            media.addEventListener("change", rebuildIfChanged);
        }
    }

    // --- Фильтр периода ---------------------------------------------------------

    // Поля «С/По» нужны только для «Свой период». Без JS они просто видны всегда.
    // Скрытые поля отключаются, чтобы не попадать в ссылку.
    function setupPeriodFields() {
        const preset = document.querySelector(".analytics-filters select[name='preset']");
        if (!preset) {
            return;
        }
        const fields = document.querySelectorAll(
            ".analytics-filter-date_from, .analytics-filter-date_to"
        );
        const update = () => {
            const custom = preset.value === "custom";
            fields.forEach((field) => {
                field.hidden = !custom;
                field.querySelectorAll("input").forEach((input) => {
                    input.disabled = !custom;
                });
            });
        };
        preset.addEventListener("change", update);
        update();
    }

    function init() {
        setupPeriodFields();
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        buildAll(!reduceMotion);
        watchTheme();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
