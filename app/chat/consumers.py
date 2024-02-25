import asyncio
import json

from asgiref.sync import sync_to_async
from bson import ObjectId
from channels.generic.websocket import AsyncWebsocketConsumer
from mongoengine import DoesNotExist

from chat.models import ChatRoom
from chat.services.chat_service import ChatService
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

    def initialize_connection_attributes(self):
        """Initializes connection attributes from the connecting request."""
        self.room_id = self.scope['url_route']['kwargs']['room_id']  # Extract room name from the URL route
        self.session_id = self.scope['session'].session_key
        self.room_group_name = f'chat_{self.room_id}'

    async def initialize_chat_service(self):
        """Initializes the chat service if not already initialized."""
        if not hasattr(self, 'chat_service'):
            r = await get_redis()
            self.chat_service = ChatService(redis=r, room_id=self.room_id, session_id=self.session_id)

    async def reject_connection(self):
        """Rejects the WebSocket connection with an appropriate message."""
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'redirect',
            'message': 'You cannot be connected to this room.'
        }))
        await self.close(code=4000)
        return

    async def accept_connection(self):
        """Accepts the WebSocket connection and performs necessary setup."""
        await self.chat_service.mark_as_connected()
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def handle_reconnect(self, is_reconnect):
        """Handles logic specific to users re-connecting to the chat."""
        if not is_reconnect:
            await self.chat_service.session_ids_append()
        else:
            await self.send(text_data=json.dumps({
                'type': 'reconnect',
                'message': ''
            }))

    async def manage_users_count_on_connection(self):
        """Manages user counts and related logic when a new connection is established."""
        users_count = await self.chat_service.get_users_count()
        if users_count < 2:
            await self.chat_service.incr_users_count()

    async def connect(self):
        """
        Called when the websocket is handshaking
        """
        self.initialize_connection_attributes()

        await self.initialize_chat_service()

        room = await self.chat_service.get_room_by_id(self.room_id)
        if room is None:
            await self.close()
            return

        is_already_connected = await self.chat_service.is_already_connected()
        is_reconnect = await self.chat_service.in_session_ids()
        is_room_not_full = await self.chat_service.session_ids_count() < 2
        should_accept = is_reconnect or (is_room_not_full and not is_reconnect)

        if not should_accept or is_already_connected:
            await self.reject_connection()

        await self.accept_connection()

        await self.handle_reconnect(is_reconnect)

        sessions_count = await self.chat_service.session_ids_count()

        if not is_reconnect and sessions_count == 2:
            print(f'JOIN SECOND USER: {self.session_id}')
            await self.join_second_user(room)

        self.cancel_user_removal(self.room_id)

        await self.manage_users_count_on_connection()

    async def join_second_user(self, room):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'second_user_joined_event',
                'message': 'Second user joined'
            }
        )
        await self.chat_service.join_second_user(room)

    async def second_user_joined_event(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'second_user_joined',
            'message': message
        }))

    async def disconnect(self, close_code):
        """
        Disconnect from chat.
        """
        await self.chat_service.unmark_as_connected()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print('DISCONNECT')
        if close_code != 4000:

            users_count = await self.chat_service.get_users_count()

            if users_count <= 1:
                await self.delete_chat_room()
                await self.chat_service.close_redis()
                del self.chat_service
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
        if self.chat_service.users_exists():
            await self.chat_service.decr_users_count()
            users_count = await self.chat_service.get_users_count()
            print(f'User left from room {room_id}\nUSERS COUNT: {users_count}')

            if users_count == 1:
                await self.end_chat_on_left(room_id)
                await self.delete_chat_room()

        await self.chat_service.close_redis()
        del self.chat_service

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

    async def delete_chat_room(self):
        """
        Delete chat room.
        :return:
        """
        if hasattr(self, 'chat_service'):
            await self.chat_service.delete_chat_data()

        self.deletion_timers.pop(self.room_id, None)

        print(f'ROOM DATA {self.room_id} DELETED')

    async def receive(self, text_data):
        """
        On message receive.
        """
        text_data_json = json.loads(text_data)
        message = text_data_json.get('message')
        room_id = text_data_json.get('room_id')
        action = text_data_json.get('action')
        ac_type = text_data_json.get('type')

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
            await self.chat_service.unmark_as_connected()
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
            await self.chat_service.save_message(message=message, room_id=room_id, session_id=self.session_id)

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
        await self.chat_service.unmark_as_connected()
        message = event['message']
        session_id = event['session_id']
        room_id = event['room_id']

        await self.send(text_data=json.dumps({
            'type': 'end_chat',
            'message': message,
            'session_id': session_id,
            'room_id': room_id

        }))

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
