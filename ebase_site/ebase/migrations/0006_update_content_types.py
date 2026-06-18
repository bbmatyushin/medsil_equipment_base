# Generated manually — updates django_content_type for moved models

from django.db import migrations


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # При применении state-миграций (SeparateDatabaseAndState с CreateModel)
    # Django создаёт новые записи ContentType для моделей в новых приложениях.
    # Но старые записи (ebase.*) уже существуют и связаны с permissions.
    # Поэтому: удаляем новые (дубликаты), переименовываем старые.

    moves = [
        # (old_app_label, model_name, new_app_label)
        ('ebase', 'client', 'clients'),
        ('ebase', 'department', 'clients'),
        ('ebase', 'deptcontactpers', 'clients'),
        ('ebase', 'manufacturer', 'directory'),
        ('ebase', 'supplier', 'directory'),
    ]

    for old_app, model_name, new_app in moves:
        # Удаляем новую запись (созданную state-миграцией), если она есть
        ContentType.objects.filter(app_label=new_app, model=model_name).delete()
        # Переименовываем старую запись
        ContentType.objects.filter(app_label=old_app, model=model_name).update(app_label=new_app)


class Migration(migrations.Migration):
    dependencies = [
        ('ebase', '0005_servicephotos'),
        ('clients', '0001_initial'),
        ('directory', '0003_supplier_manufacturer'),
    ]

    operations = [
        migrations.RunPython(update_content_types, migrations.RunPython.noop),
    ]
