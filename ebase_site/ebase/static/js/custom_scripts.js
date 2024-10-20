
// Возвращает Get-запрос с id оборудования
document.getElementById('eqSelectList').addEventListener('change', function() {
    const selectedValue = this.value;
    const selectedTitle = this.options[this.selectedIndex].text;
    if (selectedValue !== "") {
        // Отправка GET-запроса
//        fetch('?eq_select=' + encodeURIComponent(selectedValue))
//            ;
        // Создаем новый URL с параметром
        const newUrl = `${window.location.pathname}?eq_select=${encodeURIComponent(selectedValue)}&eq_title=${encodeURIComponent(selectedTitle)}`;
        // Перенаправляем на новый URL
        window.location.href = newUrl;
    } else {
        // Если выбранное значение пустое, то сбрасываем фильтр
        const newUrl = `${window.location.pathname}`;
        // Перенаправляем на новый URL
        window.location.href = newUrl;
    }
});

// Функция для фильтрации select-списка с оборудованием на странице с добавлением ремонта
document.getElementById('searchInput').addEventListener('input', function() {
            var filterValue = this.value.toLowerCase();
            var selectOptions = document.querySelectorAll('#eqSelectList option');

            selectOptions.forEach(function(option) {
                var text = option.textContent.toLowerCase();
                if (text.includes(filterValue)) {
                    option.style.display = '';
                } else {
                    option.style.display = 'none';
                }
            });
        });


// Скрываем блок с фильтрами
document.getElementById('hide-filters').addEventListener('click', function() {
    document.getElementById('changelist-filter').style.display = 'none';
});

