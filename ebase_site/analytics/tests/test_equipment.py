from datetime import date
from decimal import Decimal

from django.test import TestCase

from analytics.filters import EquipmentFilters, Period
from analytics.services.equipment import (
    AGE_UNKNOWN_LABEL,
    OTHER_MANUFACTURERS_LABEL,
    data_gaps,
    installs_by_year,
    park_age,
    park_kpis,
    park_structure,
    top_clients,
    NO_CITY_LABEL,
    NO_CLIENT_LABEL,
    NO_MODEL_NAME_LABEL,
    STATE_AT_CLIENT,
    STATE_NO_INSTALL,
    STATE_REMOVED,
    WORK_BREAKDOWN,
    WORK_PLANNED,
    WORK_UNKNOWN,
    EquipmentSet,
    active_install,
    client_label,
    department_label,
    device_label,
    install_state,
    region_label,
    repair_days,
    work_kind,
)
from analytics.tests.factories import (
    make_city,
    make_client,
    make_department,
    make_device,
    make_equipment,
    make_install,
    make_replacement,
    make_service,
    make_service_type,
)

TODAY = date(2026, 10, 16)
YEAR_2026 = Period(date(2026, 1, 1), date(2026, 12, 31))


class EquipmentRulesTests(TestCase):
    """Набор данных вкладки и базовые правила: состояние, вид работы, подписи."""

    @classmethod
    def setUpTestData(cls):
        cls.client_obj = make_client("Клиника")
        cls.department = make_department("Больница", client=cls.client_obj)
        cls.model = make_equipment("BC-5000")

    def _device(self, source, device):
        return source.device_by_id[device.pk]

    def test_install_states(self):
        at_client = make_device(self.model, "A1")
        make_install(at_client, self.department, date(2020, 1, 1))
        removed = make_device(self.model, "B1")
        make_install(removed, self.department, date(2019, 1, 1), active=False)
        no_install = make_device(self.model, "C1")

        source = EquipmentSet.load()

        self.assertEqual(
            install_state(self._device(source, at_client)), STATE_AT_CLIENT
        )
        self.assertEqual(install_state(self._device(source, removed)), STATE_REMOVED)
        self.assertEqual(
            install_state(self._device(source, no_install)), STATE_NO_INSTALL
        )
        self.assertIsNone(active_install(self._device(source, removed)))

    def test_active_install_prefers_latest_date(self):
        device = make_device(self.model, "A1")
        make_install(device, self.department, date(2020, 1, 1))
        make_install(device, self.department, date(2023, 5, 1))
        make_install(device, self.department, None)
        make_install(device, self.department, date(2024, 1, 1), active=False)

        source = EquipmentSet.load()

        install = active_install(self._device(source, device))
        self.assertEqual(install.install_dt, date(2023, 5, 1))

    def test_work_kind(self):
        device = make_device(self.model, "A1")
        maintenance = make_service(
            device,
            date(2026, 3, 1),
            service_type=make_service_type("Тех. обслуживание", planned=True),
        )
        repair = make_service(
            device, date(2026, 3, 2), service_type=make_service_type("ремонт")
        )
        unknown = make_service(device, date(2026, 3, 3))

        services = {service.pk: service for service in EquipmentSet.load().services}

        self.assertEqual(work_kind(services[maintenance.pk]), WORK_PLANNED)
        self.assertEqual(work_kind(services[repair.pk]), WORK_BREAKDOWN)
        self.assertEqual(work_kind(services[unknown.pk]), WORK_UNKNOWN)

    def test_repair_days_inclusive_and_never_negative(self):
        device = make_device(self.model, "A1")
        same_day = make_service(device, date(2026, 3, 1), date(2026, 3, 1))
        ten_days = make_service(device, date(2026, 3, 1), date(2026, 3, 10))
        reversed_dates = make_service(device, date(2026, 3, 10), date(2026, 3, 1))
        open_repair = make_service(device, date(2026, 3, 1))

        services = {service.pk: service for service in EquipmentSet.load().services}

        self.assertEqual(repair_days(services[same_day.pk]), 1)
        self.assertEqual(repair_days(services[ten_days.pk]), 10)
        self.assertEqual(repair_days(services[reversed_dates.pk]), 1)
        self.assertIsNone(repair_days(services[open_repair.pk]))

    def test_labels_without_names(self):
        nameless = make_equipment(None, None, direction=None, manufacturer=None)
        device = make_device(nameless, "sn1")
        no_city = make_department("Больница без города", city=None)
        no_region = make_department("Поликлиника", city=make_city("Казань", None))
        make_install(device, no_city, date(2020, 1, 1))

        source = EquipmentSet.load()

        self.assertEqual(
            device_label(self._device(source, device)),
            f"{NO_MODEL_NAME_LABEL} [SN1]",
        )
        self.assertEqual(department_label(no_city), "Больница без города")
        self.assertEqual(region_label(no_city), NO_CITY_LABEL)
        self.assertEqual(client_label(no_city), NO_CLIENT_LABEL)
        self.assertEqual(department_label(no_region), "Поликлиника (Казань)")
        self.assertEqual(region_label(no_region), "Казань (регион не указан)")
        self.assertEqual(region_label(self.department), "Татарстан")
        self.assertEqual(client_label(self.department), "Клиника")

    def test_filters_on_devices_services_and_fund(self):
        other = make_equipment("CL-900", direction="Биохимия", manufacturer="Sysmex")
        ours = make_device(self.model, "A1", ours=True)
        theirs = make_device(other, "B1", ours=False)
        ours_repair = make_service(ours, date(2026, 3, 1))
        theirs_repair = make_service(theirs, date(2026, 3, 2))
        spare_hem = make_replacement(self.model, "R1")
        spare_bio = make_replacement(other, "R2")
        hematology = self.model.med_direction
        sysmex = other.manufacturer

        source = EquipmentSet.load()

        def pks(items):
            return {item.pk for item in items}

        everything = EquipmentFilters()
        self.assertEqual(pks(source.devices_of(everything)), {ours.pk, theirs.pk})
        self.assertEqual(
            pks(source.devices_of(EquipmentFilters(direction=hematology))), {ours.pk}
        )
        self.assertEqual(
            pks(source.devices_of(EquipmentFilters(manufacturer=sysmex))),
            {theirs.pk},
        )
        self.assertEqual(
            pks(source.services_of(EquipmentFilters(supply="ours"))),
            {ours_repair.pk},
        )
        self.assertEqual(
            pks(source.services_of(EquipmentFilters(supply="others"))),
            {theirs_repair.pk},
        )
        # «Поставка» на подменный фонд не действует, направление — действует
        self.assertEqual(
            pks(source.replacements_of(EquipmentFilters(supply="ours"))),
            {spare_hem.pk, spare_bio.pk},
        )
        self.assertEqual(
            pks(source.replacements_of(EquipmentFilters(direction=hematology))),
            {spare_hem.pk},
        )

    def test_services_in_period_bounds(self):
        device = make_device(self.model, "A1")
        first = make_service(device, date(2026, 1, 1))
        last = make_service(device, date(2026, 12, 31))
        make_service(device, date(2025, 12, 31))

        source = EquipmentSet.load()

        self.assertEqual(
            {
                service.pk
                for service in source.services_in(YEAR_2026, EquipmentFilters())
            },
            {first.pk, last.pk},
        )

    def test_service_without_device(self):
        orphan = make_service(None, date(2026, 3, 1))

        source = EquipmentSet.load()
        service = next(item for item in source.services if item.pk == orphan.pk)

        self.assertIn(service, source.services_of(EquipmentFilters()))
        self.assertNotIn(service, source.services_of(EquipmentFilters(supply="ours")))
        self.assertNotIn(
            service,
            source.services_of(EquipmentFilters(direction=self.model.med_direction)),
        )
        self.assertIsNone(source.device_of(service))

    def test_issues_of_replacement_in_date_order(self):
        device = make_device(self.model, "A1")
        spare = make_replacement(self.model, "R1")
        later = make_service(device, date(2026, 5, 1), replacement=spare)
        earlier = make_service(device, date(2026, 2, 1), replacement=spare)
        make_service(device, date(2026, 3, 1))

        source = EquipmentSet.load()
        loaded = next(item for item in source.replacements if item.pk == spare.pk)

        self.assertEqual(
            [service.pk for service in source.issues_of(loaded)],
            [earlier.pk, later.pk],
        )

    def test_load_makes_constant_number_of_queries(self):
        for serial in ("A1", "A2", "A3"):
            device = make_device(self.model, serial)
            make_install(device, self.department, date(2020, 1, 1), engineer="Петров")
            make_service(device, date(2026, 3, 1), engineer="Петров")
        make_replacement(self.model, "R1")

        with self.assertNumQueries(4):
            source = EquipmentSet.load()
            # подписи и фильтры не делают запросов
            for device in source.devices:
                device_label(device)
                install = active_install(device)
                department_label(install.department)
                region_label(install.department)
                client_label(install.department)
            for service in source.services:
                work_kind(service)
                source.device_of(service)


class ParkTests(TestCase):
    """Блок «Парк оборудования» (на сегодня)."""

    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_client("Клиника")
        cls.department = make_department("Больница", client=cls.clinic)
        cls.model = make_equipment("BC-5000")
        # A — у клиента с 2020-03-01, нами; B — у клиента без даты, не нами;
        # C — монтаж снят; D — без монтажа
        cls.a = make_device(cls.model, "A", our_service=True, status="работает")
        make_install(cls.a, cls.department, date(2020, 3, 1), engineer="Петров")
        cls.b = make_device(cls.model, "B", ours=False)
        make_install(cls.b, cls.department, None)
        cls.c = make_device(cls.model, "C")
        make_install(cls.c, cls.department, date(2019, 5, 1), active=False)
        cls.d = make_device(cls.model, "D")

    def _source(self):
        return EquipmentSet.load()

    def test_park_kpis(self):
        kpis = park_kpis(TODAY, EquipmentFilters(), source=self._source())

        self.assertEqual(kpis["total"], 4)
        self.assertEqual(kpis["ours"], 3)
        self.assertEqual(kpis["others"], 1)
        self.assertEqual(kpis["at_client"], 2)
        self.assertEqual(kpis["no_install"], 1)
        self.assertEqual(kpis["removed"], 1)
        self.assertEqual(kpis["clients"], 1)
        self.assertEqual(kpis["avg_age"], Decimal("6.6"))
        self.assertEqual(kpis["our_service"], 1)

    def test_park_kpis_supply_filter(self):
        kpis = park_kpis(
            TODAY, EquipmentFilters(supply="others"), source=self._source()
        )

        self.assertEqual(kpis["total"], 1)
        self.assertEqual(kpis["at_client"], 1)
        self.assertIsNone(kpis["avg_age"])

    def test_installs_by_year_fills_gaps_and_accumulates(self):
        e = make_device(self.model, "E", ours=False)
        make_install(e, self.department, date(2022, 6, 1))

        result = installs_by_year(EquipmentFilters(), source=self._source())

        self.assertEqual(result["years"], [2019, 2020, 2021, 2022])
        self.assertEqual(result["ours"], [1, 1, 0, 0])
        self.assertEqual(result["others"], [0, 0, 0, 1])
        self.assertEqual(result["cumulative"], [1, 2, 2, 3])
        self.assertEqual(result["no_date"], 1)

    def test_park_structure_splits_supply(self):
        structure = park_structure(EquipmentFilters(), source=self._source())

        directions = structure["directions"]
        self.assertEqual(len(directions), 1)
        self.assertEqual(directions[0]["label"], "Гематология")
        self.assertEqual(directions[0]["key"], self.model.med_direction_id)
        self.assertEqual((directions[0]["ours"], directions[0]["others"]), (1, 1))
        self.assertEqual(set(directions[0]["ids"]), {str(self.a.pk), str(self.b.pk)})
        statuses = {row["label"]: row for row in structure["statuses"]}
        self.assertEqual(statuses["работает"]["key"], "работает")
        self.assertIsNone(statuses["Статус не указан"]["key"])
        self.assertEqual([row["label"] for row in structure["regions"]], ["Татарстан"])

    def test_park_structure_groups_rest_of_manufacturers(self):
        for number in range(11):
            model = make_equipment(
                f"Модель {number}", manufacturer=f"Завод {number:02}"
            )
            device = make_device(model, f"M{number}")
            make_install(device, self.department, date(2021, 1, 1))
        no_region = make_department("Поликлиника", city=make_city("Казань", None))
        device = make_device(self.model, "F")
        make_install(device, no_region, date(2021, 1, 1))

        structure = park_structure(EquipmentFilters(), source=self._source())

        manufacturers = structure["manufacturers"]
        self.assertEqual(len(manufacturers), 11)
        self.assertEqual(manufacturers[0]["label"], "Mindray")
        self.assertEqual(manufacturers[0]["total"], 3)
        self.assertEqual(manufacturers[-1]["label"], OTHER_MANUFACTURERS_LABEL)
        self.assertIsNone(manufacturers[-1]["key"])
        self.assertEqual(manufacturers[-1]["total"], 2)
        self.assertEqual(sum(row["total"] for row in manufacturers), 14)
        regions = {row["label"]: row["total"] for row in structure["regions"]}
        self.assertEqual(regions["Казань (регион не указан)"], 1)

    def test_park_age_buckets(self):
        biochemistry = make_equipment("CL-900", direction="Биохимия")
        for serial, install_dt in [
            ("G1", date(2026, 4, 16)),  # полгода
            ("G2", date(2024, 10, 16)),  # 2 года
            ("G3", date(2022, 10, 16)),  # 4 года
            ("G4", date(2019, 10, 16)),  # 7 лет
            ("G5", date(2014, 10, 16)),  # 12 лет
            ("G6", None),
        ]:
            make_install(make_device(biochemistry, serial), self.department, install_dt)

        rows = park_age(
            TODAY,
            EquipmentFilters(direction=biochemistry.med_direction),
            source=self._source(),
        )

        self.assertEqual(
            [row["label"] for row in rows],
            ["<1", "1–3", "3–5", "5–10", "10+ лет", AGE_UNKNOWN_LABEL],
        )
        self.assertEqual([row["count"] for row in rows], [1, 1, 1, 1, 1, 1])

    def test_top_clients(self):
        other_client = make_client("Лаборатория")
        lab = make_department("Лаборатория 1", client=other_client)
        second_model = make_equipment("CL-900", direction="Биохимия")
        for serial in ("L1", "L2"):
            make_install(make_device(second_model, serial), lab, date(2021, 1, 1))
        make_install(make_device(self.model, "L3", ours=False), lab, date(2021, 1, 1))

        rows = top_clients(EquipmentFilters(), source=self._source())

        self.assertEqual(
            [(row["name"], row["devices"], row["ours"], row["models"]) for row in rows],
            [("Лаборатория", 3, 2, 2), ("Клиника", 2, 1, 1)],
        )
        self.assertEqual(len(rows[0]["ids"]), 3)

    def test_data_gaps(self):
        make_service(self.a, date(2025, 1, 10))  # без вида и без окончания, старый
        make_service(self.a, date(2026, 9, 1), service_type=make_service_type("ремонт"))

        rows = {
            row["key"]: row
            for row in data_gaps(TODAY, EquipmentFilters(), source=self._source())
        }

        self.assertEqual(
            list(rows),
            [
                "no_install",
                "no_install_date",
                "no_status",
                "no_engineer",
                "no_service_type",
                "old_open",
            ],
        )
        self.assertEqual(rows["no_install"]["count"], 1)
        self.assertEqual(rows["no_install"]["ids"], [str(self.d.pk)])
        self.assertEqual(rows["no_install_date"]["count"], 1)
        self.assertEqual(rows["no_status"]["count"], 3)
        self.assertEqual(rows["no_engineer"]["count"], 1)
        self.assertEqual(rows["no_service_type"]["count"], 1)
        self.assertEqual(rows["old_open"]["count"], 1)
        self.assertEqual(rows["no_install"]["target"], "accounting")
        self.assertEqual(rows["old_open"]["target"], "service")
