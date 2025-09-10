django.jQuery(document).ready(function($) {
    let isInitialized = false; // Флаг: true после первой загрузки

    // Функция для получения GET-параметра из URL
    function getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    // При загрузке страницы — восстанавливаем значение из URL
    const savedSearchTerm = getUrlParameter('search_equipment_form');
    if (savedSearchTerm) {
        $('#id_search_equipment').val(decodeURIComponent(savedSearchTerm));
    }

    // Обработчик нажатия на кнопку "Поиск"
    $('#id_search_button').on('click', function(e) {
        e.preventDefault();

        // Получаем значение из поля ввода
        const searchTerm = $('#id_search_equipment').val().trim();

        // Получаем текущий URL
        const url = new URL(window.location.href);

        // Удаляем старый параметр (если есть)
        url.searchParams.delete('search_equipment_form');
        url.searchParams.delete('choice_eq_acc');

        // Добавляем новый, только если значение не пустое
        if (searchTerm) {
            url.searchParams.set('search_equipment_form', searchTerm);
        }

        // Перезагружаем страницу с обновлённым URL
        window.location.href = url.toString();
    });

    // ДОБАВЛЕНО: Обработчик изменения выбора оборудования
    $('#id_equipment_accounting').on('change', function(e) {
        e.preventDefault();

        // Игнорируем событие при инициализации страницы
        if (!isInitialized) {
            isInitialized = true; // Теперь разрешаем обработку
            return;
        }

        // Получаем выбранное значение (ID оборудования)
        const selectedEquipmentId = $(this).val();

        // Получаем текущий URL
        const url = new URL(window.location.href);

        // Удаляем старый параметр (если есть)
        url.searchParams.delete('choice_eq_acc');

        // Добавляем новый, только если значение выбрано (не пустое)
        if (selectedEquipmentId) {
            url.searchParams.set('choice_eq_acc', selectedEquipmentId);
        }

        // Перезагружаем страницу с обновлённым URL
        window.location.href = url.toString();
    });

    // Устанавливаем флаг после полной инициализации
    setTimeout(() => {
        isInitialized = true;
    }, 500); // Даём Django Admin время на восстановление формы

});