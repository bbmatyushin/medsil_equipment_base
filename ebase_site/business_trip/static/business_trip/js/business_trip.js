/**
 * Скрипт для страницы командировки (admin/business_trip/businesstrip/).
 *
 * Делает две вещи:
 *  1. В инлайне «Подразделения» после выбора подразделения подгружает город
 *     через API /admin/clients/department/<id>/get_city/ и показывает его в
 *     колонке «Город». По аналогии с единицей измерения в поставке запчастей.
 *  2. Считает и показывает «Командировочные» (дни × 700 руб.) сразу при
 *     вводе дат «Дата выезда» и «Дата возвращения», до сохранения записи.
 */
(function ($) {
    "use strict";

    var INLINE_PREFIX = "destinations";
    var DAILY_RATE = 700;

    // ---------- Город в инлайне подразделений ----------

    /**
     * Обновляет ячейку «Город» в строке инлайна.
     */
    function updateCityCell($row, cityText) {
        var $cell = $row.find("td.field-city_display");
        if ($cell.length) {
            $cell.text(cityText || "—");
        }
    }

    /**
     * Подгружает название города для выбранного подразделения.
     */
    function loadDepartmentCity(departmentId, $row) {
        if (!departmentId) {
            updateCityCell($row, null);
            return;
        }
        $.ajax({
            url:
                "/admin/clients/department/" +
                departmentId +
                "/get_city/",
            type: "GET",
            dataType: "json",
            success: function (data) {
                updateCityCell($row, data.city);
            },
            error: function (xhr, status, error) {
                console.error("Ошибка загрузки города подразделения:", error);
                updateCityCell($row, null);
            },
        });
    }

    function onDepartmentChange() {
        var $select = $(this);
        if ($select.prop("disabled") || $select.prop("readonly")) {
            return;
        }
        var $row = $select.closest(".dynamic-" + INLINE_PREFIX);
        var departmentId = $select.val();
        setTimeout(function () {
            loadDepartmentCity(departmentId, $row);
        }, 0);
    }

    // ---------- Сумма командировочных ----------

    function parseDate(value) {
        if (!value) {
            return null;
        }
        // Django admin (ru-ru) хранит дату в поле в формате дд.мм.гггг.
        // Дополнительно поддерживаем ISO-формат YYYY-MM-DD на случай смены локали.
        var parts = value.split(".");
        if (parts.length === 3) {
            var d = new Date(+parts[2], +parts[1] - 1, +parts[0]);
            return isNaN(d.getTime()) ? null : d;
        }
        parts = value.split("-");
        if (parts.length === 3) {
            var d = new Date(+parts[0], +parts[1] - 1, +parts[2]);
            return isNaN(d.getTime()) ? null : d;
        }
        return null;
    }

    function updateAllowance() {
        var $beg = $('input[name="beg_dt"]');
        var $end = $('input[name="end_dt"]');
        var $allowance = $("#id_allowance_amount");

        if (!$allowance.length) {
            return;
        }
        var beg = parseDate($beg.val());
        var end = parseDate($end.val());
        var amount = "0";
        if (beg && end) {
            if (end >= beg) {
                var days = Math.round(
                    (end - beg) / (1000 * 60 * 60 * 24)
                ) + 1;
                if (days >= 1) {
                    amount = (days * DAILY_RATE).toLocaleString("ru-RU");
                }
            }
        }
        $allowance.val(amount);
    }

    // ---------- Инициализация ----------

    $(document).ready(function () {
        // Город: привязываем обработчик к существующим и будущим полям department
        $(document).on(
            "change",
            '[name^="' + INLINE_PREFIX + '-"][name$="-department"]',
            onDepartmentChange
        );

        // Город: обработка динамически добавленных строк
        $(document).on("formset:added", function (event, $row, formsetName) {
            if (formsetName && formsetName.indexOf(INLINE_PREFIX) === 0) {
                var $departmentSelect = $row.find(
                    '[name$="-department"]'
                );
                var departmentId = $departmentSelect.val();
                if (departmentId) {
                    setTimeout(function () {
                        loadDepartmentCity(departmentId, $row);
                    }, 0);
                } else {
                    updateCityCell($row, null);
                }
            }
        });

        // Город: инициализация существующих строк
        $(".dynamic-" + INLINE_PREFIX).each(function () {
            var $row = $(this);
            var $departmentSelect = $row.find('[name$="-department"]');
            var departmentId = $departmentSelect.val();
            if (
                $departmentSelect.prop("disabled") ||
                $departmentSelect.prop("readonly")
            ) {
                return;
            }
            if (departmentId) {
                loadDepartmentCity(departmentId, $row);
            }
        });

        // Командировочные: пересчёт.
        // Админский календарь (DateTimeShortcuts.js) записывает выбранную дату
        // напрямую в input.value БЕЗ генерации события change/input, поэтому
        // обычный обработчик не срабатывает. Используем несколько механизмов:
        //  - события change/keyup/blur для ручного ввода;
        //  - делегированный клик на документ — если кликнули внутри календаря
        //    (#calendarbox*) или по ссылке календаря, запускаем отсроченный
        //    пересчёт (после того, как DateTimeShortcuts запишет значение).
        $(document).on(
            "change keyup blur",
            'input[name="beg_dt"], input[name="end_dt"]',
            updateAllowance
        );
        $(document).on("click", function (event) {
            var $target = $(event.target);
            if (
                $target.closest("#calendarbox0, #calendarbox1").length ||
                $target.closest("a[id^='calendarlink']").length
            ) {
                setTimeout(updateAllowance, 50);
                setTimeout(updateAllowance, 200);
            }
        });
        updateAllowance();
    });
})(django.jQuery);
