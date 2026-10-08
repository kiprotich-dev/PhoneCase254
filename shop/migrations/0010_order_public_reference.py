from django.db import migrations, models


def populate_references(apps, schema_editor):
    Order = apps.get_model('shop', 'Order')
    for order in Order.objects.order_by('created_at', 'pk'):
        order.public_reference = f'PC254-{order.created_at:%Y%m%d}-{order.pk:04d}'
        order.save(update_fields=['public_reference'])


class Migration(migrations.Migration):
    dependencies = [('shop', '0009_order_discounts')]

    operations = [
        migrations.AddField(name='public_reference', model_name='order', field=models.CharField(blank=True, max_length=32)),
        migrations.RunPython(populate_references, migrations.RunPython.noop),
        migrations.AlterField(name='public_reference', model_name='order', field=models.CharField(blank=True, max_length=32, unique=True)),
    ]
