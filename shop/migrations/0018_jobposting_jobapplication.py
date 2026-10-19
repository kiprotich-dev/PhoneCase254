from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('shop', '0017_product_offers')]
    operations = [
        migrations.CreateModel(
            name='JobPosting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('department', models.CharField(max_length=100)),
                ('location', models.CharField(default='Nairobi, Kenya', max_length=120)),
                ('employment_type', models.CharField(choices=[('full_time', 'Full time'), ('part_time', 'Part time'), ('contract', 'Contract'), ('internship', 'Internship')], default='full_time', max_length=20)),
                ('summary', models.CharField(max_length=240)),
                ('description', models.TextField()),
                ('requirements', models.TextField(help_text='Add one requirement per line.')),
                ('closing_date', models.DateField(blank=True, null=True)),
                ('is_published', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='JobApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=160)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=30)),
                ('cover_letter', models.TextField()),
                ('resume', models.FileField(blank=True, null=True, upload_to='job-applications/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='shop.jobposting')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
