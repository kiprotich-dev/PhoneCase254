from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('shop', '0004_alter_category_slug_alter_product_slug')]
    operations = [
        migrations.CreateModel(name='CustomerProfile', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('phone', models.CharField(blank=True, max_length=30)), ('default_address', models.TextField(blank=True)),
            ('loyalty_points', models.PositiveIntegerField(default=0)), ('total_orders', models.PositiveIntegerField(default=0)),
            ('completed_orders', models.PositiveIntegerField(default=0)), ('lifetime_spend', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('tier', models.CharField(choices=[('standard', 'Standard'), ('silver', 'Silver'), ('gold', 'Gold')], default='standard', max_length=20)),
            ('last_order_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='customer_profile', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='ContactMessage', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('message', models.TextField()), ('status', models.CharField(choices=[('new', 'New'), ('read', 'Read'), ('replied', 'Replied')], default='new', max_length=20)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='messages', to='shop.order')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contact_messages', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.AddField(model_name='order', name='customer_note', field=models.TextField(blank=True)),
        migrations.AddField(model_name='order', name='loyalty_awarded', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='order', name='payment_method', field=models.CharField(choices=[('prepaid', 'Pay before delivery'), ('cod', 'Pay on delivery')], default='prepaid', max_length=20)),
        migrations.AddField(model_name='order', name='payment_status', field=models.CharField(choices=[('pending', 'Pending payment'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending', max_length=20)),
    ]
