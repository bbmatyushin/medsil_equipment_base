from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from analytics.filters import EquipmentFilters, Period
from analytics.services.equipment import (
    effective_days,
    models_summary,
    problem_devices,
    reliability,
    repeat_repairs,
    NO_ENGINEER_LABEL,
    NO_SERVICE_TYPE_LABEL,
    OTHER_SERVICE_TYPES_LABEL,
    duration_stats,
    engineer_load,
    open_repairs,
    planned_by_month,
    repairs_kpis,
    works_by_month,
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


class RepairsTests(TestCase):
    """Блок «Ремонты» (за период)."""

    @classmethod
    def setUpTestData(cls):
        cls.department = make_department("Больница", client=make_client("Клиника"))
        cls.model = make_equipment("BC-5000")
        cls.ours = make_device(cls.model, "A1")
        make_install(cls.ours, cls.department, date(2020, 1, 1))
        cls.theirs = make_device(cls.model, "B1", ours=False)
        make_install(cls.theirs, cls.department, date(2020, 1, 1))
        cls.maintenance = make_service_type("Тех. обслуживание", planned=True)
        cls.repair = make_service_type("ремонт")

    def _source(self):
        return EquipmentSet.load()

    def test_repairs_kpis_counts_and_deltas(self):
        spare = make_replacement(self.model, "R1")
        for day in (1, 2):
            make_service(
                self.ours,
                date(2026, 3, day),
                date(2026, 3, day),
                service_type=self.maintenance,
            )
        make_service(
            self.ours, date(2026, 4, 1), date(2026, 4, 3), service_type=self.repair
        )
        make_service(
            self.ours,
            date(2026, 5, 1),
            date(2026, 5, 5),
            service_type=self.repair,
            replacement=spare,
        )
        make_service(self.theirs, date(2026, 6, 1), service_type=self.repair)
        make_service(self.ours, date(2026, 7, 1), date(2026, 7, 1))  # без вида
        make_service(
            self.ours, date(2025, 3, 1), date(2025, 3, 1), service_type=self.maintenance
        )
        make_service(
            self.ours, date(2025, 4, 1), date(2025, 4, 2), service_type=self.repair
        )

        kpis = repairs_kpis(YEAR_2026, TODAY, EquipmentFilters(), source=self._source())

        current = kpis["current"]
        self.assertEqual(current["total"], 6)
        self.assertEqual(current["planned"], 2)
        self.assertEqual(current["breakdowns"], 3)
        self.assertEqual(current["replacement_share"], Decimal("33.3"))
        self.assertEqual(current["median_days"], Decimal("4.0"))
        self.assertEqual(kpis["previous"]["total"], 2)
        self.assertEqual(kpis["delta_pct"]["total"], Decimal("200.0"))
        self.assertEqual(kpis["delta_pct"]["planned"], Decimal("100.0"))
        # доля с подменой — разность в процентных пунктах: 33,3 − 0,0
        self.assertEqual(kpis["delta_pct"]["replacement_share"], Decimal("33.3"))
        self.assertEqual(kpis["unknown_type"], 1)

    def test_median_days_only_closed_breakdowns(self):
        for beg, end in [
            (date(2026, 3, 1), date(2026, 3, 3)),
            (date(2026, 4, 1), date(2026, 4, 5)),
            (date(2026, 5, 1), date(2026, 5, 10)),
            (date(2026, 6, 1), None),
        ]:
            make_service(self.ours, beg, end, service_type=self.repair)
        make_service(
            self.ours,
            date(2026, 7, 1),
            date(2026, 7, 20),
            service_type=self.maintenance,
        )

        kpis = repairs_kpis(YEAR_2026, TODAY, EquipmentFilters(), source=self._source())

        self.assertEqual(kpis["current"]["median_days"], Decimal("5.0"))
        self.assertIsNone(kpis["previous"]["median_days"])
        self.assertIsNone(kpis["previous"]["replacement_share"])

    def test_open_repairs_window_and_future(self):
        recent = make_service(self.ours, date(2026, 10, 1), service_type=self.repair)
        edge = make_service(self.theirs, date(2025, 10, 16))
        old = make_service(self.ours, date(2025, 10, 15))
        make_service(self.ours, date(2026, 11, 1))  # начнётся позже
        make_service(self.ours, date(2026, 9, 1), date(2026, 9, 2))  # закрыт

        source = self._source()
        result = open_repairs(TODAY, EquipmentFilters(), source=source)

        self.assertEqual([row["id"] for row in result["rows"]], [edge.pk, recent.pk])
        self.assertEqual([row["days"] for row in result["rows"]], [366, 16])
        self.assertEqual(result["rows"][1]["service_type"], "ремонт")
        self.assertEqual(result["rows"][0]["service_type"], NO_SERVICE_TYPE_LABEL)
        self.assertEqual(result["rows"][1]["device"], "BC-5000 [A1]")
        self.assertEqual(result["rows"][1]["department"], "Больница (Казань)")
        self.assertEqual(result["old_count"], 1)
        self.assertEqual(result["old_ids"], [str(old.pk)])
        self.assertEqual(result["old_before"], date(2025, 10, 16))
        kpis = repairs_kpis(YEAR_2026, TODAY, EquipmentFilters(), source=source)
        self.assertEqual(kpis["open_now"], 2)

    def test_works_by_month_groups_extra_types(self):
        counts = {"T1": 6, "T2": 5, "T3": 4, "T4": 3, None: 2, "T6": 1, "T7": 1}
        for name, count in counts.items():
            service_type = make_service_type(name) if name else None
            for _ in range(count):
                make_service(self.ours, date(2026, 3, 5), service_type=service_type)

        result = works_by_month(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(len(result["months"]), 12)
        self.assertEqual(
            [series["label"] for series in result["series"]],
            ["T1", "T2", "T3", "T4", NO_SERVICE_TYPE_LABEL, OTHER_SERVICE_TYPES_LABEL],
        )
        self.assertEqual(result["series"][0]["data"][2], 6)
        self.assertEqual(result["series"][-1]["data"][2], 2)
        self.assertEqual(sum(result["series"][-1]["data"]), 2)

    def test_planned_by_month_splits_supply_and_previous_year(self):
        make_service(self.ours, date(2026, 3, 5), service_type=self.maintenance)
        make_service(self.theirs, date(2026, 3, 20), service_type=self.maintenance)
        make_service(None, date(2026, 4, 1), service_type=self.maintenance)
        make_service(self.ours, date(2025, 3, 10), service_type=self.maintenance)
        make_service(self.ours, date(2026, 3, 7), service_type=self.repair)

        result = planned_by_month(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(result["ours"][2], 1)
        self.assertEqual(result["others"][2], 1)
        self.assertEqual(result["no_device"][3], 1)
        self.assertEqual(result["previous"][2], 1)
        self.assertEqual(sum(result["ours"]) + sum(result["others"]), 2)

    def test_duration_buckets_and_by_type(self):
        for days in (1, 3, 4, 14, 15, 31):
            beg = date(2026, 3, 1)
            make_service(
                self.ours, beg, beg + timedelta(days=days - 1), service_type=self.repair
            )
        for days in (2, 4):
            beg = date(2026, 5, 1)
            make_service(
                self.ours,
                beg,
                beg + timedelta(days=days - 1),
                service_type=self.maintenance,
            )
        make_service(self.ours, date(2026, 6, 1), service_type=self.repair)

        result = duration_stats(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(
            [row["label"] for row in result["buckets"]],
            ["1–3", "4–7", "8–14", "15–30", "31+"],
        )
        self.assertEqual([row["count"] for row in result["buckets"]], [2, 1, 1, 1, 1])
        self.assertEqual(
            [
                (row["label"], row["count"], row["median"], row["max"])
                for row in result["by_type"]
            ],
            [
                ("ремонт", 6, Decimal("9.0"), 31),
                ("Тех. обслуживание", 2, Decimal("3.0"), 4),
            ],
        )
        self.assertEqual(result["open"], 1)

    def test_engineer_load(self):
        for day, name in [(2, "Петров"), (3, "Петров"), (4, "Сидоров")]:
            make_service(self.ours, date(2026, 3, day), engineer=name)
        make_service(self.ours, date(2026, 5, 1), engineer="Петров")
        make_service(self.ours, date(2026, 4, 1))

        result = engineer_load(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(
            [(row["name"], row["total"]) for row in result["rows"]],
            [("Петров", 3), (NO_ENGINEER_LABEL, 1), ("Сидоров", 1)],
        )
        self.assertEqual(result["rows"][0]["days"][2], 2)
        self.assertEqual(result["rows"][0]["days"][4], 1)
        self.assertEqual(result["max"], 2)


class ReliabilityTests(TestCase):
    """Блок «Надёжность моделей»: только поломки (вид работ без «Плановое ТО»)."""

    @classmethod
    def setUpTestData(cls):
        cls.department = make_department("Больница", client=make_client("Клиника"))
        cls.model = make_equipment("BC-5000")
        cls.maintenance = make_service_type("Тех. обслуживание", planned=True)
        cls.repair = make_service_type("ремонт")

    def _source(self):
        return EquipmentSet.load()

    def _installed(self, model, serial, **kwargs):
        device = make_device(model, serial, **kwargs)
        make_install(device, self.department, date(2020, 1, 1))
        return device

    def _breakdown(self, device, beg, end=None):
        return make_service(device, beg, end, service_type=self.repair)

    def test_effective_days(self):
        self.assertEqual(effective_days(YEAR_2026, TODAY), 289)
        self.assertEqual(
            effective_days(Period(date(2027, 1, 1), date(2027, 12, 31)), TODAY), 0
        )
        self.assertEqual(
            effective_days(Period(date(2025, 1, 1), date(2025, 12, 31)), TODAY), 365
        )

    def test_reliability_rate_and_min_units(self):
        devices = [self._installed(self.model, f"M{n}") for n in range(4)]
        self._breakdown(devices[0], date(2026, 3, 1), date(2026, 3, 5))
        self._breakdown(devices[1], date(2026, 5, 1))
        self._breakdown(devices[2], date(2026, 11, 1))  # позже сегодня
        make_service(devices[3], date(2026, 4, 1), service_type=self.maintenance)
        make_service(devices[3], date(2026, 4, 2))  # без вида работ
        small = make_equipment("CL-900", direction="Биохимия")
        small_devices = [self._installed(small, f"S{n}") for n in range(2)]
        self._breakdown(small_devices[0], date(2026, 3, 1))

        rows = reliability(YEAR_2026, TODAY, EquipmentFilters(), source=self._source())

        self.assertEqual([row["label"] for row in rows], ["BC-5000"])
        row = rows[0]
        self.assertEqual(row["units"], 4)
        self.assertEqual(row["breakdowns"], 2)
        self.assertEqual(
            row["per_unit_year"],
            (Decimal(2) / 4 * 365 / 289).quantize(Decimal("0.01")),
        )
        self.assertEqual(len(row["service_ids"]), 2)

    def test_reliability_future_period_is_empty(self):
        devices = [self._installed(self.model, f"M{n}") for n in range(3)]
        self._breakdown(devices[0], date(2027, 3, 1))

        rows = reliability(
            Period(date(2027, 1, 1), date(2027, 12, 31)),
            TODAY,
            EquipmentFilters(),
            source=self._source(),
        )

        self.assertEqual(rows, [])

    def test_repeat_repairs_boundaries(self):
        for serial, next_beg in [
            ("X", date(2026, 3, 31)),  # 30 дней
            ("Y", date(2026, 5, 30)),  # 90 дней
            ("Z", date(2026, 5, 31)),  # 91 день — не повтор
        ]:
            device = self._installed(self.model, serial)
            self._breakdown(device, date(2026, 2, 20), date(2026, 3, 1))
            self._breakdown(device, next_beg)

        result = repeat_repairs(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(result["counts"], {30: 1, 90: 2})
        self.assertEqual([row["gap_days"] for row in result["rows"]], [30, 90])
        self.assertEqual(result["rows"][0]["device"], "BC-5000 [X]")
        self.assertEqual(result["rows"][0]["previous_date"], date(2026, 3, 1))
        self.assertEqual(result["rows"][0]["current_date"], date(2026, 3, 31))

    def test_repeat_repairs_previous_rules(self):
        w = self._installed(self.model, "W")
        self._breakdown(w, date(2025, 12, 20))  # без окончания, до периода
        self._breakdown(w, date(2026, 1, 10))
        v = self._installed(self.model, "V")
        first = self._breakdown(v, date(2026, 4, 1), date(2026, 4, 5))
        make_service(
            v, date(2026, 4, 20), date(2026, 4, 20), service_type=self.maintenance
        )
        second = self._breakdown(v, date(2026, 5, 1))

        rows = {
            row["device"]: row
            for row in repeat_repairs(
                YEAR_2026, EquipmentFilters(), source=self._source()
            )["rows"]
        }

        self.assertEqual(rows["BC-5000 [W]"]["previous_date"], date(2025, 12, 20))
        self.assertEqual(rows["BC-5000 [W]"]["gap_days"], 21)
        self.assertEqual(rows["BC-5000 [V]"]["previous_id"], first.pk)
        self.assertEqual(rows["BC-5000 [V]"]["current_id"], second.pk)
        self.assertEqual(rows["BC-5000 [V]"]["gap_days"], 26)

    def test_problem_devices(self):
        p_device = self._installed(self.model, "P")
        for beg in (date(2024, 5, 1), date(2025, 5, 1), date(2026, 3, 1)):
            self._breakdown(p_device, beg)
        make_service(p_device, date(2026, 4, 1), service_type=self.maintenance)
        q_device = self._installed(self.model, "Q")
        for beg in (date(2026, 2, 1), date(2026, 6, 1)):
            self._breakdown(q_device, beg)
        self._breakdown(self._installed(self.model, "R"), date(2026, 2, 1))

        rows = problem_devices(YEAR_2026, EquipmentFilters(), source=self._source())

        self.assertEqual(
            [
                (row["device"], row["total"], row["in_period"], row["last_date"])
                for row in rows
            ],
            [
                ("BC-5000 [P]", 3, 1, date(2026, 3, 1)),
                ("BC-5000 [Q]", 2, 2, date(2026, 6, 1)),
            ],
        )
        self.assertEqual(rows[0]["device_id"], p_device.pk)
        self.assertEqual(rows[0]["department"], "Больница (Казань)")

    def test_models_summary_columns(self):
        devices = [
            self._installed(self.model, "A1"),
            self._installed(self.model, "A2"),
            self._installed(self.model, "A3", ours=False),
        ]
        removed = make_device(self.model, "A4")
        make_install(removed, self.department, date(2019, 1, 1), active=False)
        for day in (1, 2):
            make_service(
                devices[0],
                date(2026, 3, day),
                date(2026, 3, day),
                service_type=self.maintenance,
            )
        self._breakdown(devices[1], date(2026, 5, 1), date(2026, 5, 5))
        make_replacement(self.model, "R1")
        make_replacement(self.model, "R2")
        make_replacement(self.model, "R3", state="not_working")
        spare_only = make_equipment("Запасной", direction=None, manufacturer=None)
        make_replacement(spare_only, "R4")

        rows = models_summary(
            YEAR_2026, TODAY, EquipmentFilters(), source=self._source()
        )

        self.assertEqual([row["label"] for row in rows], ["BC-5000", "Запасной"])
        first = rows[0]
        self.assertEqual(first["manufacturer"], "Mindray")
        self.assertEqual(first["direction"], "Гематология")
        self.assertEqual(
            (first["at_client"], first["ours"], first["others"]), (3, 2, 1)
        )
        self.assertEqual((first["planned"], first["breakdowns"]), (2, 1))
        self.assertEqual(
            first["per_unit_year"],
            (Decimal(1) / 3 * 365 / 289).quantize(Decimal("0.01")),
        )
        self.assertEqual(first["median_days"], Decimal("5.0"))
        self.assertEqual((first["fund_working"], first["fund_total"]), (2, 3))
        second = rows[1]
        self.assertEqual(second["at_client"], 0)
        self.assertIsNone(second["per_unit_year"])
        self.assertEqual(second["manufacturer"], "Производитель не указан")
        self.assertEqual(second["direction"], "Направление не указано")
