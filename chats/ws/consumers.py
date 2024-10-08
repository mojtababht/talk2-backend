import json
import asyncio

from django.utils.timezone import datetime
from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import DenyConnection

from .serializers import CreateMessageSerializer, MessageSerializer, ChatNotifSerializer
from ..models import Chat, Message
from ..tasks import send_notifications
from reusable.utils import encrypt_message


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = "chat_%s" % self.chat_id
        if not self.scope['user'].is_authenticated:
            raise DenyConnection()
        self.user = self.scope['user']
        self.chat = await self.get_chat(self.chat_id)
        if not self.chat:
            raise DenyConnection()
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(self.room_group_name, {"type": "chat_message"})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        if message := text_data_json.get("message"):
            message = encrypt_message(message, self.chat_id)
            data = {'user': self.scope['user'].id, 'chat': self.chat.id, 'text': message}
            await self.save_message(data)
            await self.channel_layer.group_send(self.room_group_name, {"type": "chat_message", "message": message})
        if seen_messages_id_list := text_data_json.get("seen"):
            asyncio.create_task(self.seen_messages(seen_messages_id_list, self.user.id))
            await self.channel_layer.group_send(self.room_group_name, {"type": "chat_message"})



    async def chat_message(self, event):
        response = await self.get_messages()
        await self.send(text_data=json.dumps(response))

    @database_sync_to_async
    def get_chat(self, chat_id):
        try:
            chat = Chat.objects.get(id=chat_id)
            if not self.scope['user'] in chat.members.all():
                return False
        except Chat.DoesNotExist:
            return False
        return chat

    @database_sync_to_async
    def get_chat_name(self, chat):
        return chat.name

    @database_sync_to_async
    def save_message(self, data):
        serializer = CreateMessageSerializer(data=data)
        serializer.is_valid()
        serializer.save()

    @database_sync_to_async
    def get_messages(self):
        messages = Message.objects.filter(chat=self.chat).select_related('chat')
        return MessageSerializer(messages, many=True, context={'user': self.user}).data

    @database_sync_to_async
    def seen_messages(self, messages_id_list, user_id):
        messages = Message.objects.filter(id__in=messages_id_list)
        for message in messages:
            message.seen_by.add(user_id)


class InformationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.name = f'infos_{self.user.id}'
        if not self.user.is_authenticated:
            raise DenyConnection()
        await self.channel_layer.group_add(self.name, self.channel_name)
        await self.set_user_online()
        await self.notif_after_online_offline()
        await self.accept()
        data = await self.get_chats(self.user.id)
        await self.send(text_data=json.dumps(data))

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.set_user_offline()
            await self.notif_after_online_offline()
        await self.channel_layer.group_discard(self.name, self.channel_name)

    async def receive(self, text_data):
        await self.channel_layer.group_send(self.name, {"type": "send_notification", 'user_id': self.user.id})

    async def send_notification(self, event):
        if user_id := event.get('user_id'):
            data = await self.get_chats(user_id)
            await self.send(text_data=json.dumps(data))


    @database_sync_to_async
    def get_chats(self, user_id):
        chats = Chat.objects.filter(members__id=user_id)
        return ChatNotifSerializer(chats, many=True, context={'user_id': user_id, 'user': self.user}).data

    @database_sync_to_async
    def set_user_online(self):
        profile = self.user.profile
        profile.is_online = True
        profile.save()


    @database_sync_to_async
    def set_user_offline(self):
        profile = self.user.profile
        profile.is_online = False
        profile.last_online = datetime.now()
        profile.save()

    @database_sync_to_async
    def notif_after_online_offline(self):
        users = get_user_model().objects.filter(chats__in=self.user.chats.all())
        users_id = list(users.values_list('id', flat=True))
        send_notifications.apply_async(args=(users_id,))
