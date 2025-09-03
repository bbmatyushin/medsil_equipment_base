function removeQueryParam(paramName) {
    // Получаем текущий URL
    const url = new URL(window.location.href);

    // Удаляем указанный параметр из строки запроса
    url.searchParams.delete(paramName);

    // Обновляем URL без перезагрузки страницы
    history.replaceState({}, '', url);
}


document.addEventListener("DOMContentLoaded", function () {
    // Вызов функции для удаления параметра 'eq_acc'
//    removeQueryParam('eq_select');
    let currentEqSelectValue = null;

    // Сначала ждём появления самого span
    const observerForSpan = new MutationObserver(() => {
        const spanEl = document.getElementById("select2-id_equipment_accounting-container");
        if (spanEl) {
            console.log("Нашли span:", spanEl);

            // Создаём постоянный наблюдатель для текста
            const observerForText = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    if (mutation.type === "childList" || mutation.type === "characterData") {
                        const newText = spanEl.textContent.trim();
                        console.log("Изменение текста:", newText);

                        // 👉 здесь можно делать fetch к Django и менять URL
                        if (newText && newText !== currentEqSelectValue) {
                        currentEqSelectValue = newText;
                        fetch(`/get_equipment_id_by_name/${encodeURIComponent(newText)}`)
                           .then(r => r.json())
                           .then(data => {
                                if (data.id) {

                                    const url = new URL(window.location.href);
                                    url.searchParams.set("eq_select", data.id);
                                    window.location.href = url.toString();
                                } else {
                                    console.log("ID для оборудования не найдено");
                                }
                           })
                        }
                    }
                });
            });

            observerForText.observe(spanEl, {
                childList: true,
                characterData: true,
                subtree: true
            });

            // Этот отключаем, чтобы не искал span повторно
            observerForSpan.disconnect();
        }
    });

    observerForSpan.observe(document.body, { childList: true, subtree: true });
});




            // Отправляем fetch-запрос к Django
//            fetch(`/get_equipment_id/?name=${encodeURIComponent(selectedText)}`)
//                .then(response => response.json())
//                .then(data => {
//                    if (data.id) {
//                        // Обновляем URL с новым GET параметром
//                        const url = new URL(window.location.href);
//                        url.searchParams.set("equipment_id", data.id);
//                        window.location.href = url.toString();
//                    }
//                })
//                .catch(error => {
//                    console.error("Ошибка при запросе:", error);
//                });
//        });
//    }
//});



// Возвращает Get-запрос с id оборудования
//document.addEventListener('DOMContentLoaded', () => {
//    const eqSelectList = document.getElementById('eqSelectList');
//
//    if (eqSelectList) {
//        eqSelectList.addEventListener('change', function() {
//            const selectedValue = this.value;
//            const selectedTitle = this.options[this.selectedIndex].text;
//            if (selectedValue !== "") {
//                // Отправка GET-запроса
//        //        fetch('?eq_select=' + encodeURIComponent(selectedValue))
//        //            ;
//                // Создаем новый URL с параметром
//                const newUrl = `${window.location.pathname}?eq_select=${encodeURIComponent(selectedValue)}&eq_title=${encodeURIComponent(selectedTitle)}`;
//                // Перенаправляем на новый URL
//                window.location.href = newUrl;
//            } else {
//                // Если выбранное значение пустое, то сбрасываем фильтр
//                const newUrl = `${window.location.pathname}`;
//                // Перенаправляем на новый URL
//                window.location.href = newUrl;
//            }
//        });
//    }
//});

// Функция для фильтрации select-списка с оборудованием на странице с добавлением ремонта
//document.addEventListener('DOMContentLoaded', () => {
//    const searchInput = document.getElementById('searchInput');
//    if (searchInput) {
//        searchInput.addEventListener('input', function() {
//            var filterValue = this.value.toLowerCase();
//            var selectOptions = document.querySelectorAll('#eqSelectList option');
//
//            selectOptions.forEach(function(option) {
//                var text = option.textContent.toLowerCase();
//                if (text.includes(filterValue)) {
//                    option.style.display = '';
//                } else {
//                    option.style.display = 'none';
//                }
//            });
//        });
//    }
//});

// Скрываем блок с фильтрами
//document.addEventListener('DOMContentLoaded', () => {
//    const btnToggle = document.getElementById('hidden-filter-button');
//    const hiddenDiv = document.getElementById('changelist-filter');
//
//    btnToggle.addEventListener('click', () => {
//        if (hiddenDiv.style.display === 'none') {
//            hiddenDiv.style.display = 'block';
//        } else {
//            hiddenDiv.style.display = 'none';
//        }
//    });
//});
