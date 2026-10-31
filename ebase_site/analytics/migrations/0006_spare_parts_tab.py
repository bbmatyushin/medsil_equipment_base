from django.db import migrations

GROUP_NAME = "Аналитика"
SPARE_PARTS = ("view_spare_parts", "Аналитика: Запчасти")


def _content_type(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="analytics", model="analyticsaccess"
    )
    return content_type


def add_spare_parts_tab(apps, schema_editor):
    """Создаёт право «Запчасти» и выдаёт его группе «Аналитика»."""
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    spare_parts, _ = Permission.objects.get_or_create(
        content_type=_content_type(apps),
        codename=SPARE_PARTS[0],
        defaults={"name": SPARE_PARTS[1]},
    )
    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is not None:
        group.permissions.add(spare_parts)


def remove_spare_parts_tab(apps, schema_editor):
    """Удаляет право «Запчасти» вместе с его выдачами."""
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(
        content_type=_content_type(apps), codename=SPARE_PARTS[0]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0005_equipment_tab"),
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
                    ("view_spare_parts", "Аналитика: Запчасти"),
                ),
                "verbose_name": "Доступ к аналитике",
                "verbose_name_plural": "Доступ к аналитике",
            },
        ),
        migrations.RunPython(add_spare_parts_tab, remove_spare_parts_tab),
    ]
