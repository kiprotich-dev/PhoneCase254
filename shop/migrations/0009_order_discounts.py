from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shop', '0008_backfill_order_subtotals')]

    operations = [
        migrations.AddField(name='item_discount', model_name='order', field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField(name='delivery_discount', model_name='order', field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
    ]
