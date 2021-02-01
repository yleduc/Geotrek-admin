# Generated by Django 3.1.5 on 2021-02-01 16:48

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    replaces = [('zoning', '0001_initial'), ('zoning', '0002_auto_20200211_1011'),
                ('zoning', '0003_auto_20200406_1412'), ('zoning', '0004_auto_20200831_1406'),
                ('zoning', '0005_auto_20201126_0706'), ('zoning', '0006_clean_spatial_index'),
                ('zoning', '0007_auto_20210126_0956'), ('zoning', '0008_auto_20210118_1443')]

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='City',
            fields=[
                ('code', models.CharField(max_length=6, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=2154)),
                ('published', models.BooleanField(default=True, help_text='Visible on Geotrek-rando', verbose_name='Published')),
            ],
            options={
                'verbose_name': 'City',
                'verbose_name_plural': 'Cities',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='District',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=2154)),
                ('published', models.BooleanField(default=True, help_text='Visible on Geotrek-rando', verbose_name='Published')),
            ],
            options={
                'verbose_name': 'District',
                'verbose_name_plural': 'Districts',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='RestrictedAreaType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
            ],
            options={
                'verbose_name': 'Restricted area type',
            },
        ),
        migrations.CreateModel(
            name='RestrictedArea',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250, verbose_name='Name')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=2154)),
                ('published', models.BooleanField(default=True, help_text='Visible on Geotrek-rando', verbose_name='Published')),
                ('area_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zoning.restrictedareatype', verbose_name='Restricted area')),
            ],
            options={
                'verbose_name': 'Restricted area',
                'verbose_name_plural': 'Restricted areas',
                'ordering': ['area_type', 'name'],
            },
        ),
    ]
