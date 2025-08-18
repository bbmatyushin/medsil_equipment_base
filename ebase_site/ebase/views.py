import logging
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db.models import Sum, QuerySet
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView

from typing import Optional

from .models import Service
from spare_part.models import SparePartCount, SparePart


logger = logging.getLogger(__name__)


def index(request):
    logger.info('LOGGER HERE!')
    return redirect(f"{request.path}admin/")
    # return HttpResponse("Hello, world. You're at the ebase index.")


class IndexRedirectView(RedirectView):
    url = 'admin/'


def get_service_part_count(spare_part_count_info: Optional[dict], part: dict) -> int:
    """Получаем количество запчестей используемых в ремонте
    для определенного срока годности"""
    if spare_part_count_info:
        for info in spare_part_count_info:
            ext_dt = datetime.date(datetime.strptime(info["expiration_dt"], "%Y-%m-%d")) \
                if info["expiration_dt"] else None
            if ext_dt == part["expiration_dt"]:
                return info["service_part_count"]
    return 0


@staff_member_required
def get_spare_part_quantity(request, service_id,  spare_part_id):
    """
    API endpoint для получения доступного количества запчасти
    Для страницы admin/ebase/service/<spare_part_id>/change/, на которой
    динамически, с помощью JS, формируется блок "Выбранные запчасти" > part_to_service.js
    """
    try:
        part = SparePart.objects.get(pk=spare_part_id)
        service = Service.objects.get(pk=service_id)

        # информация о том склолько уже было использованна данной запчасти в ремонте
        spare_part_count_info = service.spare_part_count.get(str(spare_part_id))

        part_count = SparePartCount.objects.annotate(total_amount=Sum('amount')) \
            .filter(spare_part=part) \
            .values('total_amount', 'expiration_dt') \
            .order_by("expiration_dt")

        if not part_count:  # заглушка на случай, если запчасть не ставили на приход
            part_count = [{"total_amount": 0, "expiration_dt": None}]

        data = [
            {
                "name": f"{part.name}" + (f" (арт. {part.article})" if part.article else "") +
                        (f' годен до: {obj.get("expiration_dt").strftime("%d.%m.%Y")}г.' if obj.get("expiration_dt") else ""),
                "quantity": obj["total_amount"] if obj.get("total_amount") else 0,
                "id": spare_part_id,
                "expiration_dt": obj["expiration_dt"] if obj.get("expiration_dt") else None,
                "service_part_count": get_service_part_count(spare_part_count_info, obj),
            } for obj in part_count
        ]

        return JsonResponse({"results": data})
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)


@staff_member_required
def get_spare_part_quantity_null(request, spare_part_id):
    """
    API endpoint для получения доступного количества запчасти
    Для страницы admin/ebase/service/<spare_part_id>/change/, на которой
    динамически, с помощью JS, формируется блок "Выбранные запчасти" > part_to_service.js
    """
    try:
        part = SparePart.objects.get(pk=spare_part_id)
        # service = Service.objects.get(pk=service_id)

        # информация о том склолько уже было использованна данной запчасти в ремонте
        # spare_part_count_info = service.spare_part_count.get(str(spare_part_id))

        part_count = SparePartCount.objects.annotate(total_amount=Sum('amount')) \
            .filter(spare_part=part) \
            .values('total_amount', 'expiration_dt') \
            .order_by("expiration_dt")

        data = [
            {
                "name": f"{part.name}" + (f" (арт. {part.article})" if part.article else "") +
                        (f' годен до: {obj.get("expiration_dt").strftime("%d.%m.%Y")}г.' if obj.get("expiration_dt") else ""),
                "quantity": obj["total_amount"] if obj.get("total_amount") else 0,
                "id": spare_part_id,
                "expiration_dt": obj["expiration_dt"] if obj.get("expiration_dt") else None,
                "service_part_count": 0,
            } for obj in part_count
        ]

        return JsonResponse({"results": data})
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)



