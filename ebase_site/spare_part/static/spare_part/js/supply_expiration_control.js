/**
 * Управление полем "Срок годности" (expiration_dt) в инлайн-форме поставки запчастей v2.
 *
 * При выборе запчасти (spare_part) в строке инлайн-формы SparePartSupplyItem:
 *   - Обновляется ячейка «Ед. изм.».
 *   - Если у запчасти есть срок годности (is_expiration=True) — поле "Годен до"
 *     становится видимым и доступным для ввода.
 *   - Если срока годности нет — поле "Годен до" скрывается (сохраняя фон строки),
 *     значение очищается.
 *
 * Использует API: /admin/spare_part/sparepart/<id>/get_expiration_dates/
 */
(function($) {
    $(document).ready(function() {

        var INLINE_PREFIX = 'items';

        /**
         * Обновляет ячейку «Ед. изм.» в строке инлайна.
         */
        function updateUnitCell($row, unitText) {
            var $unitCell = $row.find('td.field-unit_display');
            if ($unitCell.length) {
                $unitCell.text(unitText || '-');
            }
        }

        /**
         * Управляет видимостью DateTimeShortcuts ("Сегодня|" и календарь).
         */
        function setExpirationShortcutsVisible($row, visible) {
            var $cell = $row.find('td.field-expiration_dt');
            if (!$cell.length) return;

            // Django DateTimeShortcuts создаёт <span class="datetimeshortcuts">
            var $shortcuts = $cell.find('.datetimeshortcuts');
            if ($shortcuts.length) {
                $shortcuts.css('visibility', visible ? 'visible' : 'hidden');
            }
        }

        /**
         * Загружает информацию о запчасти и управляет видимостью срока годности.
         * $row — jQuery-объект строки <tr> табулярного инлайна.
         */
        function loadSparePartInfo(sparePartId, $row) {
            var $expSelect = $row.find('[name$="-expiration_dt"]');
            if (!$expSelect.length) return;

            $expSelect.prop('disabled', true);

            $.ajax({
                url: '/admin/spare_part/sparepart/' + sparePartId + '/get_expiration_dates/',
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    // Обновляем единицу измерения
                    updateUnitCell($row, data.unit);

                    if (data.is_expiration) {
                        // Показываем поле срока годности
                        $expSelect.css('visibility', 'visible');
                        $expSelect.prop('disabled', false);
                        $expSelect.prop('required', false);
                        setExpirationShortcutsVisible($row, true);
                    } else {
                        // Скрываем поле срока годности, очищаем значение
                        $expSelect.val('');
                        $expSelect.css('visibility', 'hidden');
                        $expSelect.prop('required', false);
                        $expSelect.prop('disabled', false);
                        setExpirationShortcutsVisible($row, false);
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Ошибка загрузки данных запчасти:', error);
                    $expSelect.prop('disabled', false);
                }
            });
        }

        /**
         * Обработчик изменения выбора запчасти.
         */
        function onSparePartChange() {
            var $select = $(this);

            if ($select.prop('disabled') || $select.prop('readonly')) {
                return;
            }

            var $row = $select.closest('.dynamic-' + INLINE_PREFIX);
            var sparePartId = $select.val();

            setTimeout(function() {
                if (sparePartId) {
                    loadSparePartInfo(sparePartId, $row);
                } else {
                    var $expSelect = $row.find('[name$="-expiration_dt"]');
                    $expSelect.val('');
                    $expSelect.css('visibility', 'hidden');
                    setExpirationShortcutsVisible($row, false);
                    updateUnitCell($row, null);
                }
            }, 0);
        }

        // Привязываем обработчик к существующим и будущим полям spare_part
        $(document).on(
            'change',
            '[name^="' + INLINE_PREFIX + '-"][name$="-spare_part"]',
            onSparePartChange
        );

        // Обрабатываем динамически добавленные строки (кнопка "Добавить ещё")
        $(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName && formsetName.indexOf(INLINE_PREFIX) === 0) {
                var $sparePartSelect = $row.find('[name$="-spare_part"]');
                var sparePartId = $sparePartSelect.val();
                var $expSelect = $row.find('[name$="-expiration_dt"]');

                // Для новой строки скрываем срок годности по умолчанию
                $expSelect.css('visibility', 'hidden');
                setExpirationShortcutsVisible($row, false);

                if (sparePartId) {
                    setTimeout(function() {
                        loadSparePartInfo(sparePartId, $row);
                    }, 0);
                }
            }
        });

        // Инициализация существующих строк при загрузке страницы
        $('.dynamic-' + INLINE_PREFIX).each(function() {
            var $row = $(this);
            var $sparePartSelect = $row.find('[name$="-spare_part"]');
            var sparePartId = $sparePartSelect.val();
            var $expSelect = $row.find('[name$="-expiration_dt"]');

            if ($sparePartSelect.prop('disabled') || $sparePartSelect.prop('readonly')) {
                return;
            }

            if (sparePartId) {
                loadSparePartInfo(sparePartId, $row);
            } else {
                $expSelect.css('visibility', 'hidden');
                setExpirationShortcutsVisible($row, false);
            }
        });

        // Установка значения по умолчанию для поля "Номер документа" на странице добавления
        if (window.location.pathname.indexOf('/admin/spare_part/sparepartsupplyv2/add/') !== -1) {
            var $docNumInput = $('input[name="doc_num"]');
            if ($docNumInput.length && !$docNumInput.val()) {
                $docNumInput.val('б/н');
            }
        }

    });
})(django.jQuery);
