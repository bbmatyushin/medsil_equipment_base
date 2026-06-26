import uuid
from pathlib import Path

from django.db import models
from django.conf import settings
from django.core import validators
from django.core.validators import MinValueValidator

# from django.contrib.postgres.fields import ArrayField
from django.utils.timezone import now


company = '"medsil"'  # название схемы для таблиц


class EbaseModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
        db_comment="ID записи",
        help_text="ID записи",
    )
    create_dt = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        verbose_name="Дата создания",
        db_comment="Дата создания записи.",
        help_text="Дата создания записи. Заполняется автоматически",
    )

    class Meta:
        abstract = True


class Equipment(EbaseModel):
    """Модель для перечьня моделей медицинского оборудования.
    Для полей с автоматическим заполнением, обязательно editable=False"""

    full_name = models.CharField(
        max_length=256,
        null=True,
        blank=False,
        db_comment="Полное наименование оборудования",
        verbose_name="Полное наименование",
        help_text="Полное наименование + краткое должно быть уникальным сочетанием",
    )
    short_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Краткое наименование",
        db_comment="Краткое наименование оборудования",
        help_text="Полное наименование + краткое должно быть уникальным сочетанием",
    )
    med_direction = models.ForeignKey(
        "directory.MedDirection",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="equipment_med_equipment",
        verbose_name="Направление",
        db_comment="ID направления",
        help_text="ID из таблицы Направления.",
    )
    manufacturer = models.ForeignKey(
        "directory.Manufacturer",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="equipment_manufacturer",
        verbose_name="Производитель",
        db_comment="ID производителя",
        help_text="ID из таблицы Производителя.",
    )
    supplier = models.ForeignKey(
        "directory.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_supplier",
        verbose_name="Поставщик",
        db_comment="ID поставщика",
    )
    spare_part = models.ManyToManyField(
        "spare_part.SparePart",
        related_name="equipment_spare_part",
        verbose_name="ID Запасных частей",
        help_text="ID из таблицы Запасных частей.",
    )

    class Meta:
        db_table = f'{company}."equipment"'
        db_table_comment = "Перечень моделей медициского оборудования.\n\n-- BMatyushin"
        verbose_name = "Мед. оборудование"
        verbose_name_plural = "Мед. оборудование"
        unique_together = (
            "full_name",
            "short_name",
        )
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["short_name"]),
            models.Index(fields=["med_direction"]),
            models.Index(fields=["manufacturer"]),
            models.Index(fields=["supplier"]),
        ]

    def __str__(self):
        return self.full_name

    def __repr__(self):
        return f"<Equipment {self.full_name=!r}>"


class EquipmentAccounting(EbaseModel):
    """Модель для учета оборудований.
    Для полей с автоматическим заполнением, обязательно editable=False"""

    equipment = models.ForeignKey(
        "Equipment",
        on_delete=models.RESTRICT,
        null=False,
        editable=True,
        related_name="equipment_accounting_equipment",
        verbose_name="Оборудования",
        db_comment="ID оборудования",
    )
    equipment_status = models.ForeignKey(
        "directory.EquipmentStatus",
        on_delete=models.SET_NULL,
        null=True,
        editable=True,
        related_name="equipment_accounting_equipment_status",
        verbose_name="Статус",
        db_comment="ID статуса оборудования",
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="equipment_accounting_user",
        verbose_name="Пользователь",
        db_comment='Пользователь, который добавил запись в таблицу "Учёт оборудования"',
        help_text=(
            'Пользователь, который добавил запись в таблицу "Учёт оборудования". '
            "Заполняется автоматически"
        ),
    )
    serial_number = models.CharField(
        max_length=50,
        null=False,
        blank=False,
        verbose_name="Серийный номер",
        db_comment="Серийный номер оборудования",
        help_text="Серийный номер оборудования",
    )
    is_our_service = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name="Проведено ТО",
        db_comment="True, если оборудование обслуживалось нами",
    )
    is_our_supply = models.BooleanField(
        null=False,
        blank=False,
        default=True,
        verbose_name="Поставлен нами",
        db_comment="True, если оборудование было поставлено нами",
    )
    is_our_reagents = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name="Поставка реагентов",
        db_comment="True, если реагенты поставляются нами",
    )
    row_update_dt = models.DateTimeField(
        auto_now=True,
        editable=False,
        verbose_name="Дата обновления строки",
        db_comment="Дата обновления строки.",
        help_text="Дата обновления строки. Заполняется автоматически",
    )
    url_youjail = models.URLField(
        max_length=2000,
        verbose_name="Ссылка YouJail",
        null=True,
        blank=True,
        default=None,
        help_text="Ссылка для связи с сервисом YouJail",
        db_comment="Ссылка для связи с сервисом YouJail",
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name="Комментарий", db_comment="Комментарий"
    )

    class Meta:
        db_table = f'{company}."equipment_accounting"'
        indexes = [
            models.Index(fields=["equipment"]),
            models.Index(fields=["serial_number"], name="serial_number_idx"),
            models.Index(fields=["equipment_status"]),
            models.Index(fields=["is_our_supply"]),
            models.Index(fields=["is_our_service"]),
            models.Index(fields=["user"]),
        ]
        db_table_comment = (
            "Таблица с учёт оборудования. Для отслеживаия оборудования по его серийному "
            "номеру.\n\n-- BMatyushin"
        )
        verbose_name = "Учёт оборудования"
        verbose_name_plural = "1. Учёт оборудований"
        unique_together = ("serial_number", "equipment")

    def get_absolute_url(self):
        return "http://109.172.114.134/%s/" % self.pk
        # return reverse('equipment_accounting_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.equipment} [{self.serial_number.upper()}]"

    def __repr__(self):
        return f"<EquipmentAccounting {self.serial_number=!r}>"


class EquipmentAccDepartment(EbaseModel):
    """Учет поставленного оборудования в подразделения клиента"""

    equipment_accounting = models.ForeignKey(
        "EquipmentAccounting",
        on_delete=models.CASCADE,
        null=False,
        editable=True,
        related_name="equipment_acc_department_equipment_accounting",
        verbose_name="Оборудование",
        db_comment="ID Учёта оборудования",
        help_text="Поставленное оборудование",
    )
    department = models.ForeignKey(
        "clients.Department",
        on_delete=models.RESTRICT,
        null=False,
        editable=True,
        related_name="equipment_accounting_department_department",
        verbose_name="Подразделение",
        db_comment="ID подразделения",
        help_text="Подразделение или филиал клиента",
    )
    engineer = models.ForeignKey(
        "directory.Engineer",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="equipment_accounting_engineer",
        verbose_name="Инженер",
        help_text="Инженер, который запускал оборудование",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="У клиента",
        db_comment="Флаг, указывающий на то, что прибор установлен в подразделении клиента",
        help_text="Флаг, указывающий на то, что прибор установлен в подразделении клиента",
    )
    install_dt = models.DateField(
        null=True,
        blank=False,
        verbose_name="Дата монтажа",
        db_comment="Дата установки оборудования в подразделении клиента",
        help_text="Дата установки оборудования в подразделении клиента",
    )

    class Meta:
        db_table = f'{company}."equipment_acc_department"'
        db_table_comment = (
            "Учет поставленного оборудования в подразделения клиента.\n\n-- BMatyushin"
        )
        verbose_name = "Оборудование по клиентам"
        verbose_name_plural = "Оборудование по клиентам"
        indexes = [
            models.Index(fields=["equipment_accounting"]),
            models.Index(fields=["department"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["install_dt"]),
            models.Index(fields=["engineer"]),
        ]

    def __str__(self):
        return f"{self.department} - {self.equipment_accounting}"

    def __repr__(self):
        return f"<EquipmentAccDepartment {self.id=!r}, {self.is_active=!r}>"


class ReplacementEquipment(EbaseModel):
    """Подменное оборудование для временной замены"""

    equipment = models.ForeignKey(
        "Equipment",
        on_delete=models.RESTRICT,
        null=False,
        blank=False,
        related_name="replacement_equipment_equipment",
        verbose_name="Модель оборудования",
        db_comment="ID модели подменного оборудования",
        help_text="Модель подменного оборудования",
    )
    serial_number = models.CharField(
        max_length=50,
        null=False,
        blank=False,
        verbose_name="Серийный номер",
        db_comment="Серийный номер подменного прибора",
        help_text="Серийный номер подменного прибора",
    )
    accessories = models.ManyToManyField(
        "spare_part.SparePartAccessories",
        blank=True,
        related_name="replacement_equipment_accessories",
        verbose_name="Комплектующие",
        db_comment="ID комплектующих к прибору",
        help_text="Комплектующие, которые передаются с прибором",
    )
    state = models.CharField(
        max_length=20,
        null=False,
        blank=False,
        verbose_name="Состояние",
        db_comment="Состояние оборудования: рабочий/не рабочий",
        help_text="Состояние оборудования",
        choices=[("working", "Рабочий"), ("not_working", "Не рабочий")],
        default="working",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Комментарий",
        db_comment="Комментарий к подменному оборудованию",
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="replacement_equipment_user",
        verbose_name="Пользователь",
        db_comment="Пользователь, который добавил запись о подменном оборудовании",
        help_text="Пользователь, который добавил запись о подменном оборудовании",
    )

    class Meta:
        db_table = f'{company}."replacement_equipment"'
        db_table_comment = (
            "Подменное оборудование для временной замены.\n\n-- BMatyushin"
        )
        verbose_name = "Подменное оборудование"
        verbose_name_plural = "Подменное оборудование"
        indexes = [
            models.Index(fields=["equipment"]),
            models.Index(fields=["serial_number"]),
            models.Index(fields=["state"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        accessories_list = list(self.accessories.all().values_list("name", flat=True))
        accessories_info = (
            f" с комплектующими: {', '.join(accessories_list)}"
            if accessories_list
            else ""
        )
        return f"{self.equipment.short_name} [{self.serial_number}]{accessories_info}"

    def __repr__(self):
        return f"<ReplacementEquipment {self.serial_number=!r}, {self.state=!r}>"


class ServiceAccessories(models.Model):
    """Промежуточная модель для связи сервиса и комплектующих с количеством"""

    service = models.ForeignKey(
        "Service",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="service_accessories",
        verbose_name="Ремонт",
        db_comment="ID ремонта",
    )
    accessory = models.ForeignKey(
        "spare_part.SparePartAccessories",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="service_accessories_accessory",
        verbose_name="Комплектующее",
        db_comment="ID комплектующего",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Количество",
        db_comment="Количество комплектующих",
        help_text="Количество используемых комплектующих",
    )
    create_dt = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        verbose_name="Дата создания",
        db_comment="Дата создания записи",
    )

    class Meta:
        db_table = f'{company}."service_accessories"'
        db_table_comment = (
            "Связь ремонта с комплектующими и их количеством.\n\n-- BMatyushin"
        )
        verbose_name = "Комплектующее для ремонта"
        verbose_name_plural = "Комплектующие для ремонта"
        unique_together = ("service", "accessory")

    def __str__(self):
        return f"{self.accessory.name} - {self.quantity} шт."

    def __repr__(self):
        return f"<ServiceAccessories {self.accessory.name=!r}, {self.quantity=!r}>"


class Service(EbaseModel):
    """Таблица для учета поступившего на ремонт оборудования."""

    replacement_equipment = models.OneToOneField(
        "ReplacementEquipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_replacement_equipment",
        verbose_name="Передается на время ремонта",
        db_comment="ID подменного оборудования, передаваемого на время ремонта",
        help_text="Подменное оборудование, передаваемое на время ремонта",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        unique=True,
        related_name="service",
        verbose_name="Связанный Контракт",
        db_comment="ID контракта из реестра контрактов",
        help_text="Контракт, связанный с данным ремонтом. Один контракт может быть связан только с одним ремонтом.",
    )
    service_type = models.ForeignKey(
        "directory.ServiceType",
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="service_service_type",
        verbose_name="Типа ремонта",
        db_comment="ID Типа ремонта",
    )
    equipment_accounting = models.ForeignKey(
        "EquipmentAccounting",
        related_name="service_equipment_accounting",
        verbose_name="Оборудование для ремонта. ",
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.RESTRICT,
        null=False,
        blank=False,
        related_name="service_company_user",
        verbose_name="ID Пользователя",
        db_comment="ID Пользователя (сотрудника)",
        help_text='Пользователь из таблицы "Пользователи"',
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Описание неисправности",
        db_comment="Описание неисправности",
    )
    reason = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Причина",
        db_comment="На основании чего делается ремонт",
        help_text="На основании чего делается ремонт",
    )
    job_content = models.TextField(
        null=True,
        blank=True,
        verbose_name="Содержание работ",
        db_comment="Содержание работ",
    )
    beg_dt = models.DateField(
        null=False,
        blank=False,
        editable=True,
        verbose_name="Дата начала",
        db_comment="Дата начала ремонта",
        help_text="Дата начала ремонта",
        default=now,
    )
    end_dt = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата окончания",
        db_comment="Дата окончания ремонта",
        help_text="Дата окончания ремонта",
    )
    returned_to_office = models.BooleanField(
        default=False,
        verbose_name="Вернули в офис",
        db_comment="Флаг, означающий что подменное оборудование физически вернулось в офис",
        help_text="Отметьте, если подменное оборудование фактически вернулось в офис",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Комментарии",
        db_comment="Примечание, комментарии по ремонту",
        help_text="Примечание, комментарии по ремонту",
    )
    spare_part = models.ManyToManyField(
        "spare_part.SparePart",
        related_name="service_spare_part",
        verbose_name="Запчасти",
        help_text="Запчасти, которые используются в ремонте. ",
        blank=True,
    )
    spare_part_count = models.JSONField(
        default=dict,
        blank=True,
        editable=False,
        db_comment="Для хранения сколько и каких запчестей использовалось в ремонте. "
        "Формат - {spare_part_id: {expiration_dt: date, service_part_count: count}}",
    )
    contact_person_data = models.JSONField(
        default=dict,
        blank=True,
        editable=False,
        db_comment="Для хранения данных выбранного контактного лица. "
        'Формат - {contact_person_id: id, fio: "ФИО"}',
    )
    accessories = models.ManyToManyField(
        "spare_part.SparePartAccessories",
        through="ServiceAccessories",
        blank=True,
        verbose_name="Комплектующие",
        help_text="Комплектующие, используемые в ремонте",
    )
    service_akt = models.CharField(
        max_length=2056,
        null=True,
        blank=True,
        verbose_name="Акт",
        db_comment="Акт о проведении работ",
        help_text="Акт о проведении работ",
        validators=[validators.RegexValidator(regex=r"\.docs$|\.doc$")],
    )
    accept_in_akt = models.CharField(
        max_length=2056,
        null=True,
        blank=True,
        verbose_name="Акт в ремонт",
        db_comment="Акт приема-передачи оборудования в ремонт",
        help_text="Акт приёма-передачи оборудования в ремонт",
        validators=[validators.RegexValidator(regex=r"\.docs$|\.doc$")],
    )
    accept_from_akt = models.CharField(
        max_length=2056,
        null=True,
        blank=True,
        verbose_name="Акт из ремонта",
        db_comment="Акт приема-передачи оборудования из ремонт",
        help_text="Акт приёма-передачи оборудования из ремонт",
        validators=[validators.RegexValidator(regex=r"\.docs$|\.doc$")],
    )

    class Meta:
        db_table = f'{company}."service"'
        db_table_comment = "Учет ремонта оборудования. \n\n-- BMatyushin"
        verbose_name = "Ремонт оборудования"
        verbose_name_plural = "Ремонт оборудования"
        indexes = [
            models.Index(fields=["equipment_accounting"]),
            models.Index(fields=["service_type"]),
            models.Index(fields=["beg_dt"]),
            models.Index(fields=["end_dt"]),
            models.Index(fields=["-beg_dt"]),  # Для сортировки по убыванию
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.equipment_accounting} - {self.service_type}"

    def __repr__(self):
        return f"<Service {self.id=!r}, {self.user=!r}>"


class ServicePhotos(EbaseModel):
    """Набор фото связанных с ремонтом"""

    service = models.ForeignKey(
        "Service",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="service_photos",
        verbose_name="Ремонт",
        db_comment="ID Ремонта",
    )
    photo = models.ImageField(
        upload_to="service/%Y/",
        blank=True,
        null=True,
        verbose_name="Фото ремонта",
        db_comment="Ссылка на поле для фото связанных с ремонтом",
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="service_photo_user",
        verbose_name="ID Пользователя",
        db_comment="ID Пользователя (сотрудника)",
        help_text='Пользователь из таблицы "Пользователи"',
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, verbose_name="Когда было добавлено фото"
    )

    class Meta:
        db_table = f'{company}."service_photos"'
        db_table_comment = "Фотографии ремонта оборудования. \n\n-- BMatyushin"
        verbose_name = "Фото ремонта"
        verbose_name_plural = "Фото ремонта"

    def delete(self, using=None, keep_parents=False):
        self.photo.delete(save=False)
        super().delete(using=None, keep_parents=False)

    def __str__(self):
        return f"{self.service} - {self.photo}"

    def __repr__(self):
        return f"<ServicePhotos {self.id=!r}, {self.service=!r}>"


class ServiceExpense(EbaseModel):
    """Материализованные расходы на запчасти в ремонте (для аналитики)."""

    service = models.ForeignKey(
        "Service",
        on_delete=models.CASCADE,
        related_name="service_expenses",
        verbose_name="Ремонт",
        db_comment="ID ремонта",
    )
    spare_part = models.ForeignKey(
        "spare_part.SparePart",
        on_delete=models.RESTRICT,
        related_name="service_expense_spare_part",
        verbose_name="Запчасть",
        db_comment="ID запчасти",
    )
    quantity = models.FloatField(
        validators=[MinValueValidator(0)],
        verbose_name="Кол-во",
        db_comment="Количество запчастей, использованных в ремонте",
    )
    unit = models.CharField(
        max_length=50, verbose_name="Ед. изм.", db_comment="Единица измерения запчасти"
    )
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Цена закупки",
        db_comment="Закупочная цена по FIFO",
    )
    sum = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Сумма",
        db_comment="quantity * price",
    )

    class Meta:
        db_table = f'{company}."service_expense"'
        db_table_comment = (
            "Расходы на запчасти по ремонту (для аналитики).\n\n-- Generated"
        )
        verbose_name = "Расход ремонта"
        verbose_name_plural = "Расходы ремонта"
        indexes = [
            models.Index(fields=["service"]),
            models.Index(fields=["spare_part"]),
        ]

    def __str__(self):
        return f"{self.spare_part.name} — {self.sum}"

    def save(self, *args, **kwargs):
        from decimal import Decimal

        self.sum = Decimal(str(self.quantity or 0)) * Decimal(str(self.price or 0))
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"sum"}
        super().save(*args, **kwargs)
