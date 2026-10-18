from django.db import migrations

# Значения зафиксированы здесь, а не взяты из analytics.models: миграция
# не должна меняться вслед за моделью.
GROUP_NAME = "Аналитика"
EQUIPMENT = ("view_equipment", "Аналитика: Оборудование")


def _content_type(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="analytics", model="analyticsaccess"
    )
    return content_type


def add_equipment_tab(apps, schema_editor):
    """Право «Оборудование», выдаётся группе «Аналитика» (если она есть).

    Идемпотентна: повторный проход, в том числе после отката на новом коде,
    когда `post_migrate` уже пересоздал права по модели, даёт тот же результат.
    """
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    equipment, _ = Permission.objects.get_or_create(
        content_type=_content_type(apps),
        codename=EQUIPMENT[0],
        defaults={"name": EQUIPMENT[1]},
    )
    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is not None:
        group.permissions.add(equipment)


def remove_equipment_tab(apps, schema_editor):
    """Откат: удаляет право «Оборудование» вместе с его выдачами."""
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(
        content_type=_content_type(apps), codename=EQUIPMENT[0]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0004_trips_tab"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="analyticsaccess",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("view_finance", "Аналитика: Финансы"),
                    ("view_trips", "Аналитика: Командировки"),
                    ("view_equipment", "Аналитика: Оборудование"),
                ),
                "verbose_name": "Доступ к аналитике",
                "verbose_name_plural": "Доступ к аналитике",
            },
        ),
        migrations.RunPython(add_equipment_tab, remove_equipment_tab),
    ]
