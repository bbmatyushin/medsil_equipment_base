(function($) {
    $(document).ready(function() {
        function removeDateTimeShortcuts() {
            console.log('Запуск removeDateTimeShortcuts...');
            
            // Ищем все поля с именем shipment_m2m-*-expiration_dt
            $('input[name^="shipment_m2m-"][name$="-expiration_dt"]').each(function() {
                var $input = $(this);
                console.log('Найдено поле:', this.name, 'readonly:', this.readOnly, 'disabled:', this.disabled);
                
                // Проверяем атрибуты readonly и disabled
                if ($input.is('[readonly], [disabled]')) {
                    console.log('Поле заблокировано:', this.name);
                    
                    // Ищем следующий элемент span с классом datetimeshortcuts
                    var $shortcuts = $input.next('.datetimeshortcuts');
                    console.log('Найден shortcuts:', $shortcuts.length);
                    
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
            console.log('Добавлена форма:', formsetName);
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
        // Используем более надежный подход с setInterval для проверки изменений
        setInterval(function() {
            $('input[name^="shipment_m2m-"][name$="-expiration_dt"][readonly], input[name^="shipment_m2m-"][name$="-expiration_dt"][disabled]')
                .each(function() {
                    var $shortcuts = $(this).next('.datetimeshortcuts');
                    if ($shortcuts.length) {
                        $shortcuts.remove();
                        console.log('Удален datetime shortcuts (интервал):', this.name);
                    }
                });
        }, 500);
    });
})(django.jQuery);
