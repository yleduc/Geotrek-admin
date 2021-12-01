# Generated by Django 3.1.13 on 2021-10-22 12:55

from django.db import migrations
import uuid


def gen_uuid(apps, schema_editor):
    MyModel1 = apps.get_model('tourism', 'touristiccontent')
    MyModel2 = apps.get_model('tourism', 'touristicevent')
    for row in MyModel1.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])
    for row in MyModel2.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('tourism', '0016_auto_20211022_1251'),
    ]

    operations = [
        migrations.RunPython(gen_uuid),
    ]
