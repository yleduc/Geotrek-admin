# Generated by Django 2.2.17 on 2020-11-12 10:10

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_remove_other_objects_from_factories'),
    ]

    operations = [
        migrations.AlterField(
            model_name='path',
            name='geom',
            field=django.contrib.gis.db.models.fields.LineStringField(srid=2154),
        ),
    ]
