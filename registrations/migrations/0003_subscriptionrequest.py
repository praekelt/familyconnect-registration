# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-03-28 14:50
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0002_registration_mother_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('contact', models.CharField(max_length=36)),
                ('messageset', models.IntegerField()),
                ('next_sequence_number', models.IntegerField(default=1)),
                ('lang', models.CharField(max_length=6)),
                ('schedule', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
