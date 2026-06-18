django.jQuery(function($) {
    const $replacementSelect = $('#id_replacement_equipment');
    const $returnedCheckbox = $('#id_returned_to_office');

    // Если элементов нет на странице — ничего не делаем
    if (!$replacementSelect.length || !$returnedCheckbox.length) {
        return;
    }

    function updateCheckboxState() {
        var hasValue = $replacementSelect.val() && $replacementSelect.val() !== '';
        $returnedCheckbox.prop('disabled', !hasValue);
        if (!hasValue) {
            $returnedCheckbox.prop('checked', false);
        }
    }

    // При загрузке страницы
    updateCheckboxState();

    // При изменении выпадающего списка подменного оборудования
    $replacementSelect.on('change', updateCheckboxState);
});
