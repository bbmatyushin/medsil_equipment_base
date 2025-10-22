// Удаляем ссылку "Добавить Отгрузка запчастей" на странице списка отгрузок
(function($) {
    $(document).ready(function() {
        // Проверяем, что находимся на странице списка отгрузок запчастей
        if (window.location.pathname.indexOf('/admin/spare_part/sparepartshipment/') !== -1) {
            // Находим ссылку с текстом "Добавить Отгрузка запчастей"
            $('a.addlink').each(function() {
                if ($(this).text().includes('Добавить Отгрузка запчастей')) {
                    $(this).remove();
                }
            });
        }
    });
})(django.jQuery);
