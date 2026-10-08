from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('shop', '0005_contactmessage_customerprofile_order_fields')]
    operations = [migrations.AlterField(model_name='order', name='status', field=models.CharField(choices=[('pending', 'Pending payment'), ('confirmed', 'Confirmed'), ('packed', 'Packed'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')], default='pending', max_length=20))]
