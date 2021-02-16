# Generated by Django 1.11.14 on 2018-12-03 10:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authent', '0002_auto_20181107_1620'),
        ('core', '0004_auto_20181116_1821'),
        ('infrastructure', '0006_auto_20181219_1524'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Infrastructure',
        ),
        migrations.DeleteModel(
            name='Signage',
        ),
        migrations.CreateModel(
            name='Infrastructure',
            fields=[
                ('published', models.BooleanField(db_column='public', default=False, help_text='Online', verbose_name='Published')),
                ('publication_date', models.DateField(blank=True, db_column='date_publication', editable=False, null=True, verbose_name='Publication date')),
                ('topo_object', models.OneToOneField(db_column='evenement', on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.Topology')),
                ('name', models.CharField(db_column='nom', help_text='Reference, code, ...', max_length=128, verbose_name='Name')),
                ('description', models.TextField(blank=True, db_column='description', help_text='Specificites', verbose_name='Description')),
                ('implantation_year', models.PositiveSmallIntegerField(db_column='annee_implantation', null=True, verbose_name='Implantation year')),
                ('condition', models.ForeignKey(blank=True, db_column='etat', null=True, on_delete=django.db.models.deletion.PROTECT, to='infrastructure.InfrastructureCondition', verbose_name='Condition')),
                ('structure', models.ForeignKey(db_column='structure', default=1, on_delete=django.db.models.deletion.CASCADE, to='authent.Structure', verbose_name='Related structure')),
                ('type', models.ForeignKey(db_column='type', on_delete=django.db.models.deletion.CASCADE, to='infrastructure.InfrastructureType', verbose_name='Type')),
                ('eid', models.CharField(blank=True, db_column='id_externe', max_length=1024, null=True, verbose_name='External id')),
            ],
            options={
                'db_table': 'a_t_infrastructure',
                'verbose_name': 'Infrastructure',
                'verbose_name_plural': 'Infrastructures',
            },
            bases=('core.topology', models.Model),
        ),
        migrations.CreateModel(
            name='Signage',
            fields=[
                ('published', models.BooleanField(db_column='public', default=False, help_text='Online', verbose_name='Published')),
                ('publication_date', models.DateField(blank=True, db_column='date_publication', editable=False, null=True, verbose_name='Publication date')),
                ('topo_object', models.OneToOneField(db_column='evenement', on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.Topology')),
                ('name', models.CharField(db_column='nom', help_text='Reference, code, ...', max_length=128, verbose_name='Name')),
                ('description', models.TextField(blank=True, db_column='description', help_text='Specificites', verbose_name='Description')),
                ('implantation_year', models.PositiveSmallIntegerField(db_column='annee_implantation', null=True, verbose_name='Implantation year')),
                ('condition', models.ForeignKey(blank=True, db_column='etat', null=True, on_delete=django.db.models.deletion.PROTECT, to='infrastructure.InfrastructureCondition', verbose_name='Condition')),
                ('structure', models.ForeignKey(db_column='structure', default=1, on_delete=django.db.models.deletion.CASCADE, to='authent.Structure', verbose_name='Related structure')),
                ('type', models.ForeignKey(db_column='type', on_delete=django.db.models.deletion.CASCADE, to='infrastructure.InfrastructureType', verbose_name='Type')),
                ('eid', models.CharField(blank=True, db_column='id_externe', max_length=1024, null=True, verbose_name='External id')),
            ],
            options={
                'db_table': 'a_t_signaletique',
                'verbose_name': 'Signage',
                'verbose_name_plural': 'Signages',
            },
            bases=('core.topology', models.Model),
        ),
    ]
