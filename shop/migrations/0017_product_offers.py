from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shop', '0016_orderstatusupdate')]
    operations = [
        migrations.AddField('product', 'offer_type', models.CharField(choices=[('none', 'No offer'), ('offer', 'Offer'), ('flash_sale', 'Flash sale')], default='none', max_length=20)),
        migrations.AddField('product', 'discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
        migrations.AddField('product', 'offer_ends_at', models.DateTimeField(blank=True, null=True)),
    ]
