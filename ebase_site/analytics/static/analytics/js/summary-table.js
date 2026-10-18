/* «Сводная по моделям»: колонка «Модель» уже на 30%, высота таблицы — не больше N строк.
   Ширину считаем от естественной (без переносов) ширины самого длинного названия. */
(function () {
    "use strict";

    var NARROW_RATIO = 0.7;

    function setup(wrap) {
        var table = wrap.querySelector("table");
        if (!table) {
            return;
        }
        var maxRows = parseInt(wrap.getAttribute("data-an-max-rows"), 10) || 15;
        var cells = table.querySelectorAll("td.an-model-cell");
        var rows = table.tBodies[0] ? table.tBodies[0].rows : [];

        function fitHeight() {
            wrap.style.maxHeight = "";
            if (rows.length <= maxRows) {
                return;
            }
            var height = table.tHead.offsetHeight;
            for (var i = 0; i < maxRows; i++) {
                height += rows[i].offsetHeight;
            }
            wrap.style.maxHeight = height + "px";
        }

        function narrow() {
            var natural = 0;
            cells.forEach(function (cell) {
                cell.classList.remove("is-narrowed");
                cell.style.width = "";
                cell.style.maxWidth = "";
            });
            cells.forEach(function (cell) {
                natural = Math.max(natural, cell.getBoundingClientRect().width);
            });
            if (natural > 0) {
                var width = Math.round(natural * NARROW_RATIO) + "px";
                cells.forEach(function (cell) {
                    cell.style.width = width;
                    cell.style.maxWidth = width;
                    cell.classList.add("is-narrowed");
                });
            }
            fitHeight();
        }

        narrow();
        // шрифты и ширина окна меняют высоту строк — пересчитываем высоту, ширину берём заново
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(narrow);
        }
        var timer = null;
        window.addEventListener("resize", function () {
            clearTimeout(timer);
            timer = setTimeout(narrow, 150);
        });
    }

    document.querySelectorAll("[data-an-max-rows]").forEach(setup);
})();
