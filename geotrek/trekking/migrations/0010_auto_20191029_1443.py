# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2019-10-29 13:43
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trekking', '0009_auto_20190809_1146'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trek',
            name='duration',
            field=models.FloatField(blank=True, db_column=b'duree', help_text='In hours (1.5 = 1 h 30, 24 = 1 day, 48 = 2 days)', null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Duration'),
        ),
    ]
