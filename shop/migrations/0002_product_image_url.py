from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('shop', '0001_initial')]
    operations = [migrations.AddField(model_name='product', name='image_url', field=models.URLField(blank=True, help_text='Optional hosted product photo URL from Unsplash, Pexels, or your own CDN.'))]
