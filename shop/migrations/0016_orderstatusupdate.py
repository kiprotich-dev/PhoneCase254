from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_order_status_history(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    OrderStatusUpdate = apps.get_model('shop', 'OrderStatusUpdate')
    OrderStatusUpdate.objects.bulk_create(
        OrderStatusUpdate(order_id=order.pk, status=order.status, created_at=order.created_at)
        for order in Order.objects.all().only('pk', 'status', 'created_at')
    )


class Migration(migrations.Migration):
    dependencies = [('shop', '0015_update_payment_status_labels')]
    operations = [
        migrations.CreateModel(
            name='OrderStatusUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('queue', 'On queue'), ('shipping', 'Shipping'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('returned', 'Returned'), ('cancelled', 'Cancelled')], max_length=20)),
                ('note', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_updates', to='shop.order')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.RunPython(seed_order_status_history, migrations.RunPython.noop),
    ]
