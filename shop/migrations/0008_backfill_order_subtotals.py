from django.db import migrations


def backfill_order_subtotals(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    for order in Order.objects.all():
        order.subtotal = order.total
        order.delivery_fee = 0
        order.save(update_fields=['subtotal', 'delivery_fee'])


class Migration(migrations.Migration):
    dependencies = [('shop', '0007_order_delivery_fee_order_subtotal')]

    operations = [migrations.RunPython(backfill_order_subtotals, migrations.RunPython.noop)]
