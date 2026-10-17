from django.db import migrations

# Значения зафиксированы здесь, а не взяты из analytics.models: миграция
# не должна меняться вслед за моделью.
GROUP_NAME = "Аналитика"
TRIPS = ("view_trips", "Аналитика: Командировки")
# Права-заготовки под вкладки, которых нет. Удаляются вместе с выдачами:
# новые вкладки добавят свои права, когда появятся.
UNUSED = {
    "view_warehouse_trips": "Аналитика: Склад и командировки",
    "view_service": "Аналитика: Сервис и надёжность",
    "view_park": "Аналитика: Парк и продажи",
}


def _content_type(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="analytics", model="analyticsaccess"
    )
    return content_type


def add_trips_tab(apps, schema_editor):
    """Право «Командировки» (выдаётся группе «Аналитика») и удаление прав-заготовок.

    Идемпотентна: повторный проход, в том числе после отката на новом коде,
    когда `post_migrate` уже пересоздал права по модели, даёт тот же результат.
    """
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    content_type = _content_type(apps)
    Permission.objects.filter(content_type=content_type, codename__in=UNUSED).delete()
    trips, _ = Permission.objects.get_or_create(
        content_type=content_type, codename=TRIPS[0], defaults={"name": TRIPS[1]}
    )
    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is not None:
        group.permissions.add(trips)


def remove_trips_tab(apps, schema_editor):
    """Откат: удаляет право «Командировки» и возвращает права-заготовки.

    Прежние выдачи удалённых прав не восстанавливаются — их больше нет.
    """
    Permission = apps.get_model("auth", "Permission")
    content_type = _content_type(apps)
    Permission.objects.filter(content_type=content_type, codename=TRIPS[0]).delete()
    for codename, name in UNUSED.items():
        Permission.objects.get_or_create(
            content_type=content_type, codename=codename, defaults={"name": name}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0003_rename_to_analytics"),
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
                ),
                "verbose_name": "Доступ к аналитике",
                "verbose_name_plural": "Доступ к аналитике",
            },
        ),
        migrations.RunPython(add_trips_tab, remove_trips_tab),
    ]
