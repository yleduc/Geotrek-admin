# Generated by Django 3.1.14 on 2022-03-07 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('infrastructure', '0026_auto_20210908_1337'),
    ]

    operations = [
        migrations.AddField(
            model_name='infrastructure',
            name='accessibility',
            field=models.TextField(blank=True, verbose_name='Accessibility'),
        ),
    ]
