import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from directory.models import ServiceType

User = get_user_model()


def _maintenance_migration():
    return importlib.import_module(
        "directory.migrations.0004_servicetype_is_planned_maintenance"
    )


class PlannedMaintenanceFlagTests(TestCase):
    """Флаг «Плановое ТО» у вида работ и миграция, ставящая его ТО."""

    def test_default_is_false(self):
        self.assertFalse(
            ServiceType.objects.create(name="ремонт").is_planned_maintenance
        )

    def test_migration_marks_maintenance_only(self):
        maintenance = ServiceType.objects.create(name="Тех. обслуживание")
        repair = ServiceType.objects.create(name="ремонт")
        migration = _maintenance_migration()

        migration.mark_planned_maintenance(django_apps, None)
        migration.mark_planned_maintenance(django_apps, None)  # идемпотентность

        maintenance.refresh_from_db()
        repair.refresh_from_db()
        self.assertTrue(maintenance.is_planned_maintenance)
        self.assertFalse(repair.is_planned_maintenance)

    def test_migration_without_maintenance_type_does_nothing(self):
        ServiceType.objects.create(name="ремонт")

        _maintenance_migration().mark_planned_maintenance(django_apps, None)

        self.assertFalse(
            ServiceType.objects.filter(is_planned_maintenance=True).exists()
        )


class ServiceTypeAdminTests(TestCase):
    """Карточка и список видов работ: флаг «Плановое ТО» с пояснением."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "super", "super@example.com", "pass"
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_change_form_explains_flag(self):
        service_type = ServiceType.objects.create(name="Тех. обслуживание")

        response = self.client.get(
            reverse("admin:directory_servicetype_change", args=[service_type.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Плановое ТО")
        self.assertContains(response, "не входят в надёжность моделей")

    def test_changelist_saves_flag_inline(self):
        service_type = ServiceType.objects.create(name="Тех. обслуживание")

        response = self.client.post(
            reverse("admin:directory_servicetype_changelist"),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-0-id": str(service_type.pk),
                "form-0-is_planned_maintenance": "on",
                "_save": "Сохранить",
            },
        )

        self.assertEqual(response.status_code, 302)
        service_type.refresh_from_db()
        self.assertTrue(service_type.is_planned_maintenance)
