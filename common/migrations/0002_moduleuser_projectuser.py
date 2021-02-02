# Generated by Django 3.1.1 on 2021-02-02 10:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='2', max_length=1)),
                ('delete_state', models.CharField(default='0', max_length=1)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='common.project')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.user')),
            ],
        ),
        migrations.CreateModel(
            name='ModuleUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='2', max_length=1)),
                ('delete_state', models.CharField(default='0', max_length=1)),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='common.module')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.user')),
            ],
        ),
    ]
