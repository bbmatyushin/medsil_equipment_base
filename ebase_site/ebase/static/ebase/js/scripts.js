document.addEventListener('DOMContentLoaded', () => {
    const $ = django.jQuery;
    const $accountingField = $('#id_equipment_accounting');

    $accountingField.on('select2:select', function (e) {
                const selectedId = e.params.data.id;  // UUID выбранного EquipmentAccounting

                console.log(selectedId);

                // AJAX-запрос к кастомному эндпоинту
                $.getJSON(
                    '{% url "admin:get_equipment_id_by_accounting" pk="PLACEHOLDER" %}'.replace('PLACEHOLDER', selectedId),
                    function (data) {
                        if (data.equipment_id) {
                            // Формируем новый URL с get-параметром
                            const url = new URL(window.location.href);
                            url.searchParams.set('equipment_id', data.equipment_id);

                            // Обновляем URL без перезагрузки
                            window.history.pushState({}, '', url);

                            console.log('URL обновлён:', url.toString());
                        }
                    }
                ).fail(function () {
                    console.error('Ошибка при получении equipment_id');
                });
            });

});


// Возвращает Get-запрос с id оборудования
//document.addEventListener('DOMContentLoaded', () => {
//    const eqSelectList = document.getElementById('id_search_equipment');
//
//    if (eqSelectList) {
//        eqSelectList.addEventListener('change', function() {
//            const selectedValue = this.value;
//            const selectedTitle = this.options[this.selectedIndex].text;
//            if (selectedValue !== "") {
//                // Отправка GET-запроса
//        //        fetch('?eq_select=' + encodeURIComponent(selectedValue))
//        //            ;
//                // Создаем новый URL с параметром
//                const newUrl = `${window.location.pathname}?eq_select=${encodeURIComponent(selectedValue)}&eq_title=${encodeURIComponent(selectedTitle)}`;
//                // Перенаправляем на новый URL
//                window.location.href = newUrl;
//            } else {
//                // Если выбранное значение пустое, то сбрасываем фильтр
//                const newUrl = `${window.location.pathname}`;
//                // Перенаправляем на новый URL
//                window.location.href = newUrl;
//            }
//        });
//    }
//});

// Функция для фильтрации select-списка с оборудованием на странице с добавлением ремонта
//document.addEventListener('DOMContentLoaded', () => {
//    const searchInput = document.getElementById('searchInput');
//    if (searchInput) {
//        searchInput.addEventListener('input', function() {
//            var filterValue = this.value.toLowerCase();
//            var selectOptions = document.querySelectorAll('#eqSelectList option');
//
//            selectOptions.forEach(function(option) {
//                var text = option.textContent.toLowerCase();
//                if (text.includes(filterValue)) {
//                    option.style.display = '';
//                } else {
//                    option.style.display = 'none';
//                }
//            });
//        });
//    }
//});

// Скрываем блок с фильтрами
//document.addEventListener('DOMContentLoaded', () => {
//    const btnToggle = document.getElementById('hidden-filter-button');
//    const hiddenDiv = document.getElementById('changelist-filter');
//
//    btnToggle.addEventListener('click', () => {
//        if (hiddenDiv.style.display === 'none') {
//            hiddenDiv.style.display = 'block';
//        } else {
//            hiddenDiv.style.display = 'none';
//        }
//    });
//});
