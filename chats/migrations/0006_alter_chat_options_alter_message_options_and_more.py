# Generated by Django 5.1 on 2024-09-08 08:31

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0005_alter_chat_options_alter_message_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='chat',
            options={},
        ),
        migrations.AlterModelOptions(
            name='message',
            options={'ordering': ('-created_at',)},
        ),
        migrations.RemoveField(
            model_name='message',
            name='created_at_date',
        ),
        migrations.RemoveField(
            model_name='message',
            name='created_at_time',
        ),
        migrations.RemoveField(
            model_name='message',
            name='updated_at_date',
        ),
        migrations.RemoveField(
            model_name='message',
            name='updated_at_time',
        ),
        migrations.AddField(
            model_name='message',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='message',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
