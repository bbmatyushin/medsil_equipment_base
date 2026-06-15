/**
 * Управление полем "Срок годности" (expiration_dt) в инлайн-форме отгрузки запчастей.
 * 
 * При выборе запчасти (spare_part) в строке инлайн-формы SparePartShipmentM2M:
 *   - Если у запчасти есть срок годности (is_expiration=True) — загружаются доступные 
 *     даты из SparePartCount и populate-ятся в выпадающий список.
 *   - Если срока годности нет — поле скрывается, значение очищается.
 *
 * Использует API: /admin/spare_part/sparepart/<id>/get_expiration_dates/
 *
 * ВАЖНО: все манипуляции с DOM внутри обработчика change обёрнуты в setTimeout,
 * чтобы не сбивать состояние Select2-виджета (синхронные изменения DOM в соседнем <td>
 * заставляют Select2 сбрасывать выбранное значение).
 */
(function($) {
    $(document).ready(function() {

        var INLINE_PREFIX = 'shipment_m2m';

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
         * Загружает доступные сроки годности и заполняет <select>.
         * $row — jQuery-объект строки <tr> табулярного инлайна.
         */
        function loadExpirationDates(sparePartId, $row) {
            var $expSelect = $row.find('[name$="-expiration_dt"]');
            if (!$expSelect.length) return;

            // Сохраняем текущее значение, чтобы восстановить после загрузки (если оно есть в новых вариантах)
            var currentValue = $expSelect.val();

            $expSelect.prop('disabled', true);

            $.ajax({
                url: '/admin/spare_part/sparepart/' + sparePartId + '/get_expiration_dates/',
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    // Обновляем единицу измерения
                    updateUnitCell($row, data.unit);

                    $expSelect.empty();

                    if (data.is_expiration) {
                        $expSelect.append($('<option>', { value: '', text: '-- выберите срок --' }));
                        
                        if (data.available_dates && data.available_dates.length > 0) {
                            $.each(data.available_dates, function(i, dateInfo) {
                                $expSelect.append($('<option>', {
                                    value: dateInfo.date,
                                    text: dateInfo.display + ' (остаток: ' + dateInfo.amount + ')'
                                }));
                            });
                        } else {
                            $expSelect.append($('<option>', { value: '', text: 'Нет в наличии' }));
                        }

                        // Восстанавливаем ранее выбранное значение (если было отгружено)
                        if (currentValue) {
                            // Если отгруженный срок уже не числится на складе — добавляем его отдельной опцией
                            if (!$expSelect.find('option[value="' + currentValue + '"]').length) {
                                // Форматируем ISO-дату в ДД.ММ.ГГГГ для показа
                                var parts = currentValue.split('-');
                                var displayText = currentValue;
                                if (parts.length === 3) {
                                    displayText = parts[2] + '.' + parts[1] + '.' + parts[0];
                                }
                                $expSelect.append($('<option>', {
                                    value: currentValue,
                                    text: displayText + ' (отгружено)'
                                }));
                            }
                            $expSelect.val(currentValue);
                        }

                        // Показываем select (td остаётся видимой — наследует фон строки)
                        $expSelect.css('visibility', 'visible');
                        $expSelect.prop('disabled', false);
                        $expSelect.prop('required', true);
                    } else {
                        $expSelect.append($('<option>', { value: '', text: '--' }));
                        $expSelect.val('');
                        // Скрываем только select — td остаётся видимой и наследует цвет строки
                        $expSelect.css('visibility', 'hidden');
                        $expSelect.prop('required', false);
                        $expSelect.prop('disabled', false);
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Ошибка загрузки сроков годности:', error);
                    $expSelect.empty().append($('<option>', { value: '', text: 'Ошибка загрузки' }));
                    $expSelect.prop('disabled', false);
                }
            });
        }

        /**
         * Обработчик изменения выбора запчасти.
         * Вся работа с DOM отложена через setTimeout, чтобы не мешать Select2.
         */
        function onSparePartChange() {
            var $select = $(this);

            // Если поле заблокировано — не вмешиваемся
            if ($select.prop('disabled') || $select.prop('readonly')) {
                return;
            }

            var $row = $select.closest('.dynamic-' + INLINE_PREFIX);
            var sparePartId = $select.val();

            // Откладываем, чтобы Select2 завершил свою внутреннюю работу
            setTimeout(function() {
                if (sparePartId) {
                    loadExpirationDates(sparePartId, $row);
                } else {
                    var $expSelect = $row.find('[name$="-expiration_dt"]');
                    $expSelect.empty().append($('<option>', { value: '', text: '--' }));
                    // Скрываем только select — td наследует фон строки
                    $expSelect.css('visibility', 'hidden');
                    // Сбрасываем единицу измерения
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

                // Для новой строки: скрываем select, td наследует фон строки
                $expSelect.css('visibility', 'hidden');

                if (sparePartId) {
                    // Для новой строки тоже откладываем загрузку
                    setTimeout(function() {
                        loadExpirationDates(sparePartId, $row);
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

            // Если поля заблокированы — не вмешиваемся
            if ($sparePartSelect.prop('disabled') || $sparePartSelect.prop('readonly')) {
                return;
            }

            if (sparePartId) {
                loadExpirationDates(sparePartId, $row);
            } else {
                // Скрываем select — td видима и наследует фон строки
                $expSelect.css('visibility', 'hidden');
            }
        });

    });
})(django.jQuery);
