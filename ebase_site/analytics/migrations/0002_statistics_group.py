from django.conf import settings
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Значения зафиксированы в миграции намеренно: история миграций не должна
# меняться вслед за правками констант в models.py.
GROUP_NAME = "Статистика"
PERMISSION_CODENAMES = (
    "view_finance",
    "view_warehouse_trips",
    "view_service",
    "view_park",
)


def create_statistics_group(apps, schema_editor):
    """Создаёт права вкладок, группу «Статистика» и добавляет в неё активный персонал.

    Права создаются здесь явно: сигнал post_migrate срабатывает только после
    всех миграций, а группе права нужны уже сейчас. Функция идемпотентна.
    """
    app_config = apps.get_app_config("analytics")
    # В историческом реестре у заглушки приложения нет models_module (или он
    # пуст), и create_permissions молча ничего не делает. В глобальном реестре
    # значение уже заполнено, его не трогаем.
    had_attr = hasattr(app_config, "models_module")
    original_models_module = getattr(app_config, "models_module", None)
    if not original_models_module:
        app_config.models_module = True
    try:
        create_permissions(app_config, apps=apps, verbosity=0)
    finally:
        if had_attr:
            app_config.models_module = original_models_module
        else:
            del app_config.models_module

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    permissions = Permission.objects.filter(
        content_type__app_label="analytics", codename__in=PERMISSION_CODENAMES
    )
    # add, а не set: права, выданные существующей группе вручную, не стираем
    group.permissions.add(*permissions)
    group.user_set.add(*User.objects.filter(is_staff=True, is_active=True))


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0001_initial"),
        ("users", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_statistics_group, migrations.RunPython.noop),
    ]
