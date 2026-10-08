from django.db import migrations, models


def add_welcome_points(apps, schema_editor):
    CustomerProfile = apps.get_model('shop', 'CustomerProfile')
    for profile in CustomerProfile.objects.all():
        profile.loyalty_points += 50
        profile.save(update_fields=['loyalty_points'])


class Migration(migrations.Migration):
    dependencies = [('shop', '0012_order_points')]

    operations = [
        migrations.AlterField(name='loyalty_points', model_name='customerprofile', field=models.PositiveIntegerField(default=50)),
        migrations.RunPython(add_welcome_points, migrations.RunPython.noop),
    ]
