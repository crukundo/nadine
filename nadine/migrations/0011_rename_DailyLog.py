# -*- coding: utf-8 -*-
# Generated by Django 1.9.9 on 2016-09-14 19:58
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nadine', '0010_add_events'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DailyLog',
            new_name='CoworkingDay',
        ),
    ]
