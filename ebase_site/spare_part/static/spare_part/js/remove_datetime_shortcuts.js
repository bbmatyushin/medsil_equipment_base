(function($) {
    // Удаляем datetime shortcuts сразу, не дожидаясь полной загрузки DOM
    function removeDateTimeShortcutsImmediately() {
        var inputs = document.querySelectorAll('input[name^="shipment_m2m-"][name$="-expiration_dt"][readonly], input[name^="shipment_m2m-"][name$="-expiration_dt"][disabled]');
        for (var i = 0; i < inputs.length; i++) {
            var input = inputs[i];
            var shortcuts = input.nextElementSibling;
            if (shortcuts && shortcuts.classList.contains('datetimeshortcuts')) {
                shortcuts.remove();
            }
        }
    }
    
    // Вызываем сразу
    removeDateTimeShortcutsImmediately();
    
    $(document).ready(function() {
        // Удаляем еще раз на случай, если какие-то элементы появились позже
        removeDateTimeShortcutsImmediately();
        
        function removeDateTimeShortcuts() {
            $('input[name^="shipment_m2m-"][name$="-expiration_dt"][readonly], input[name^="shipment_m2m-"][name$="-expiration_dt"][disabled]')
                .each(function() {
                    var $shortcuts = $(this).next('.datetimeshortcuts');
                    if ($shortcuts.length) {
                        $shortcuts.remove();
                    }
                });
        }
        
        // Обрабатываем динамическое добавление форм
        $(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName.startsWith('shipment_m2m')) {
                // Удаляем shortcuts сразу для новой формы
                $row.find('input[name$="-expiration_dt"][readonly], input[name$="-expiration_dt"][disabled]')
                    .each(function() {
                        var $shortcuts = $(this).next('.datetimeshortcuts');
                        if ($shortcuts.length) {
                            $shortcuts.remove();
                        }
                    });
            }
        });
        
        // MutationObserver для отслеживания изменений атрибутов
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && 
                    (mutation.attributeName === 'readonly' || mutation.attributeName === 'disabled')) {
                    var target = mutation.target;
                    if (target.matches('input[name^="shipment_m2m-"][name$="-expiration_dt"]') && 
                        (target.readOnly || target.disabled)) {
                        var shortcuts = target.nextElementSibling;
                        if (shortcuts && shortcuts.classList.contains('datetimeshortcuts')) {
                            shortcuts.remove();
                        }
                    }
                }
            });
        });
        
        // Наблюдаем за изменениями атрибутов у всех соответствующих input элементов
        $('input[name^="shipment_m2m-"][name$="-expiration_dt"]').each(function() {
            observer.observe(this, { attributes: true });
        });
    });
})(django.jQuery);
