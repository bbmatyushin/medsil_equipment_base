import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser


class CompanyUser(AbstractUser):
    """Модель пользователя."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID пользователя',
                          help_text='ID пользователя')
    patron = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Отчество',
        db_comment='Отчество', help_text='Отчество'
    )
    sex = models.IntegerField(
        null=True, blank=True, verbose_name='Пол',
        db_comment='Пол. 1 - Мужской, 2 - Женский', choices=[(1, 'Мужской'), (2, 'Женский')]
    )
    birth = models.DateField(
        null=True, blank=True, verbose_name='Дата рождения',
        db_comment='Дата рождения', help_text='Дата рождения'
    )
    phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон', help_text='Телефоны, до 100 символов.'
    )
    equipment_acc_department = models.ManyToManyField(
        'ebase.EquipmentAccDepartment', related_name='company_user_equipment_acc_department',
        verbose_name='Учет поставленного оборудования',
    )
    position = models.ManyToManyField(
        'directory.Position', related_name='company_user_position',
        verbose_name='Должность', help_text='Может быть несколько должностей',
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name']

    class Meta:
        db_table = 'company_user'
        db_table_comment = 'Таблица с пользователями. \n\n-- BMatyushin'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return (f"{self.first_name if self.first_name else ''} "
                f"{self.patron if self.patron else ''} " 
                f"{self.last_name if self.last_name else ''} " 
                f"{f'({self.username})' if self.username else ''}")

    def __repr__(self):
        return f"<CompanyUser {self.username=!r}>"
