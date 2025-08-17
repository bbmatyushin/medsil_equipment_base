import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView

from spare_part.models import SparePartCount, SparePart


logger = logging.getLogger(__name__)


def index(request):
    logger.info('LOGGER HERE!')
    return redirect(f"{request.path}admin/")
    # return HttpResponse("Hello, world. You're at the ebase index.")


class IndexRedirectView(RedirectView):
    url = 'admin/'


@staff_member_required
def get_spare_part_quantity(request, spare_part_id):
    """
    API endpoint для получения доступного количества запчасти
    Для страницы admin/ebase/service/<spare_part_id>/change/, на которой
    динамически, с помощью JS, формируется блок "Выбранные запчасти" > part_to_service.js
    """
    #TODO: учесть только непросроченные запчасти
    try:
        part = SparePart.objects.get(pk=spare_part_id)
        part_info = ''
        if part.is_expiration:  # имеет срок годности
            part_count = SparePartCount.objects.annotate(total_amount=Sum('amount')) \
                .filter(spare_part=part) \
                .values('total_amount', 'expiration_dt') \
                .order_by('expiration_dt')

            part_info = ", ".join([f"{p['expiration_dt']} - {int(p['total_amount'])} {part.unit}" for p in part_count])

        spare_part_count = SparePartCount.objects.annotate(total_amount=Sum('amount')) \
            .filter(spare_part=part).values('total_amount')

        spare_part_count = int(sum(s['total_amount'] for s in spare_part_count))


        return JsonResponse({
            'name': f'{part.name}{f" (арт. {part.article})" if part.article else ""}{f" (сроки: {part_info})" if part_info else ""}',
            # 'quantity': spare_part_count[0].get('total_amount') if spare_part_count else 0,
            'quantity': spare_part_count if spare_part_count else 0,
            'id': spare_part_id
        })
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)


