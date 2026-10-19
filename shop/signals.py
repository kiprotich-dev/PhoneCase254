from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, OrderStatusUpdate


@receiver(post_save, sender=Order)
def record_order_status(sender, instance, created, update_fields, **kwargs):
    if not created and update_fields is not None and 'status' not in update_fields:
        return
    latest = instance.status_updates.order_by('-created_at').first()
    if latest and latest.status == instance.status:
        return
    OrderStatusUpdate.objects.create(order=instance, status=instance.status)
