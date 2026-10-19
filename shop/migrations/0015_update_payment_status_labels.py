from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shop', '0014_order_status_payment_choices')]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('paid', 'Paid'), ('on_delivery', 'To be paid on delivery'), ('pending', 'Awaiting payment'), ('failed', 'Failed')], default='pending', max_length=20),
        ),
    ]
