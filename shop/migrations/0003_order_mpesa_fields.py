from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('shop', '0002_product_image_url')]
    operations = [
        migrations.AddField(model_name='order', name='mpesa_checkout_request_id', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='order', name='mpesa_receipt', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='order', name='mpesa_result_code', field=models.CharField(blank=True, max_length=20)),
    ]
