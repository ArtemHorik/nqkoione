import asyncio
import json

from asgiref.sync import sync_to_async
from bson import ObjectId
from channels.generic.websocket import AsyncWebsocketConsumer
from mongoengine import DoesNotExist

from chat.models import Message, ChatRoom
from config.redis_pool import get_redis


class ChatConsumer(AsyncWebsocketConsumer):
    """
     WebSocket connections and messages handler for chat rooms.
    """
    deletion_timers = {}

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.room_id = None
        self.session_id = None
        self.room_group_name = None
        # self.redis = None
        self.users_count = 0

    async def fetch_users_count(self):
        users_count = await self.redis.get(f'users_count:{self.room_id}')
        self.users_count = int(users_count) if users_count else 0

    async def decr_users_count(self):
        await self.redis.decr(f'users_count:{self.room_id}', 1)
        await self.fetch_users_count()

    async def incr_users_count(self):
        await self.redis.incr(f'users_count:{self.room_id}', 1)
        await self.fetch_users_count()

    async def in_session_ids(self) -> bool:
        return bool(await self.redis.sismember(f'sessions:{self.room_id}', self.session_id))

    async def session_ids_append(self, session_id) -> None:
        if await self.session_ids_count() < 2:
            await self.redis.sadd(f'sessions:{self.room_id}', session_id)
        else:
            raise ValueError('You cannot have more than two sessions.')

    async def session_ids_count(self) -> int:
        return await self.redis.scard(f'sessions:{self.room_id}')

    async def close_redis(self):
        await self.redis.close()
        del self.redis
        print(f'REDIS CLOSED FOR SESSION ID {self.session_id}')

    async def delete_redis_data(self):
        await self.redis.delete(f'sessions:{self.room_id}', f'users_count:{self.room_id}')
        print(self.redis.get(f'sessions:{self.room_id}'))
        print(self.redis.get(f'users_count:{self.room_id}'))

    async def connect(self):
        """
        Called when the websocket is handshaking
        """
        # Extract room name from the URL route
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.session_id = self.scope['session'].session_key
        self.room_group_name = f'chat_{self.room_id}'

        room = await self.get_room(self.room_id)
        if room is None:
            await self.close()
            return

        if not hasattr(self, 'redis'):
            self.redis = await get_redis()

        is_reconnect = await self.in_session_ids()
        is_room_not_full = await self.session_ids_count() < 2
        should_accept = is_reconnect or (is_room_not_full and not is_reconnect)

        if not should_accept:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        if not is_reconnect:
            await self.session_ids_append(self.session_id)
        else:
            await self.send(text_data=json.dumps({
                'type': 'reconnect',
                'message': ''
            }))

        sessions_count = await self.session_ids_count()

        if not is_reconnect and sessions_count == 2:
            print(f'JOIN SECOND USER: {self.session_id}')
            await self.join_second_user(room)

        self.cancel_user_removal(self.room_id)

        await self.fetch_users_count()

        if self.users_count < 2:
            await self.incr_users_count()

    async def join_second_user(self, room):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'second_user_joined_event',
                'message': 'Second user joined'
            }
        )
        room.second_user_joined = True
        await sync_to_async(room.save)()

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
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print('DISCONNECT')

        await self.fetch_users_count()

        if self.users_count <= 1:
            await self.delete_chat_room()
        else:
            self.schedule_user_removal(self.room_id)

    def schedule_user_removal(self, room_id):
        """Starts timer if user didn't reconnect."""
        timer = asyncio.get_event_loop().call_later(30, asyncio.create_task, self.remove_user(room_id))
        self.deletion_timers[room_id] = timer

    def cancel_user_removal(self, room_id):
        """Cancels user remover if reconnected."""
        timer = self.deletion_timers.get(room_id)
        if timer:
            timer.cancel()
            del self.deletion_timers[room_id]

    async def remove_user(self, room_id):
        """Removes user after a timer."""
        if await self.redis.exists(f'users_count:{self.room_id}'):
            await self.decr_users_count()

            print(f'User left from room {room_id}\nUSERS COUNT: {self.users_count}')

            if self.users_count == 1:
                await self.end_chat_on_left(room_id)
                await self.delete_chat_room()
        if hasattr(self, 'redis'):
            await self.close_redis()

    async def end_chat_on_left(self, room_id):
        """
        Sends end chat message event to all.
        """

        session_id = 'system'
        print('ENDING CHAT')
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'end_chat',
                'message': 'Chat ended',
                'session_id': session_id,
                'room_id': room_id
            }
        )

    @sync_to_async
    def delete_room_from_db(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            room.delete()
            print(f'ROOM {self.room_id} DELETED FROM DB')
        except DoesNotExist:
            pass

    async def delete_chat_room(self):
        """
        Delete chat room.
        :return:
        """
        await self.delete_redis_data()
        if hasattr(self, 'redis'):
            await self.close_redis()

        self.deletion_timers.pop(self.room_id, None)
        await self.delete_room_from_db()

        print(f'ROOM {self.room_id} DELETED')

    async def receive(self, text_data):
        """
        On message receive.
        """
        text_data_json = json.loads(text_data)
        message = text_data_json.get('message')
        room_id = text_data_json.get('room_id')
        action = text_data_json.get('action')

        if action == 'end_chat':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'end_chat',
                    'message': 'Chat ended',
                    'session_id': self.session_id,
                    'room_id': room_id
                }
            )
            print('DELETING CHAT')
            await self.delete_chat_room()

        elif action == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_message',
                    'message': message,
                    'sender_channel_name': self.channel_name
                }
            )

        else:
            await self.save_message(room_id, message, self.session_id)

            # Send message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'session_id': self.session_id,
                    'room_id': room_id
                }
            )

    async def typing_message(self, event):
        """
        Sends a user typing event message
        :param event:
        :return:
        """
        if event['sender_channel_name'] != self.channel_name:  # Don't send to ourselves
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'message': event['message']
            }))

    async def end_chat(self, event):
        """
        Sends end chat message to the WebSocket.
        """
        message = event['message']
        session_id = event['session_id']
        room_id = event['room_id']

        await self.send(text_data=json.dumps({
            'type': 'end_chat',
            'message': message,
            'session_id': session_id,
            'room_id': room_id

        }))

    @sync_to_async
    def save_message(self, room_id, message, session_id):
        """
        Saves message to the database.
        """
        if room_id:
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
