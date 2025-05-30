# Generated by Django 5.2 on 2025-05-03 09:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0003_gameroom_guest_total_answered_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameroom',
            name='guest_ready',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='gameroom',
            name='host_ready',
            field=models.BooleanField(default=False),
        ),
    ]
