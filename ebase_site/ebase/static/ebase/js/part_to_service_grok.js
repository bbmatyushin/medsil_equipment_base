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

    createCustomBlock() {
        const sparePartRow = document.querySelector('.form-row.field-spare_part');
        if (!sparePartRow) {
            console.error('Spare part form row not found');
            return;
        }

        // Создаем контейнер для кастомного блока
        this.customBlock = document.createElement('div');
        this.customBlock.className = 'form-row custom-choice-spare_part';
        this.customBlock.innerHTML = `
            <div>
                <label>Выбранные запчасти:</label>
                <div id="selected-spare-parts" style="border: 1px solid #ccc; padding: 10px; margin-top: 5px; background: #f9f9f9;">
                    <div class="spare-parts-list"></div>
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

            // Также добавляем обработчик на кнопки submit
            const submitButtons = document.querySelectorAll('.submit-row input[type="submit"]');
            submitButtons.forEach((button, btnIndex) => {
                console.log(`Adding click listener to submit button ${btnIndex}:`, button);
                button.addEventListener('click', async (e) => this.handleFormSubmit(e));
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

        // Рассчитываем максимально допустимое количество для ввода
        const maxAllowed = availableQty + originalQty;

        const row = document.createElement('div');
        row.className = 'spare-part-row';
        row.setAttribute('data-unique-key', uniqueKey);
        row.style.cssText = `
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        `;

        // Добавить max="${maxAllowed}" чтобы не дать выбрать больше чем на складе
        // и расскомментировать qtyInput.max = originalAvailable + originalQty; ниже
        row.innerHTML = `
            <div style="flex: 1; margin-right: 10px;">
                <strong>${sparePartData.name}</strong>
            </div>
            <div style="margin-right: 10px;">
                Доступно: <span class="available-qty">${Math.max(0, availableQty - currentQty + originalQty)}</span> шт.
            </div>
            <div style="margin-right: 10px;">
                <label for="qty-${uniqueKey}">Количество:</label>
                <input
                    type="number"
                    id="qty-${uniqueKey}"
                    value="${currentQty}"
                    min="0"
                    max="100000"
                    style="width: 80px; margin-left: 5px;"
                    data-unique-key="${uniqueKey}"
                >
            </div>`;

        container.appendChild(row);

        // Обработчики событий для этой строки
        const qtyInput = row.querySelector(`#qty-${uniqueKey}`);

        qtyInput.addEventListener('change', (e) => {
            const newQty = parseFloat(e.target.value) || 0;
            this.currentQuantities.set(uniqueKey, newQty);
            this.updateAvailableDisplay(uniqueKey);
        });

        qtyInput.addEventListener('input', (e) => {
            const newQty = parseFloat(e.target.value) || 0;
            this.currentQuantities.set(uniqueKey, newQty);
            this.updateAvailableDisplay(uniqueKey);
        });
    }

    updateAvailableDisplay(uniqueKey) {
        const row = this.customBlock.querySelector(`[data-unique-key="${uniqueKey}"]`);
        if (!row) return;

        const availableSpan = row.querySelector('.available-qty');
        const sparePartData = this.sparePartsData.get(uniqueKey);
        const currentQty = this.currentQuantities.get(uniqueKey) || 0;
        const originalQty = this.originalQuantities.get(uniqueKey) || 0;

        if (sparePartData) {
            const originalAvailable = sparePartData.quantity || 0;
            const displayAvailable = originalAvailable - currentQty + originalQty;
            availableSpan.textContent = Math.max(0, displayAvailable);

            // Обновляем максимальное значение в input
            const qtyInput = row.querySelector(`#qty-${uniqueKey}`);
            // qtyInput.max = originalAvailable + originalQty;  // расскомментировать если выше добавляем max="${maxAllowed}"
        }
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
//        const isValid = this.validateQuantities();
//        if (!isValid) {
//            e.preventDefault();
//            alert('Проверьте количества запчастей. Некоторые значения превышают доступное количество.');
//            return false;
//        }

        return true;
    }

    validateQuantities() {
        for (let [uniqueKey, currentQty] of this.currentQuantities) {
            const sparePartData = this.sparePartsData.get(uniqueKey);
            const originalQty = this.originalQuantities.get(uniqueKey) || 0;

            if (sparePartData) {
                const availableQty = sparePartData.quantity || 0;
                const maxAllowed = availableQty + originalQty;

                if (currentQty > maxAllowed) {
                    console.error(`Spare part batch ${uniqueKey}: ${currentQty} > ${maxAllowed}`);
                    return false;
                }
            }
        }
        return true;
    }

    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }
}

// Инициализация при загрузке страницы
new SparePartsManager();