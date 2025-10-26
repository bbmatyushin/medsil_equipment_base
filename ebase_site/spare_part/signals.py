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
        spare_part = instance.spare_part
        quantity = instance.quantity
        expiration_dt = instance.expiration_dt
        
        try:
            # Обновляем остаток с учетом срока годности
            SparePartCount.objects.filter(
                spare_part=spare_part,
                expiration_dt=expiration_dt
            ).update(amount=F('amount') - quantity)

            logger.info(
                'Updated spare part count after M2M shipment. '
                'Part: %s, Shipment ID: %s, Quantity: %d, Expiration: %s',
                spare_part.name, instance.shipment_id, quantity, expiration_dt
            )
        except SparePartCount.DoesNotExist:
            logger.error(
                f'SparePartCount not found for part {spare_part.name} with expiration {expiration_dt}',
            )
        except Exception as e:
            logger.exception(
                'Error updating SparePartCount for M2M shipment: %s',
                str(e)
            )


@receiver(post_delete, sender=SparePartShipmentM2M)
def spare_part_shipment_m2m_post_delete(sender, instance, **kwargs):
    """
    Восстанавливает количество запчастей при удалении связи ShipmentM2M.
    """
    spare_part = instance.spare_part
    quantity = instance.quantity
    expiration_dt = instance.expiration_dt
    
    try:
        # Восстанавливаем остаток с учетом срока годности
        SparePartCount.objects.filter(
            spare_part=spare_part,
            expiration_dt=expiration_dt
        ).update(amount=F('amount') + quantity)
        
        logger.info(f'Restored {quantity} items of {spare_part.name} (exp: {expiration_dt}) after M2M deletion')
        
    except SparePartCount.DoesNotExist:
        logger.error(f'SparePartCount not found for part {spare_part.name} with expiration {expiration_dt}')
    except Exception as e:
        logger.exception(f'Error restoring SparePartCount: {str(e)}')


@receiver(post_save, sender=SparePartShipmentV2)
def spare_part_shipment_v2_post_save(sender, instance, created, **kwargs):
    """Сигнал для уменьшения количества запчастей на склад при добавлении записи из SparePartShipmentV2."""
    if created:
        if instance.shipment_m2m.exists():
            for shipment_item in instance.shipment_m2m.all():
                spare_part = shipment_item.spare_part
                quantity = shipment_item.quantity

                try:
                    spare_part_info = instance.service.spare_part_count.get(str(spare_part.pk))
                    for item in spare_part_info:
                        SparePartCount.objects.filter(
                            spare_part=spare_part,
                            expiration_dt=item['expiration_dt']
                        ).update(amount=F('amount') - quantity)
                    else:  # при обновлении в SparePartShipmentV2 заменяем amount на quantity
                        SparePartCount.objects.filter(
                            spare_part=spare_part,
                            expiration_dt=item['expiration_dt']
                        ).update(amount=quantity)
                    logger.info(f'Update Shipment spare part. Updated amount for spare_part_id {str(spare_part.id)}')
                except SparePartCount.DoesNotExist:
                    logger.error(f'SparePartCount not found for spare_part_id {str(spare_part.id)}')


@receiver(post_delete, sender=SparePartShipmentV2)
def spare_part_shipment_v2_post_delete(sender, instance, **kwargs):
    """Сигнал для возврата количества запчастей на склад при удалении записи из SparePartShipmentV2."""
    if instance.shipment_m2m.exists():
        for shipment_item in instance.shipment_m2m.all():
            spare_part = shipment_item.spare_part
            quantity = shipment_item.quantity
            try:
                spare_part_info = instance.service.spare_part_count.get(str(spare_part.pk))
                for item in spare_part_info:
                    SparePartCount.objects.filter(
                        spare_part=spare_part,
                        expiration_dt=item['expiration_dt']
                    ).update(amount=F('amount') + quantity)
                    logger.info(f'Deleted Shipment spare part. Updated amount for spare_part_id {spare_part.id}')
            except SparePartCount.DoesNotExist:
                logger.error('SparePartCount not found for spare_part_id %s', spare_part.id)


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
