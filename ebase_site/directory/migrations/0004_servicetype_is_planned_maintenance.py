from django.db import migrations, models

# Значения зафиксированы здесь, а не взяты из directory.models: миграция
# не должна меняться вслед за моделью.
PLANNED_MAINTENANCE_NAMES = ("Тех. обслуживание",)
PLANNED_MAINTENANCE_HELP = (
    "Отметьте, если это плановое техническое обслуживание. "
    "В разделе «Аналитика» → «Оборудование» такие работы считаются ТО "
    "(плитка «ТО проведено», график ТО по месяцам), а не поломками: "
    "они не входят в надёжность моделей и повторные ремонты. "
    "Виды работ без отметки считаются ремонтами."
)


def mark_planned_maintenance(apps, schema_editor):
    """Ставит флаг «Плановое ТО» виду «Тех. обслуживание» (если он есть).

    Идемпотентна: повторный проход ничего не меняет.
    """
    ServiceType = apps.get_model("directory", "ServiceType")
    ServiceType.objects.filter(name__in=PLANNED_MAINTENANCE_NAMES).update(
        is_planned_maintenance=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0003_supplier_manufacturer"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicetype",
            name="is_planned_maintenance",
            field=models.BooleanField(
                db_comment="True — вид работ считается плановым ТО, а не поломкой (раздел «Аналитика»)",
                default=False,
                help_text=PLANNED_MAINTENANCE_HELP,
                verbose_name="Плановое ТО",
            ),
        ),
        # Откат: данные не меняются, поле удаляет обратная операция AddField
        migrations.RunPython(mark_planned_maintenance, migrations.RunPython.noop),
    ]
