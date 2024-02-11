import asyncio
import json

from asgiref.sync import sync_to_async
from bson import ObjectId
from channels.generic.websocket import AsyncWebsocketConsumer
from mongoengine import DoesNotExist

from chat.models import Message, ChatRoom


class ChatConsumer(AsyncWebsocketConsumer):
    """
     WebSocket connections and messages handler for chat rooms.
    """
    active_users_count = {}
    deletion_timers = {}
    session_ids = {}

    async def connect(self):
        """
        Called when the websocket is handshaking
        """
        # Extract room name from the URL route
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        session_id = self.scope['session'].session_key

        room = await self.get_room(self.room_id)
        if room is None:
            await self.close()
            return

        if self.room_id not in self.session_ids:
            self.session_ids[self.room_id] = []

        is_reconnect = session_id in self.session_ids[self.room_id]
        is_room_not_full = len(self.session_ids[self.room_id]) < 2
        should_accept = is_reconnect or (is_room_not_full and session_id not in self.session_ids[self.room_id])

        if not should_accept:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        if not is_reconnect:
            self.session_ids[self.room_id].append(session_id)
        else:
            await self.send(text_data=json.dumps({
                'type': 'reconnect',
                'message': ''
            }))

        if not is_reconnect and len(self.session_ids[self.room_id]) == 2:
            print(f'JOIN SECOND USER: {session_id}')
            await self.join_second_user(room)

        self.cancel_user_removal(self.room_id)

        if self.active_users_count.get(self.room_id, 0) < 2:
            self.active_users_count[self.room_id] = self.active_users_count.get(self.room_id, 0) + 1

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
        if self.active_users_count.get(self.room_id, 0) <= 1:
            await self.delete_chat_room(self.room_id)
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
        if room_id in self.active_users_count:
            self.active_users_count[room_id] -= 1
            print(f'User left from room {room_id}\nUSERS COUNT: {self.active_users_count[room_id]}')
            if self.active_users_count[room_id] == 1:
                await self.end_chat_on_left(room_id)
                await self.delete_chat_room(room_id)

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
    def delete_chat_room(self, room_id):
        """
        Delete chat room.
        :param room_id:
        :return:
        """
        self.deletion_timers.pop(room_id, None)
        self.active_users_count.pop(room_id, None)
        self.session_ids.pop(room_id, None)
        try:
            room = ChatRoom.objects.get(id=room_id)
            room.delete()
        except DoesNotExist:
            pass
        print(f'ROOM {room_id} DELETED')
        print(f'SESSIONS: {self.session_ids}')
        print(f'USERS: {self.active_users_count}')

    async def receive(self, text_data):
        """
        On message receive.
        """
        text_data_json = json.loads(text_data)
        message = text_data_json.get('message')
        room_id = text_data_json.get('room_id')
        session_id = self.scope['session'].session_key
        action = text_data_json.get('action')

        if action == 'end_chat':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'end_chat',
                    'message': 'Chat ended',
                    'session_id': session_id,
                    'room_id': room_id
                }
            )
            print('DELETING CHAT')
            await self.delete_chat_room(room_id)

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
