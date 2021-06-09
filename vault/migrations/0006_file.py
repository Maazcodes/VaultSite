# Generated by Django 3.2.3 on 2021-06-09 22:16

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0005_rename_geolocations_geolocation'),
    ]

    operations = [
        migrations.CreateModel(
            name='File',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_filename', models.TextField()),
                ('staging_filename', models.TextField()),
                ('md5_sum', models.CharField(blank=True, max_length=32, null=True, validators=[django.core.validators.RegexValidator('^[a-zA-Z0-9]{32}$', 'only hex-encoded md5 hashes are allowed')])),
                ('sha1_sum', models.CharField(blank=True, max_length=40, null=True, validators=[django.core.validators.RegexValidator('^[a-zA-Z0-9]{40}$', 'only hex-encoded sha1 hashes are allowed')])),
                ('sha256_sum', models.CharField(max_length=64, validators=[django.core.validators.RegexValidator('^[a-zA-Z0-9]{64}$', 'only hex-encoded sha256 hashes are allowed')])),
                ('size', models.PositiveBigIntegerField()),
                ('file_type', models.CharField(blank=True, max_length=255, null=True)),
                ('creation_date', models.DateTimeField()),
                ('modified_date', models.DateTimeField()),
                ('deletion_date', models.DateTimeField(blank=True, null=True)),
                ('comment', models.TextField(blank=True, null=True)),
                ('collection', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='vault.collection')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
