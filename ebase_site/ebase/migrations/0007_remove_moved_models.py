# Generated manually — removes moved models from ebase state only (tables already exist)

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ebase', '0006_update_content_types'),
    ]

    state_operations = [
        migrations.DeleteModel(name='Client'),
        migrations.DeleteModel(name='Department'),
        migrations.DeleteModel(name='DeptContactPers'),
        migrations.DeleteModel(name='Manufacturer'),
        migrations.DeleteModel(name='Supplier'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],  # Таблицы не удаляем — они на месте
        ),
    ]
