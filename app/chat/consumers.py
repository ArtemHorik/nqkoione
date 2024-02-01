import asyncio
import json

from asgiref.sync import sync_to_async
from bson import ObjectId
from channels.generic.websocket import AsyncWebsocketConsumer
from mongoengine import DoesNotExist, ValidationError

from chat.models import Message, ChatRoom


class ChatConsumer(AsyncWebsocketConsumer):
    """
     WebSocket connections and messages handler for chat rooms.
    """
    active_users_count = {}
    deletion_timers = {}

    async def connect(self):
        """
        Called when the websocket is handshaking as part of the connection process.
        """
        # Extract room name from the URL route
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        if self.room_id in self.deletion_timers:
            self.deletion_timers[self.room_id].cancel()
            del self.deletion_timers[self.room_id]

        room = await self.get_room(self.room_id)

        if room is None or self.active_users_count.get(self.room_id) == 2:
            await self.close(code=4001)
            return

        if self.active_users_count.get(self.room_id, 0) < 2:
            self.active_users_count[self.room_id] = self.active_users_count.get(self.room_id, 0) + 1
            if self.active_users_count[self.room_id] == 2:
                room.second_user_joined = True
                await sync_to_async(room.save)()
        else:
            await self.close()  # Close connection if room full
            return

        await self.accept()

        if room.second_user_joined:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'second_user_joined_event',
                    'message': 'Second user joined'
                }
            )

    async def second_user_joined_event(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'second_user_joined',
            'message': message
        }))

    @sync_to_async
    def get_room(self, room_id):
        room_id_obj = ObjectId(room_id)
        try:
            return ChatRoom.objects.get(id=room_id_obj)
        except DoesNotExist:
            return None

    async def disconnect(self, close_code):
        """
        Disconnect from chat.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        if self.room_id in self.active_users_count:
            self.active_users_count[self.room_id] -= 1
            print(f'USERS COUNT: {self.active_users_count[self.room_id]}')
            if self.active_users_count[self.room_id] == 0:
                # Timer for room deletion if all users left
                self.deletion_timers[self.room_id] = asyncio.create_task(self.schedule_deletion(self.room_id))

    async def schedule_deletion(self, room_id: str, delay: int = 30):
        """
        Schedule a chat room delete.
        :param room_id:
        :param delay:
        :return:
        """
        await asyncio.sleep(delay)
        if self.active_users_count.get(room_id, 0) == 0:
            await self.delete_chat_room(room_id)
            del self.deletion_timers[room_id]

    @sync_to_async
    def delete_chat_room(self, room_id):
        """
        Delete chat room.
        :param room_id:
        :return:
        """
        try:
            room = ChatRoom.objects.get(id=room_id)
            room.delete()
        except DoesNotExist:
            pass

    async def receive(self, text_data):
        """
        On message receive.
        """
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        room_id = text_data_json['room_id']
        session_id = self.scope['session'].session_key

        await self.save_message(room_id, message, session_id)

        # Send message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'session_id': session_id,
                'room_id': room_id
            }
        )

    @sync_to_async
    def save_message(self, room_id, message, session_id):
        """
        Saves message to the database.
        """
        room = ChatRoom.objects.get(id=room_id)
        Message(room=room, content=message, session_id=session_id).save()

    async def chat_message(self, event):
        """
        Sends message to the WebSocket.
        """
        message = event['message']
        session_id = event['session_id']
        room_id = event['room_id']

        await self.send(text_data=json.dumps({
            'message': message,
            'session_id': session_id,
            'room_id': room_id

        }))
