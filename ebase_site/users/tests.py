from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UsersAdminMenuTests(TestCase):
    """Пользователи выводятся в блоке «Пользователи и группы» вместе с группами."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "super", "super@example.com", "pass"
        )
        cls.users_staff = User.objects.create_user(
            "users_staff", password="pass", is_staff=True
        )
        cls.users_staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="users", codename="view_companyuser"
            )
        )

    @staticmethod
    def _models(app):
        return [(model["name"], model["admin_url"]) for model in app["models"]]

    def test_sidebar_has_one_block_with_groups_and_users(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        labels = [app["app_label"] for app in response.context["available_apps"]]
        self.assertNotIn("users", labels)
        app = next(
            app
            for app in response.context["available_apps"]
            if app["app_label"] == "auth"
        )
        self.assertEqual(app["name"], "Пользователи и группы")
        self.assertEqual(
            self._models(app),
            [
                ("Группы", reverse("admin:auth_group_changelist")),
                ("Пользователи", reverse("admin:users_companyuser_changelist")),
            ],
        )
        # тот же блок — в списке на главной странице
        self.assertIn(app, response.context["app_list"])
        self.assertNotContains(response, "_Пользователи")

    def test_app_pages_show_merged_block(self):
        self.client.force_login(self.superuser)
        for app_label in ("users", "auth"):
            with self.subTest(app_label=app_label):
                response = self.client.get(
                    reverse("admin:app_list", kwargs={"app_label": app_label})
                )
                self.assertEqual(response.status_code, 200)
                [app] = response.context["app_list"]
                self.assertEqual(app["name"], "Пользователи и группы")
                self.assertEqual(
                    [name for name, _ in self._models(app)],
                    ["Группы", "Пользователи"],
                )

    def test_users_changelist_breadcrumbs(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:users_companyuser_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<a href="%s">Пользователи и группы</a>'
            % reverse("admin:app_list", kwargs={"app_label": "users"}),
        )

    def test_staff_without_group_permissions_sees_users(self):
        self.client.force_login(self.users_staff)
        response = self.client.get(reverse("admin:index"))
        [app] = [
            app
            for app in response.context["available_apps"]
            if app["app_label"] in ("users", "auth")
        ]
        self.assertEqual(app["name"], "Пользователи и группы")
        self.assertEqual(
            self._models(app),
            [("Пользователи", reverse("admin:users_companyuser_changelist"))],
        )
