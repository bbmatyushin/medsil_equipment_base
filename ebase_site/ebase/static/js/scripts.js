
// Возвращает Get-запрос с id оборудования
document.getElementById('eqList').addEventListener('change', function() {
    const selectedValue = this.value;
    if (selectedValue !== "") {
        // Отправка GET-запроса
        fetch('?eq_select=' + encodeURIComponent(selectedValue))
            ;
    }
});
