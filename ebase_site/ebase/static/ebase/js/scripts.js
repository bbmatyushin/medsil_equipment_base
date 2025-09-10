django.jQuery(document).ready(function($) {
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

        // Добавляем новый, только если значение не пустое
        if (searchTerm) {
            url.searchParams.set('search_equipment_form', searchTerm);
        }

        // Перезагружаем страницу с обновлённым URL
        window.location.href = url.toString();
    });
});