# Generated manually — updates FK references BEFORE models are removed from ebase state

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ebase', '0005_servicephotos'),
        ('clients', '0001_initial'),
        ('directory', '0003_supplier_manufacturer'),
    ]

    state_operations = [
        migrations.AlterField(
            model_name='equipment',
            name='manufacturer',
            field=models.ForeignKey(
                db_comment='ID производителя',
                help_text='ID из таблицы Производителя.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='equipment_manufacturer',
                to='directory.manufacturer',
                verbose_name='Производитель',
            ),
        ),
        migrations.AlterField(
            model_name='equipment',
            name='supplier',
            field=models.ForeignKey(
                blank=True,
                db_comment='ID поставщика',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='equipment_supplier',
                to='directory.supplier',
                verbose_name='Поставщик',
            ),
        ),
        migrations.AlterField(
            model_name='equipmentaccdepartment',
            name='department',
            field=models.ForeignKey(
                db_comment='ID подразделения',
                help_text='Подразделение или филиал клиента',
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='equipment_accounting_department_department',
                to='clients.department',
                verbose_name='Подразделение',
            ),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],  # FK в БД не изменились — ссылаются на те же таблицы
        ),
    ]
