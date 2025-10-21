(function($) {
    $(document).ready(function() {
        // Находим кнопку с классом toggle-filter и id hidden-filter-button
        var $toggleButton = $('button.toggle-filter#hidden-filter-button');
        
        // Находим контейнер фильтра
        var $filterContainer = $('#changelist-filter');
        
        // Добавляем обработчик события click
        $toggleButton.on('click', function() {
            // Переключаем видимость контейнера фильтра
            if ($filterContainer.is(':visible')) {
                $filterContainer.hide();
            } else {
                $filterContainer.show();
            }
        });
    });
})(django.jQuery);
