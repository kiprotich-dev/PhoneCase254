from django.db import migrations

def remove_false_cancellations(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    OrderStatusUpdate = apps.get_model('shop', 'OrderStatusUpdate')
    successful_queue_ids = Order.objects.filter(payment_status='paid', status='queue').values_list('id', flat=True)
    OrderStatusUpdate.objects.filter(order_id__in=successful_queue_ids, status='cancelled').delete()


def reverse_cleanup(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('shop', '0019_reconcile_delivered_cod_orders')]
    operations = [migrations.RunPython(remove_false_cancellations, reverse_cleanup)]

