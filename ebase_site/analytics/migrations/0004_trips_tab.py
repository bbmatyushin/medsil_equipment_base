from django.db import migrations

# Значения зафиксированы здесь, а не взяты из analytics.models: миграция
# не должна меняться вслед за моделью.
GROUP_NAME = "Аналитика"
OLD_WAREHOUSE = ("view_warehouse_trips", "Аналитика: Склад и командировки")
NEW_WAREHOUSE = ("view_warehouse", "Аналитика: Склад")
TRIPS = ("view_trips", "Аналитика: Командировки")


def _analytics_permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    return Permission.objects.filter(
        content_type__app_label="analytics", content_type__model="analyticsaccess"
    )


def _rename(apps, source, target):
    """Переименовывает право (та же строка — выдачи сохраняются).

    Если право с новым codename уже есть, ничего не делает: права не сливаются.
    """
    permissions = _analytics_permissions(apps)
    if permissions.filter(codename=target[0]).exists():
        return
    permissions.filter(codename=source[0]).update(codename=target[0], name=target[1])


def add_trips_tab(apps, schema_editor):
    """Право склада без командировок, право «Командировки» и выдача его группе.

    Переименование идёт до создания прав: иначе право `view_warehouse` с тем же
    ContentType появилось бы второй строкой. Функция идемпотентна.
    """
    _rename(apps, OLD_WAREHOUSE, NEW_WAREHOUSE)

    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="analytics", model="analyticsaccess"
    )
    trips, _ = Permission.objects.get_or_create(
        content_type=content_type, codename=TRIPS[0], defaults={"name": TRIPS[1]}
    )
    group = Group.objects.filter(name=GROUP_NAME).first()
    if group is not None:
        group.permissions.add(trips)


def remove_trips_tab(apps, schema_editor):
    """Откат: удаляет право «Командировки» и возвращает прежнее право склада."""
    _analytics_permissions(apps).filter(codename=TRIPS[0]).delete()
    _rename(apps, NEW_WAREHOUSE, OLD_WAREHOUSE)


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
                    ("view_warehouse", "Аналитика: Склад"),
                    ("view_service", "Аналитика: Сервис и надёжность"),
                    ("view_park", "Аналитика: Парк и продажи"),
                ),
                "verbose_name": "Доступ к аналитике",
                "verbose_name_plural": "Доступ к аналитике",
            },
        ),
        migrations.RunPython(add_trips_tab, remove_trips_tab),
    ]
