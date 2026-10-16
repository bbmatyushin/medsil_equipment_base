import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

User = get_user_model()


class StatisticsGroupMigrationTests(TestCase):
    def test_permissions_exist(self):
        codenames = set(
            Permission.objects.filter(content_type__app_label="analytics").values_list(
                "codename", flat=True
            )
        )
        self.assertEqual(
            codenames,
            {"view_finance", "view_warehouse_trips", "view_service", "view_park"},
        )

    def test_group_gets_all_permissions_and_active_staff_only(self):
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
