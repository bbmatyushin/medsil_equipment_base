import uuid
from enum import Enum

from django.db import models
from django.utils.text import slugify

company = '"medsil"'  # название схемы для таблиц


class PositionType(Enum):
    """Тип должности."""
    employee = 'Сотрудник'
    client = 'Клиент'


def get_instance_city():
    """Возвращает экземпляр модели City."""
    # return None  # расскомментировать перед миграцией
    return City.objects.get(name='Не указан')


def get_instance_country():
    """Возвращает экземпляр модели Country."""
    # return None  # расскомментировать перед миграцией
    return Country.objects.get(name='Россия')


def get_instance_unit():
    """Возвращает экземпляр модели Unit штука."""
    # return None  # расскомментировать перед миграцией
    return Unit.objects.get(short_name='шт.')


class City(models.Model):
    """Модель для перечьня городов."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Город',
        db_comment='Город', help_text='Город'
    )
    region = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Регион',
        db_comment='Регион', help_text='Регион, Область в которой расположен город'
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        db_table = f'{company}."city"'
        db_table_comment = 'Таблица с перечнем городов. \n\n-- BMatyushin'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        unique_together = ('name', 'region')
        # indexes = ['name', 'region']

    def __str__(self):  # в админ панели будет видно название города, вместо City object(1)
        return f"{self.name} {f'({self.region})' if self.region else ''}"

    def __repr__(self):
        return f"<City {self.name=!r}, {self.region=!r}>"


class Country(models.Model):
    """Модель для перечьня городов."""
    name = models.CharField(
        max_length=50, null=False, blank=False, unique=True, verbose_name='Страна',
        db_comment='Страна', help_text='Используется для Производителей и поставщиков'
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        db_table = f'{company}."country"'
        db_table_comment = 'Таблица с перечнем стран. \n\n-- BMatyushin'
        verbose_name = 'Страна'
        verbose_name_plural = 'Страны'

    def __str__(self):  # в админ панели будет видно название города, вместо City object(1)
        return f"{self.name}"

    def __repr__(self):
        return f"<Country {self.name=!r}"


class Engineer(models.Model):
    """Инженеры. Отдельная сущность, чтобы не привязываться к пользователю в системе.
    Через сигнал заполняется автоматически, если у нового пользователя должность инженер."""
    # TODO: Настроить сигнал для заполнения модели
    name = models.CharField(
        max_length=100, null=False, blank=False, unique=True,
        verbose_name='Инженер', db_comment='Имя инженера', help_text='Имя инженера'
    )
    user = models.OneToOneField(
        "users.CompanyUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="engineer_company_user", verbose_name='Пользователь системы',
        db_comment="ID пользователя", help_text="Зарегистрированный пользователь системы"
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
    )

    class Meta:
        db_table = f'{company}."engineer"'
        db_table_comment = ("Инженеры. Отдельная сущность, чтобы не привязываться к пользователю в системе.\n"
                            "Через сигнал заполняется автоматически, если у нового пользователя должность инженер."
                            "\n\n-- BMatyushin")
        verbose_name = 'Инженер'
        verbose_name_plural = 'Инженеры'

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<Engineer {self.name=!r}>'


class EquipmentStatus(models.Model):
    """Модель для фиксированного набора статусов оборудования"""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Статус оборудования', unique=True,
        db_comment='Статус оборудования', help_text='Статус оборудования',
    )

    class Meta:
        db_table = f'{company}."equipment_status"'
        db_table_comment = 'Таблица с набором статусов оборудования. \n\n-- BMatyushin'
        verbose_name = 'Статус оборудования'
        verbose_name_plural = 'Статусы оборудования'

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<EquipmentStatus {self.name=!r}>'


class MedDirection(models.Model):
    """Модель для перечьня направлений для оборудования: Гематологическое, Биохимическое и т.д."""
    name = models.CharField(
        max_length=100, null=False, blank=False, unique=True, verbose_name='Направление',
        db_comment='Направление медицинского оборудования (Гематологическое, Биохимическое и т.д.)',
    )
    slug_name = models.SlugField(
        max_length=100, null=False, editable=False, unique=False,
        db_comment='Slug для названия направления мед.оборудования'
    )

    class Meta:
        db_table = f'{company}."med_direction"'
        db_table_comment = ('Направления медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
                            '\n\n-- BMatyushin')
        verbose_name = 'Направление мед.оборудования'
        verbose_name_plural = 'Направления мед.оборудования'

    def save(self, *args, **kwargs):
        if self._state.adding and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<MedDirection {self.name=!r}>'


class Position(models.Model):
    """Справочник должностей."""
    POST_GROUPS = (
        ('Group 1', (
            ('employee', 'Сотрудник'),
        )),
        ('Group 2', (
            ('client', 'Клиент'),
        ))
    )
    POST = (
        ('employee', 'Сотрудник'),
        ('client', 'Клиент'),
    )

    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Должность',
        db_comment='Должность',
    )
    type = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Тип', default=PositionType.client.name,
        # choices=[(t.name, t.value) for t in PositionType],
        choices=POST,
        db_comment='Тип должности. Cотрудник - для компании, организации. Клиент - для учреждений',
        help_text='Тип должности. Cотрудник - для компании, организации. Клиент - для учреждений'
    )
    user = models.ManyToManyField(
        "users.CompanyUser", related_name="position_user", verbose_name='Сотрудник',
    )

    class Meta:
        db_table = f'{company}."position"'
        db_table_comment = 'Должности сотрудников и клиентов. \n\n-- BMatyushin'
        verbose_name = 'Должность'
        verbose_name_plural = 'Должности'
        unique_together = ('name', 'type')

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<Position {self.name=!r}>'


class ServiceType(models.Model):
    """Типы ремонта / Виды работ"""
    name = models.CharField(
        max_length=100, null=False, blank=False, verbose_name='Тип ремонта',
        db_comment='Тип ремонта', unique=True,
    )

    class Meta:
        db_table = f'{company}."service_type"'
        db_table_comment = 'Типы ремонтов / Виды работ. \n\n-- BMatyushin'
        verbose_name = 'Справочник с типом ремонта'
        verbose_name_plural = 'Справочник с типом ремонтов'

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<ServiceType {self.name=!r}>'


class Unit(models.Model):
    """Единицы измерения."""
    short_name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Сокращенное наименование',
        db_comment='Единица измерения', help_text='Единица измерения',
        unique=True,
    )
    full_name = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Полное наименование',
        db_comment='Полное наименование единицы измерения',
        help_text='Полное наименование единицы измерения'
    )

    class Meta:
        db_table = f'{company}."unit"'
        db_table_comment = 'Справочник с единицами измерения. \n\n-- BMatyushin'
        verbose_name = 'Единица измерения'
        verbose_name_plural = 'Единицы измерения'

    def __str__(self):
        return self.short_name

    def __repr__(self):
        return f'<Unit {self.short_name=!r}>'


class Manufacturer(models.Model):
    """Модель для перечьня производителей оборудования"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID записи', help_text='ID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Производитель',
        db_comment='Производитель оборудования', help_text='Производитель оборудования'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН', unique=True,
        db_comment='ИНН производителя', help_text='ИНН производителя'
    )
    country = models.ForeignKey(
        'Country', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="manufacturer_country", verbose_name='Страна',
        db_comment='Страна производителя',
    )
    city = models.ForeignKey(
        'City', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="manufacturer_city", verbose_name='Город',
        db_comment='Город производителя', help_text='Город производителя',
        default=get_instance_city
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес производителя', help_text='Адрес производителя'
    )
    contact_person = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Контактное лицо',
        db_comment='Контактное лицо производителя', help_text='Контактное лицо производителя'
    )
    contact_phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон производителя', help_text='Контактные телефоны производителя'
    )
    email = models.EmailField(
        max_length=100, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail производителя'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Действующий',
        db_comment='True, если производитель активен',
        help_text='True, если активен. Для мягкого удаления производителя.'
    )

    class Meta:
        db_table = f'{company}."manufacturer"'
        db_table_comment = 'Производители оборудования. \n\n-- BMatyushin'
        verbose_name = 'Производитель'
        verbose_name_plural = 'Производители'
        unique_together = ('name', 'city',)

    def __str__(self):
        return f"{self.name}{f', ({self.city.name})' if self.city.name != 'Не указан' else ''}"

    def __repr__(self):
        return f'<Manufacturer {self.name=!r}, {self.city=!r}>'


class Supplier(models.Model):
    """Поставщики оборудования."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID записи', help_text='ID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Поставщик',
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН', unique=True
    )
    country = models.ForeignKey(
        'Country', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supplier_country", verbose_name='Страна',
        db_comment='Страна производителя',
    )
    city = models.ForeignKey(
        'City', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supplier_city", verbose_name='Город',
        db_comment='Город поставщика', help_text='Город поставщика',
        default=get_instance_city
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес поставщика', help_text='Адрес поставщика'
    )
    contact_person = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Контактное лицо',
        db_comment='Контактное лицо поставщика', help_text='Контактное лицо поставщика'
    )
    contact_phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон поставщика', help_text='Контактные телефоны поставщика'
    )
    email = models.EmailField(
        max_length=100, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail поставщика'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Действующий',
        db_comment='True, если поставщик активен',
        help_text='True, если активен. Для мягкого удаления поставщика.'
    )

    class Meta:
        db_table = f'{company}."supplier"'
        db_table_comment = 'Поставщики оборудования. \n\n-- BMatyushin'
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        unique_together = ('name', 'city')

    def __str__(self):
        return f"{self.name}{f', ({self.city.name})' if self.city.name != 'Не указан' else ''}"

    def __repr__(self):
        return f'<Supplier {self.name=!r}, {self.city=!r}>'
