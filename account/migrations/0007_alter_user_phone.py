# Generated by Django 4.2 on 2023-08-17 08:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0006_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.TextField(max_length=13, unique=True),
        ),
    ]
