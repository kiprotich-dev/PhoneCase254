from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('shop', '0003_order_mpesa_fields')]
    operations = [
        migrations.AlterField(model_name='category', name='slug', field=models.SlugField(blank=True, unique=True)),
        migrations.AlterField(model_name='product', name='slug', field=models.SlugField(blank=True, unique=True)),
    ]
