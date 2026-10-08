from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shop', '0011_productreview')]

    operations = [
        migrations.AddField(name='points_discount', model_name='order', field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField(name='points_redeemed', model_name='order', field=models.PositiveIntegerField(default=0)),
    ]
