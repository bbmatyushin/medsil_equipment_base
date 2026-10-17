import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

User = get_user_model()


def _permissions_before_0004():
    """Права как до миграции 0004: view_warehouse_trips вместо view_warehouse, без view_trips.

    В тестах миграции выключены и права создаются по текущей модели, поэтому
    тестам миграций 0002–0004 прежнее состояние нужно восстановить вручную.
    """
    analytics = Permission.objects.filter(content_type__app_label="analytics")
    analytics.filter(codename="view_warehouse").update(
        codename="view_warehouse_trips", name="Аналитика: Склад и командировки"
    )
    analytics.filter(codename="view_trips").delete()


class StatisticsGroupMigrationTests(TestCase):
    def test_permissions_exist(self):
        codenames = set(
            Permission.objects.filter(content_type__app_label="analytics").values_list(
                "codename", flat=True
            )
        )
        self.assertEqual(
            codenames,
            {
                "view_finance",
                "view_trips",
                "view_warehouse",
                "view_service",
                "view_park",
            },
        )

    def test_group_gets_all_permissions_and_active_staff_only(self):
        _permissions_before_0004()
        staff = User.objects.create_user("staff", password="p", is_staff=True)
        User.objects.create_user(
            "inactive", password="p", is_staff=True, is_active=False
        )
        User.objects.create_user("plain", password="p")
        migration = importlib.import_module(
            "analytics.migrations.0002_statistics_group"
        )
        migration.create_statistics_group(django_apps, None)
        migration.create_statistics_group(django_apps, None)  # идемпотентность
        group = Group.objects.get(name="Статистика")
        self.assertEqual(group.permissions.count(), 4)
        self.assertEqual(list(group.user_set.all()), [staff])
        self.assertTrue(
            User.objects.get(pk=staff.pk).has_perm("analytics.view_finance")
        )

    def test_existing_group_keeps_its_permissions(self):
        _permissions_before_0004()
        extra = Permission.objects.filter(content_type__app_label="auth").first()
        group = Group.objects.create(name="Статистика")
        group.permissions.add(extra)
        migration = importlib.import_module(
            "analytics.migrations.0002_statistics_group"
        )

        migration.create_statistics_group(django_apps, None)

        # права, выданные группе вручную, не стираются; четыре права вкладок добавлены
        self.assertEqual(group.permissions.count(), 5)
        self.assertTrue(group.permissions.filter(pk=extra.pk).exists())


class RenameToAnalyticsMigrationTests(TestCase):
    """Миграция 0003: «Статистика» → «Аналитика», «Деньги» → «Финансы»."""

    OLD_NAMES = {
        "view_finance": "Статистика: Деньги",
        "view_warehouse_trips": "Статистика: Склад и командировки",
        "view_service": "Статистика: Сервис и надёжность",
        "view_park": "Статистика: Парк и продажи",
    }
    NEW_NAMES = {
        "view_finance": "Аналитика: Финансы",
        "view_warehouse_trips": "Аналитика: Склад и командировки",
        "view_service": "Аналитика: Сервис и надёжность",
        "view_park": "Аналитика: Парк и продажи",
    }

    def setUp(self):
        self.migration = importlib.import_module(
            "analytics.migrations.0003_rename_to_analytics"
        )
        # состояние после 0002: старые названия прав и группа «Статистика»
        _permissions_before_0004()
        for codename, name in self.OLD_NAMES.items():
            Permission.objects.filter(
                content_type__app_label="analytics", codename=codename
            ).update(name=name)

    def _names(self):
        return dict(
            Permission.objects.filter(content_type__app_label="analytics").values_list(
                "codename", "name"
            )
        )

    def test_renames_permissions_and_group(self):
        group = Group.objects.create(name="Статистика")
        staff = User.objects.create_user("staff", password="p", is_staff=True)
        group.user_set.add(staff)

        self.migration.rename_to_analytics(django_apps, None)

        self.assertEqual(self._names(), self.NEW_NAMES)
        group.refresh_from_db()
        self.assertEqual(group.name, "Аналитика")
        self.assertEqual(list(group.user_set.all()), [staff])

    def test_existing_analytics_group_is_not_touched(self):
        Group.objects.create(name="Аналитика")
        Group.objects.create(name="Статистика")

        self.migration.rename_to_analytics(django_apps, None)

        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)),
            ["Аналитика", "Статистика"],
        )

    def test_reverse_restores_old_names(self):
        Group.objects.create(name="Статистика")
        self.migration.rename_to_analytics(django_apps, None)

        self.migration.rename_to_statistics(django_apps, None)

        self.assertEqual(self._names(), self.OLD_NAMES)
        self.assertTrue(Group.objects.filter(name="Статистика").exists())


class TripsTabMigrationTests(TestCase):
    """Миграция 0004: право view_trips и переименование права склада."""

    def setUp(self):
        self.migration = importlib.import_module("analytics.migrations.0004_trips_tab")
        _permissions_before_0004()

    @staticmethod
    def _perm(codename):
        return Permission.objects.get(
            content_type__app_label="analytics", codename=codename
        )

    def test_renames_warehouse_permission_and_keeps_grants(self):
        old = self._perm("view_warehouse_trips")
        user = User.objects.create_user("staff", password="p", is_staff=True)
        user.user_permissions.add(old)
        group = Group.objects.create(name="Аналитика")
        group.permissions.add(old)

        self.migration.add_trips_tab(django_apps, None)

        renamed = self._perm("view_warehouse")
        self.assertEqual(renamed.pk, old.pk)
        self.assertEqual(renamed.name, "Аналитика: Склад")
        self.assertTrue(group.permissions.filter(pk=old.pk).exists())
        self.assertTrue(
            User.objects.get(pk=user.pk).has_perm("analytics.view_warehouse")
        )

    def test_creates_trips_permission_and_grants_group(self):
        group = Group.objects.create(name="Аналитика")
        user = User.objects.create_user("staff", password="p", is_staff=True)
        group.user_set.add(user)

        self.migration.add_trips_tab(django_apps, None)

        trips = self._perm("view_trips")
        self.assertEqual(trips.name, "Аналитика: Командировки")
        self.assertTrue(group.permissions.filter(pk=trips.pk).exists())
        self.assertTrue(User.objects.get(pk=user.pk).has_perm("analytics.view_trips"))

    def test_without_group_creates_permission_only(self):
        self.migration.add_trips_tab(django_apps, None)

        self.assertTrue(
            Permission.objects.filter(
                content_type__app_label="analytics", codename="view_trips"
            ).exists()
        )
        self.assertEqual(Group.objects.count(), 0)

    def test_is_idempotent(self):
        Group.objects.create(name="Аналитика")

        self.migration.add_trips_tab(django_apps, None)
        self.migration.add_trips_tab(django_apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type__app_label="analytics", codename="view_trips"
            ).count(),
            1,
        )
        self.assertEqual(self._perm("view_warehouse").name, "Аналитика: Склад")

    def test_reverse_restores_previous_state(self):
        self.migration.add_trips_tab(django_apps, None)

        self.migration.remove_trips_tab(django_apps, None)

        restored = self._perm("view_warehouse_trips")
        self.assertEqual(restored.name, "Аналитика: Склад и командировки")
        codenames = set(
            Permission.objects.filter(content_type__app_label="analytics").values_list(
                "codename", flat=True
            )
        )
        self.assertNotIn("view_trips", codenames)
        self.assertNotIn("view_warehouse", codenames)
