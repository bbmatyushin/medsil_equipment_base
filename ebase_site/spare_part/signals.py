import logging

from django.db.models import F
from django.db.models.functions.math import Round
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete, pre_save

from .models import *

logger = logging.getLogger("SPARE_PART_SIGNALS")


@receiver(post_save, sender=SparePartSupply)
def spare_part_supply_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.count_supply > 0:
            part = SparePartCount.objects.filter(
                spare_part=instance.spare_part,
                expiration_dt=instance.expiration_dt,
            )
            if part.exists():
                SparePartCount.objects.filter(
                    spare_part=instance.spare_part,
                    expiration_dt=instance.expiration_dt,
                ).update(amount=Round(F("amount") + instance.count_supply, 2))
                logger.info(
                    "New Supply spare part. Updated amount for spare_part_id %s",
                    instance.spare_part,
                )
            else:
                SparePartCount.objects.create(
                    spare_part=instance.spare_part,
                    amount=instance.count_supply,
                    expiration_dt=instance.expiration_dt,
                )
                logger.info(
                    "New Supply spare part. Created new amount for spare part %s",
                    instance.spare_part,
                )


@receiver(post_delete, sender=SparePartSupply)
def spare_part_supply_post_delete(sender, instance, **kwargs):
    if instance.count_supply > 0:
        part = SparePartCount.objects.filter(
            spare_part=instance.spare_part,
            expiration_dt=instance.expiration_dt,
        )
        if part.exists():
            SparePartCount.objects.filter(
                spare_part=instance.spare_part,
                expiration_dt=instance.expiration_dt,
            ).update(amount=Round(F("amount") - instance.count_supply, 2))
            logger.info(
                "Deleted Supply spare part. Updated amount for spare_part_id %s",
                instance.spare_part,
            )


@receiver(pre_save, sender=SparePartShipmentM2M)
def spare_part_m2m_pre_save(sender, instance, **kwargs):
    """
    Сохраняем старые значения перед сохранением, чтобы в post_save
    можно было вычислить дельту изменений (количество, запчасть, срок годности).
    """
    if instance.pk:
        try:
            old = SparePartShipmentM2M.objects.get(pk=instance.pk)
            instance._old_quantity = old.quantity
            instance._old_expiration_dt = old.expiration_dt
            instance._old_spare_part_id = old.spare_part_id
        except SparePartShipmentM2M.DoesNotExist:
            instance._old_quantity = 0
            instance._old_expiration_dt = None
            instance._old_spare_part_id = None
    else:
        instance._old_quantity = 0
        instance._old_expiration_dt = None
        instance._old_spare_part_id = None


@receiver(post_save, sender=SparePartShipmentM2M)
def spare_part_quantity_post_save(sender, instance, created, **kwargs):
    """
    Обновляет остатки SparePartCount при создании/изменении записи отгрузки.

    - Новая запись (created=True): списывает quantity со склада.
    - Изменение существующей (created=False):
        1. Возвращает старый остаток (old_quantity, old_part, old_expiration).
        2. Списывает новый остаток (new_quantity, new_part, new_expiration).
      Такой подход корректно обрабатывает изменение количества, запчасти и срока.
    """
    new_quantity = instance.quantity
    new_exp_dt = instance.expiration_dt
    new_spare_part = instance.spare_part

    old_quantity = getattr(instance, "_old_quantity", 0)
    old_exp_dt = getattr(instance, "_old_expiration_dt", None)
    old_spare_part_id = getattr(instance, "_old_spare_part_id", None)

    if created:
        # --- Новая запись: просто списываем ---
        if new_quantity > 0:
            SparePartCount.objects.filter(
                spare_part=new_spare_part, expiration_dt=new_exp_dt
            ).update(amount=Round(F("amount") - new_quantity, 2))
            logger.info(
                "Created M2M shipment. Part: %s, Qty: %s, Exp: %s, Shipment: %s",
                new_spare_part.name,
                new_quantity,
                new_exp_dt,
                instance.shipment_id,
            )
    else:
        # --- Изменение существующей: возвращаем старое, списываем новое ---
        # Шаг 1: возвращаем старый остаток
        if old_quantity > 0 and old_spare_part_id:
            try:
                old_spare_part = SparePart.objects.get(pk=old_spare_part_id)
                SparePartCount.objects.filter(
                    spare_part=old_spare_part, expiration_dt=old_exp_dt
                ).update(amount=Round(F("amount") + old_quantity, 2))
                logger.info(
                    "Returned old stock. Part: %s, Qty: %s, Exp: %s",
                    old_spare_part.name,
                    old_quantity,
                    old_exp_dt,
                )
            except SparePart.DoesNotExist:
                logger.error(
                    "Old spare part (pk=%s) not found during update", old_spare_part_id
                )

        # Шаг 2: списываем новый остаток
        if new_quantity > 0:
            SparePartCount.objects.filter(
                spare_part=new_spare_part, expiration_dt=new_exp_dt
            ).update(amount=Round(F("amount") - new_quantity, 2))
            logger.info(
                "Deducted new stock. Part: %s, Qty: %s, Exp: %s, Shipment: %s",
                new_spare_part.name,
                new_quantity,
                new_exp_dt,
                instance.shipment_id,
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
            spare_part=spare_part, expiration_dt=expiration_dt
        ).update(amount=Round(F("amount") + quantity, 2))

        logger.info(
            f"Restored {quantity} items of {spare_part.name} (exp: {expiration_dt}) after M2M deletion"
        )

    except SparePartCount.DoesNotExist:
        logger.error(
            f"SparePartCount not found for part {spare_part.name} with expiration {expiration_dt}"
        )
    except Exception as e:
        logger.exception(f"Error restoring SparePartCount: {str(e)}")


# Сигналы post_save/post_delete для SparePartShipmentV2 удалены.
# Учёт остатков полностью обслуживается сигналами модели SparePartShipmentM2M:
#   - spare_part_quantity_post_save (списание при создании M2M-связи)
#   - spare_part_shipment_m2m_post_delete (возврат при удалении M2M-связи)
# Каскадное удаление SparePartShipmentV2 → SparePartShipmentM2M автоматически
# восстанавливает остатки через сигнал post_delete на M2M.


@receiver(post_save, sender=SparePartShipment)
def spare_part_shipment_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.spare_part_count is None:
            return
        if instance.count_shipment > 0:
            part = instance.spare_part_count
            part_name = part.spare_part.name
            part.amount = round(part.amount - instance.count_shipment, 2)
            part.save()
            logger.info(
                "New Shipment spare part. Updated amount for spare_part %s", part_name
            )


@receiver(post_delete, sender=SparePartShipment)
def spare_part_shipment_post_delete(sender, instance, **kwargs):
    if instance.spare_part_count is None:
        return
    if instance.count_shipment > 0:
        part = instance.spare_part_count
        part_name = part.spare_part.name
        part.amount = round(part.amount + instance.count_shipment, 2)
        part.save()
        logger.info(
            "Deleted Shipment spare part. Updated amount for spare_part_id %s",
            part_name,
        )


# --- SparePartSupplyItem signals (V2 supply) ---


@receiver(pre_save, sender=SparePartSupplyItem)
def supply_item_pre_save(sender, instance, **kwargs):
    """Сохраняем старые значения для вычисления дельты при обновлении."""
    if instance.pk:
        try:
            old = SparePartSupplyItem.objects.get(pk=instance.pk)
            instance._old_quantity = old.quantity
            instance._old_expiration_dt = old.expiration_dt
            instance._old_spare_part_id = old.spare_part_id
        except SparePartSupplyItem.DoesNotExist:
            instance._old_quantity = 0
            instance._old_expiration_dt = None
            instance._old_spare_part_id = None
    else:
        instance._old_quantity = 0
        instance._old_expiration_dt = None
        instance._old_spare_part_id = None


@receiver(post_save, sender=SparePartSupplyItem)
def supply_item_post_save(sender, instance, created, **kwargs):
    """Увеличивает остатки при поставке."""
    new_quantity = instance.quantity
    new_exp_dt = instance.expiration_dt
    new_spare_part = instance.spare_part

    old_quantity = getattr(instance, "_old_quantity", 0)
    old_exp_dt = getattr(instance, "_old_expiration_dt", None)
    old_spare_part_id = getattr(instance, "_old_spare_part_id", None)

    if created:
        if new_quantity > 0:
            _add_supply_stock(new_spare_part, new_exp_dt, new_quantity)
            logger.info(
                "Supply item created. Part: %s, Qty: %s, Exp: %s",
                new_spare_part.name,
                new_quantity,
                new_exp_dt,
            )
    else:
        # Возвращаем старый остаток
        if old_quantity > 0 and old_spare_part_id:
            try:
                old_spare_part = SparePart.objects.get(pk=old_spare_part_id)
                SparePartCount.objects.filter(
                    spare_part=old_spare_part, expiration_dt=old_exp_dt
                ).update(amount=Round(F("amount") - old_quantity, 2))
            except SparePart.DoesNotExist:
                pass
        # Добавляем новый остаток
        if new_quantity > 0:
            _add_supply_stock(new_spare_part, new_exp_dt, new_quantity)
        logger.info(
            "Supply item updated. Reversed old: Part=%s Qty=%s; Added new: Part=%s Qty=%s",
            old_spare_part_id,
            old_quantity,
            new_spare_part.name,
            new_quantity,
        )


@receiver(post_delete, sender=SparePartSupplyItem)
def supply_item_post_delete(sender, instance, **kwargs):
    """Уменьшает остатки при удалении строки поставки."""
    quantity = instance.quantity
    expiration_dt = instance.expiration_dt
    spare_part = instance.spare_part

    updated = SparePartCount.objects.filter(
        spare_part=spare_part, expiration_dt=expiration_dt
    ).update(amount=Round(F("amount") - quantity, 2))

    if updated:
        logger.info(
            "Supply item deleted. Part: %s, Qty: %s, Exp: %s",
            spare_part.name,
            quantity,
            expiration_dt,
        )
    else:
        logger.warning(
            "SparePartCount not found for part %s with expiration %s during supply item deletion",
            spare_part.name,
            expiration_dt,
        )


def _add_supply_stock(spare_part, expiration_dt, quantity):
    """Вспомогательная функция: увеличивает остаток запчасти."""
    part = SparePartCount.objects.filter(
        spare_part=spare_part, expiration_dt=expiration_dt
    )
    if part.exists():
        part.update(amount=Round(F("amount") + quantity, 2))
    else:
        SparePartCount.objects.create(
            spare_part=spare_part, amount=quantity, expiration_dt=expiration_dt
        )
