import logging

from django.db.models import F
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import *


logger = logging.getLogger('SPARE_PART_SIGNALS')


@receiver(post_save, sender=SparePartSupply)
def spare_part_supply_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.count_supply > 0:
            part = SparePartCount.objects.filter(spare_part=instance.spare_part, expiration_dt=instance.expiration_dt,)
            if part.exists():
                SparePartCount.objects.filter(spare_part=instance.spare_part, expiration_dt=instance.expiration_dt,)\
                    .update(amount=F('amount') + instance.count_supply)
                logger.info('New Supply spare part. Updated amount for spare_part_id %s',
                            instance.spare_part)
            else:
                SparePartCount.objects.create(spare_part=instance.spare_part, amount=instance.count_supply,
                                              expiration_dt=instance.expiration_dt,)
                logger.info('New Supply spare part. Created new amount for spare part %s',
                            instance.spare_part)


@receiver(post_delete, sender=SparePartSupply)
def spare_part_supply_post_delete(sender, instance, **kwargs):
    if instance.count_supply > 0:
        part = SparePartCount.objects.filter(spare_part=instance.spare_part, expiration_dt=instance.expiration_dt,)
        if part.exists():
            SparePartCount.objects.filter(spare_part=instance.spare_part, expiration_dt=instance.expiration_dt,)\
                .update(amount=F('amount') - instance.count_supply)
            logger.info('Deleted Supply spare part. Updated amount for spare_part_id %s',
                        instance.spare_part)


@receiver(post_save, sender=SparePartShipmentM2M)
def spare_part_quantity_post_save(sender, instance, created, **kwargs):
    if created and instance.quantity > 0:
        try:
            # Получаем связанную запчасть и её количество
            spare_part = instance.spare_part
            quantity = instance.quantity

            # Находим соответствующую запись в SparePartCount
            part_count = SparePartCount.objects.get(
                spare_part=spare_part,
                expiration_dt=instance.shipment.expiration_dt  # используем дату из отгрузки
            )

            # Атомарно уменьшаем количество
            SparePartCount.objects.filter(pk=part_count.pk).update(
                amount=F('amount') - quantity
            )

            logger.info(
                'Updated spare part count after M2M shipment. '
                'Part: %s, Shipment ID: %s, Quantity: %d',
                spare_part.name, instance.shipment_id, quantity
            )

        except SparePartCount.DoesNotExist:
            logger.error(
                'SparePartCount not found for part %s and expiration date %s',
                spare_part.name, instance.shipment.expiration_dt
            )
        except Exception as e:
            logger.exception(
                'Error updating SparePartCount for M2M shipment: %s',
                str(e)
            )


@receiver(post_save, sender=SparePartShipment)
def spare_part_shipment_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.count_shipment > 0:
            part = instance.spare_part_count
            part_name = part.spare_part.name
            part.amount = part.amount - instance.count_shipment
            part.save()
            logger.info('New Shipment spare part. Updated amount for spare_part %s', part_name)


@receiver(post_delete, sender=SparePartShipment)
def spare_part_shipment_post_delete(sender, instance, **kwargs):
    if instance.count_shipment > 0:
        part = instance.spare_part_count
        part_name = part.spare_part.name
        part.amount = part.amount + instance.count_shipment
        part.save()
        logger.info('Deleted Shipment spare part. Updated amount for spare_part_id %s', part_name)
