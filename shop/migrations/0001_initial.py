from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Category', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=80)), ('slug', models.SlugField(unique=True))]),
        migrations.CreateModel(name='Product', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=160)), ('slug', models.SlugField(unique=True)), ('description', models.TextField()), ('price', models.DecimalField(decimal_places=2, max_digits=10)), ('image', models.ImageField(blank=True, null=True, upload_to='products/')), ('accent', models.CharField(default='#e7d9ca', help_text='Fallback card colour, e.g. #e7d9ca', max_length=7)), ('is_featured', models.BooleanField(default=False)), ('stock', models.PositiveIntegerField(default=25)), ('created_at', models.DateTimeField(auto_now_add=True)), ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='shop.category'))]),
        migrations.CreateModel(name='Order', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('full_name', models.CharField(max_length=160)), ('phone', models.CharField(max_length=30)), ('delivery_address', models.TextField()), ('mpesa_number', models.CharField(max_length=30)), ('total', models.DecimalField(decimal_places=2, max_digits=10)), ('status', models.CharField(choices=[('pending', 'Pending payment'), ('confirmed', 'Confirmed'), ('packed', 'Packed'), ('shipped', 'Shipped')], default='pending', max_length=20)), ('created_at', models.DateTimeField(auto_now_add=True)), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='Wishlist', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.product')), ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wishlist', to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='OrderItem', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('quantity', models.PositiveIntegerField(default=1)), ('price', models.DecimalField(decimal_places=2, max_digits=10)), ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='shop.order')), ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='shop.product'))]),
        migrations.AddConstraint(model_name='wishlist', constraint=models.UniqueConstraint(fields=('user', 'product'), name='one_wishlist_item')),
    ]

