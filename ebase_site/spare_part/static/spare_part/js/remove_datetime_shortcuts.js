(function($) {
    $(document).ready(function() {
        function removeDateTimeShortcuts() {
            $('input[name^="shipment_m2m-"][name$="-expiration_dt"]').each(function() {
                if ($(this).is('[readonly], [disabled]')) {
                    var $shortcuts = $(this).next('.datetimeshortcuts');
                    if ($shortcuts.length) {
                        $shortcuts.remove();
                        console.log('Удален datetime shortcuts для поля:', this.name);
                    }
                }
            });
        }
        
        // Удаляем сразу после загрузки DOM
        removeDateTimeShortcuts();
        
        // Обрабатываем динамическое добавление форм (используем Django's formset events)
        $(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName.startsWith('shipment_m2m')) {
                setTimeout(removeDateTimeShortcuts, 100);
            }
        });
        
        // Также обрабатываем изменения в DOM через MutationObserver для дополнительной надежности
        var observer = new MutationObserver(function(mutations) {
            var shouldCheck = false;
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    $(mutation.addedNodes).each(function() {
                        if ($(this).is('input[name^="shipment_m2m-"][name$="-expiration_dt"]') || 
                            $(this).find('input[name^="shipment_m2m-"][name$="-expiration_dt"]').length) {
                            shouldCheck = true;
                        }
                    });
                }
            });
            if (shouldCheck) {
                setTimeout(removeDateTimeShortcuts, 100);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // Дополнительная проверка при изменении атрибутов readonly/disabled
        $(document).on('DOMAttrModified', 'input[name^="shipment_m2m-"][name$="-expiration_dt"]', function() {
            if ($(this).is('[readonly], [disabled]')) {
                var $shortcuts = $(this).next('.datetimeshortcuts');
                if ($shortcuts.length) {
                    $shortcuts.remove();
                }
            }
        });
    });
})(django.jQuery);
