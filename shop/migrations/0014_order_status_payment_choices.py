from django.db import migrations, models


def migrate_order_states(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    Order.objects.filter(status__in=['pending', 'confirmed', 'packed']).update(status='queue')
    Order.objects.filter(payment_method='cod', payment_status='pending').update(payment_status='on_delivery')


class Migration(migrations.Migration):
    dependencies = [('shop', '0013_loyalty_rules')]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('queue', 'On queue'), ('shipping', 'Shipping'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('returned', 'Returned'), ('cancelled', 'Cancelled')], default='queue', max_length=20),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('paid', 'Paid'), ('on_delivery', 'On delivery'), ('pending', 'Pending payment'), ('failed', 'Failed')], default='pending', max_length=20),
        ),
        migrations.RunPython(migrate_order_states, migrations.RunPython.noop),
    ]
