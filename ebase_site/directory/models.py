from enum import Enum

from django.db import models


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
        max_length=50, null=False, blank=False, verbose_name='Статус', unique=True,
        db_comment='Статус оборудования', help_text='Статус оборудования'
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

    class Meta:
        db_table = f'{company}."med_direction"'
        db_table_comment = ('Направления медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
                            '\n\n-- BMatyushin')
        verbose_name = 'Направление мед.оборудования'
        verbose_name_plural = 'Направления мед.оборудования'

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<MedDirection {self.name=!r}>'


class Position(models.Model):
    """Справочник должностей."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Должность',
        db_comment='Должность',
    )
    type = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Тип', default=PositionType.client.name,
        choices=[(t.name, t.value) for t in PositionType],
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
