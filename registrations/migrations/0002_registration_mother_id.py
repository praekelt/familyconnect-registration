# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-03-28 11:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='mother_id',
            field=models.CharField(default='replace_me', max_length=36),
            preserve_default=False,
        ),
    ]
