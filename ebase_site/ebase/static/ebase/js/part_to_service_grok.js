class SparePartsManager {
    constructor() {
        this.sparePartSelect = null;
        this.customBlock = null;
        this.originalQuantities = new Map(); // Хранит оригинальные количества при загрузке
        this.currentQuantities = new Map(); // Текущие введенные количества
        this.sparePartsData = new Map(); // Данные о запчастях (название, количество), ключ - uniqueKey
        this.sparePartGroups = new Map(); // sparePartId -> Set of uniqueKeys
        this.isUpdating = false; // Флаг для предотвращения множественных обновлений

        this.init();
    }

    init() {
        // Ждем загрузки DOM
        if (document.readyState === 'loading') {
            window.addEventListener('load', () => this.setup());
        } else {
            this.setup();
        }
    }

    async setup() {
        await this.waitForElement('#id_spare_part_to');
        this.sparePartSelect = document.getElementById('id_spare_part_to');

        if (!this.sparePartSelect) {
            console.warn('Spare part select element not found');
            return;
        }

        this.createCustomBlock();
        await this.loadInitialData();
        this.setupEventListeners();
        await this.updateCustomBlock();
    }

    waitForElement(selector, timeout = 5000) {
    // Чтобы дождаться полной инициализации filter_horizontal
        return new Promise((resolve, reject) => {
            const startTime = Date.now();

            const checkElement = () => {
                const element = document.querySelector(selector);
                if (element) {
                    console.log(`✅ Element ${selector} found after ${Date.now() - startTime}ms`);
                    resolve(element);
                } else if (Date.now() - startTime > timeout) {
                    console.error(`❌ Timeout: Element ${selector} not found after ${timeout}ms`);
                    reject(new Error(`Element ${selector} not found`));
                } else {
                    // Проверяем снова через 100ms
                    setTimeout(checkElement, 100);
                }
            };

            checkElement();
        });
    }

    createCustomBlock() {
        const sparePartRow = document.querySelector('.form-row.field-spare_part');
        if (!sparePartRow) {
            console.error('Spare part form row not found');
            return;
        }

        // Создаем контейнер для кастомного блока в виде таблицы Django admin
        this.customBlock = document.createElement('div');
        this.customBlock.className = 'form-row custom-choice-spare_part';
        this.customBlock.innerHTML = `
            <div class="selected-spare-parts-wrapper">
                <h2 class="selected-spare-parts-heading">Выбранные запчасти</h2>
                <div id="selected-spare-parts" class="selected-spare-parts-table-wrapper">
                    <table class="selected-spare-parts-table">
                        <thead>
                            <tr>
                                <th class="column-name">Запчасть</th>
                                <th class="column-unit">Ед. изм.</th>
                                <th class="column-available">Доступно</th>
                                <th class="column-qty">Кол-во</th>
                                <th class="column-price">Цена</th>
                                <th class="column-sum">Сумма</th>
                            </tr>
                        </thead>
                        <tbody class="spare-parts-list"></tbody>
                    </table>
                </div>
            </div>
        `;

        // Вставляем после блока запчастей
        sparePartRow.parentNode.insertBefore(this.customBlock, sparePartRow.nextSibling);
    }

    async loadInitialData() {
        console.log('Loading initial data...');

        // Загружаем изначальные выбранные запчасти
        const selectedOptions = this.sparePartSelect.querySelectorAll('option');
        console.log(`Found ${selectedOptions.length} options in select`);

        for (let option of selectedOptions) {
            if (option.value && option.value.trim() !== '') {
                console.log(`Loading data for spare part: ${option.value}`);

                // Получаем данные о запчасти с сервера
                let results = await this.getSparePartData(option.value);
                if (results.length === 0) {
                    // Fallback если нет данных
                    results = [{
                        name: `Запчасть c ID: ${option.value} не найдена в поставках`,
                        quantity: 0,
                        id: option.value,
                        expiration_dt: null,
                        service_part_count: 0
                    }];
                }

                const group = new Set();

                for (let item of results) {
                    const expiration_dt = item.expiration_dt;
                    const uniqueKey = `${option.value}_${expiration_dt ? expiration_dt : 'none'}`;

                    this.sparePartsData.set(uniqueKey, {
                        ...item,
                        sparePartId: option.value,
                        uniqueKey: uniqueKey
                    });

                    // Получаем исходное количество из скрытых полей или service_part_count
                    const existingQuantity = this.getExistingQuantity(option.value, expiration_dt);
                    const initialQuantity = item.service_part_count !== undefined ? item.service_part_count : existingQuantity;
                    this.originalQuantities.set(uniqueKey, existingQuantity);
                    this.currentQuantities.set(uniqueKey, initialQuantity);

                    group.add(uniqueKey);

                    console.log(`Loaded spare part batch: ${item.name}, available: ${item.quantity}, existing: ${existingQuantity}, service_part_count: ${item.service_part_count || 0}`);
                }

                if (group.size > 0) {
                    this.sparePartGroups.set(option.value, group);
                }
            }
        }

        console.log(`Loaded ${this.sparePartsData.size} spare part batches`);
    }

    getExistingQuantity(sparePartId, expirationDt) {
        // Попытка получить существующее количество из data-атрибутов или других источников
        // Учитываем expiration_dt для матчинга

        // Ищем в скрытых полях формы
        const hiddenFields = document.querySelectorAll('input[name^="spare_part_quantities"]');
        for (let field of hiddenFields) {
            try {
                const data = JSON.parse(field.value);
                if (data.id === sparePartId &&
                    (data.expiration_dt === expirationDt ||
                     (data.expiration_dt == null && expirationDt == null))) {
                    return data.quantity || 0;
                }
            } catch (e) {
                continue;
            }
        }

        // Можно также попробовать получить из data-атрибута option, но для простоты пропускаем
        return 0; // По умолчанию
    }

    setupEventListeners() {
        // Отслеживаем изменения в select
        const observer = new MutationObserver((mutations) => {
            if (this.isUpdating) return; // Предотвращаем множественные обновления

            let hasChanges = false;
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                console.log('Select changed, updating...');
                this.handleSelectChange();
            }
        });

        observer.observe(this.sparePartSelect, {
            childList: true,
            subtree: true
        });

        // Также отслеживаем прямые изменения в select (для случаев когда MutationObserver может не сработать)
        this.sparePartSelect.addEventListener('change', () => {
            if (!this.isUpdating) {
                console.log('Select change event triggered');
                setTimeout(() => this.handleSelectChange(), 100);
            }
        });

        // Обработчик для формы сохранения
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const ok = await this.handleFormSubmit(e);
                if (ok) {
                    e.target.submit(); // теперь сабмит произойдёт уже с добавленными hidden-полями
                }
            });

            // Обработчик на кнопки submit: предотвращаем двойной вызов handleFormSubmit
            const submitButtons = document.querySelectorAll('.submit-row input[type="submit"]');
            submitButtons.forEach((button, btnIndex) => {
                console.log(`Adding click listener to submit button ${btnIndex}:`, button);
                button.addEventListener('click', async (e) => {
                    const ok = await this.handleFormSubmit(e);
                    if (!ok) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                });
            });
        }
    }

    async handleSelectChange() {
        if (this.isUpdating) {
            console.log('Already updating, skipping...');
            return;
        }

        console.log('Handling select change...');
        this.isUpdating = true;

        // Получаем текущие ID из select
        const currentIds = new Set();
        const selectedOptions = this.sparePartSelect.querySelectorAll('option');

        console.log(`Found ${selectedOptions.length} options in select`);

        for (let option of selectedOptions) {
            if (option.value && option.value.trim() !== '') {
                currentIds.add(option.value);

                // Если это новая запчасть (группа не загружена), получаем её данные
                if (!this.sparePartGroups.has(option.value)) {
                    console.log(`Loading new spare part: ${option.value}`);
                    let results = await this.getSparePartData(option.value);
                    if (results.length === 0) {
                        // Fallback
                        results = [{
                            name: `Запчасть c ID: ${option.value} не найдена`,
                            quantity: 0,
                            id: option.value,
                            expiration_dt: null,
                            service_part_count: 0
                        }];
                    }

                    const group = new Set();

                    for (let item of results) {
                        const expiration_dt = item.expiration_dt;
                        const uniqueKey = `${option.value}_${expiration_dt ? expiration_dt : 'none'}`;

                        if (!this.sparePartsData.has(uniqueKey)) {
                            this.sparePartsData.set(uniqueKey, {
                                ...item,
                                sparePartId: option.value,
                                uniqueKey: uniqueKey
                            });
                            const existingQuantity = this.getExistingQuantity(option.value, expiration_dt);
                            const initialQuantity = item.service_part_count !== undefined ? item.service_part_count : existingQuantity;
                            this.originalQuantities.set(uniqueKey, existingQuantity);
                            this.currentQuantities.set(uniqueKey, initialQuantity);

                            group.add(uniqueKey);
                        }
                    }

                    if (group.size > 0) {
                        this.sparePartGroups.set(option.value, group);
                    }
                }
            }
        }

        // Удаляем данные о запчастях, которых больше нет в select
        const toRemove = [];
        this.sparePartGroups.forEach((keys, id) => {
            if (!currentIds.has(id)) {
                console.log(`Removing spare part group: ${id}`);
                keys.forEach(key => toRemove.push(key));
                this.sparePartGroups.delete(id);
            }
        });

        toRemove.forEach(key => {
            this.sparePartsData.delete(key);
            this.originalQuantities.delete(key);
            this.currentQuantities.delete(key);
        });

        console.log(`Current spare parts batches count: ${this.sparePartsData.size}`);

        // Обновляем отображение
        await this.updateCustomBlock();

        this.isUpdating = false;
        console.log('Select change handled');
    }

    async updateCustomBlock() {
        console.log('Updating custom block...');
        const container = this.customBlock.querySelector('.spare-parts-list');
        if (!container) {
            console.error('Container not found');
            return;
        }

        // Очищаем контейнер
        container.innerHTML = '';

        console.log(`Creating rows for ${this.sparePartsData.size} spare parts batches`);

        // Создаем строки для каждой запчасти
        for (let [uniqueKey, sparePartData] of this.sparePartsData) {
            console.log(`Creating row for: ${sparePartData.name}`);
            await this.createSparePartRow(container, uniqueKey, sparePartData);
        }

        console.log('Custom block updated');
    }

    async createSparePartRow(container, uniqueKey, sparePartData) {
        const currentQty = this.currentQuantities.get(uniqueKey) || 0;
        const originalQty = this.originalQuantities.get(uniqueKey) || 0;
        const availableQty = sparePartData.quantity || 0;
        const price = parseFloat(sparePartData.price) || 0;
        const sum = this.formatMoney(price * currentQty);

        // Рассчитываем максимально допустимое количество для ввода
        const maxAllowed = availableQty + originalQty;
        const displayAvailable = this.formatQty(availableQty - currentQty + originalQty);
        const priceText = price > 0 ? `${this.formatMoney(price)}` : '<span class="no-price">цена не задана</span>';

        const row = document.createElement('tr');
        row.className = 'spare-part-row';
        row.setAttribute('data-unique-key', uniqueKey);

        row.innerHTML = `
            <td class="field-name" data-label="Запчасть"><strong>${sparePartData.name}</strong></td>
            <td class="field-unit" data-label="Ед. изм.">${sparePartData.unit || 'шт.'}</td>
            <td class="field-available" data-label="Доступно"><span class="available-qty">${displayAvailable}</span></td>
            <td class="field-qty" data-label="Кол-во">
                <input
                    type="number"
                    id="qty-${uniqueKey}"
                    value="${currentQty}"
                    min="0"
                    max="100000"
                    style="width: 70px;"
                    data-unique-key="${uniqueKey}"
                >
            </td>
            <td class="field-price" data-label="Цена"><span class="price-value">${priceText}</span></td>
            <td class="field-sum" data-label="Сумма"><span class="sum-value" data-sum="${sum}">${sum}</span></td>
        `;

        container.appendChild(row);

        // Обработчики событий для этой строки
        const qtyInput = row.querySelector(`#qty-${uniqueKey}`);

        qtyInput.addEventListener('change', (e) => {
            let newQty = parseFloat(e.target.value) || 0;
            if (newQty < 0) {
                newQty = 0;
                e.target.value = 0;
            }
            this.currentQuantities.set(uniqueKey, newQty);
            this.updateAvailableDisplay(uniqueKey);
        });

        qtyInput.addEventListener('input', (e) => {
            let newQty = parseFloat(e.target.value) || 0;
            if (newQty < 0) {
                newQty = 0;
                e.target.value = 0;
            }
            this.currentQuantities.set(uniqueKey, newQty);
            this.updateAvailableDisplay(uniqueKey);
        });
    }

    updateAvailableDisplay(uniqueKey) {
        const row = this.customBlock.querySelector(`tr[data-unique-key="${uniqueKey}"]`);
        if (!row) return;

        const availableSpan = row.querySelector('.available-qty');
        const sumValue = row.querySelector('.sum-value');
        const sparePartData = this.sparePartsData.get(uniqueKey);
        const currentQty = this.currentQuantities.get(uniqueKey) || 0;
        const originalQty = this.originalQuantities.get(uniqueKey) || 0;

        if (sparePartData) {
            const originalAvailable = sparePartData.quantity || 0;
            const displayAvailable = originalAvailable - currentQty + originalQty;
            availableSpan.textContent = this.formatQty(displayAvailable);

            const price = parseFloat(sparePartData.price) || 0;
            const sum = this.formatMoney(price * currentQty);
            sumValue.textContent = sum;
            sumValue.setAttribute('data-sum', sum);

            // Если ушли в минус — сразу подсвечиваем красным
            if (displayAvailable < 0) {
                row.classList.add('insufficient');
            } else {
                row.classList.remove('insufficient');
            }

            // Обновляем максимальное значение в input
            const qtyInput = row.querySelector(`#qty-${uniqueKey}`);
            // qtyInput.max = originalAvailable + originalQty;  // расскомментировать если выше добавляем max="${maxAllowed}"
        }
    }

    /**
     * Форматирует денежное значение в русском формате:
     * тысячи разделяются пробелом, копейки — запятой.
     * Пример: 20000.00 → "20 000,00"
     */
    formatMoney(value) {
        const num = Math.round((parseFloat(value) || 0) * 100) / 100;
        const [intPart, decPart] = num.toFixed(2).split('.');
        const formattedInt = parseInt(intPart, 10).toLocaleString('ru-RU');
        return `${formattedInt},${decPart}`;
    }

    /**
     * Форматирует количество: убирает floating-point шум и лишние нули.
     * 4.55 - 1.35 = 3.1999999999999997 → 3.2
     * 5 - 2 = 3.0 → 3
     */
    formatQty(value) {
        return Math.round(value * 100) / 100;
    }

    async getSparePartData(sparePartId) {
        console.log(`Fetching data for spare part: ${sparePartId}`);
        try {
            const currentPath = window.location.pathname;  // остается тольк путь без get параметров
            const serviceId = currentPath.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
            const response = await fetch(`/admin/get-spare-part-quantity/${serviceId}/${sparePartId}/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`Received data:`, data);
                return data.results || [];
            } else {
                console.error(`Failed to fetch data for ${sparePartId}: ${response.status}`);
            }
        } catch (error) {
            console.error('Error fetching spare part sparePartId:', error);
        }

        return [];
    }

    async handleFormSubmit(e) {
        // Подготавливаем данные для отправки
        const sparePartsData = [];

        console.log(this.currentQuantities);

        this.currentQuantities.forEach((quantity, uniqueKey) => {
            if (quantity > 0) {
                const data = this.sparePartsData.get(uniqueKey);
                sparePartsData.push({
                    id: data.sparePartId,
                    quantity: quantity,
                    originalQuantity: this.originalQuantities.get(uniqueKey) || 0,
                    expiration_dt: data.expiration_dt
                });
            }
        });

        // Добавляем скрытые поля в форму для передачи данных
        const form = e.target.closest('form') || e.target.form || e.target;

        // Удаляем предыдущие скрытые поля, если есть
        const existingFields = form.querySelectorAll('input[name^="spare_part_quantities"]');
        existingFields.forEach(field => field.remove());

        // Добавляем новые скрытые поля
        sparePartsData.forEach((item, index) => {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = `spare_part_quantities[${index}]`;
            hiddenField.value = JSON.stringify(item);
            form.appendChild(hiddenField);
        });

        // Валидация количеств
        const { errors, insufficientKeys } = this.validateQuantities();

        // Снимаем старую подсветку и наносим новую
        this.updateInsufficientHighlights(insufficientKeys);

        if (errors.length > 0) {
            const message = [
                '⚠️ Недостаточно запчастей на складе:',
                '',
                ...errors,
                '',
                'Уменьшите количество или уберите запчасть из списка выбранных.'
            ].join('\n');
            alert(message);
            return false;
        }

        return true;
    }

    validateQuantities() {
        const errors = [];
        const insufficientKeys = new Set();

        for (let [uniqueKey, currentQty] of this.currentQuantities) {
            const sparePartData = this.sparePartsData.get(uniqueKey);
            const originalQty = this.originalQuantities.get(uniqueKey) || 0;

            if (sparePartData && currentQty > 0) {
                const availableQty = sparePartData.quantity || 0;
                // Доступно сейчас = то что на складе + то что уже было списано в этой записи
                const effectiveAvailable = availableQty + originalQty;

                if (currentQty > effectiveAvailable) {
                    insufficientKeys.add(uniqueKey);
                    const deficit = currentQty - effectiveAvailable;
                    const expInfo = sparePartData.expiration_dt
                        ? ` (срок: ${sparePartData.expiration_dt})`
                        : '';
                    errors.push(
                        `• «${sparePartData.name}»${expInfo}: ` +
                        `запрошено ${this.formatQty(currentQty)}, ` +
                        `в наличии ${this.formatQty(effectiveAvailable)} ` +
                        `(не хватает ${this.formatQty(deficit)})`
                    );
                }
            }
        }

        return { errors, insufficientKeys };
    }

    /**
     * Подсвечивает красным строки с нехваткой, снимает подсветку с остальных.
     */
    updateInsufficientHighlights(insufficientKeys) {
        if (!this.customBlock) return;

        const rows = this.customBlock.querySelectorAll('.spare-part-row');
        rows.forEach(row => {
            const key = row.getAttribute('data-unique-key');
            if (insufficientKeys.has(key)) {
                row.classList.add('insufficient');
            } else {
                row.classList.remove('insufficient');
            }
        });
    }

    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }
}

// Инициализация при загрузке страницы
new SparePartsManager();