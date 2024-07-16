
# 1. python manage.py makemigrations ebase --empty
# 2. В файле миграции дописать функцию для добавления записи в таблицу
#    с помощью RunPython

from django.db import migrations


def add_unit(apps, schema_editor):
    Unit = apps.get_model('ebase', 'Unit')
    Unit.objects.create(full_name='штука', short_name='шт')


class Migration(migrations.Migration):

    dependencies = [
        ('ebase', '0001_initial'),  # TODO: 0001_initial - заменить на нужный файл миграции
    ]

    operations = [
        migrations.RunPython(add_unit),
    ]

# 3. python manage.py migrate ebase
