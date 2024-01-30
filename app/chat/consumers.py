import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from chat.models import Message, ChatRoom


class ChatConsumer(AsyncWebsocketConsumer):
    """
     WebSocket connections and messages handler for chat rooms.
    """

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

        await self.accept()

    async def disconnect(self, close_code):
        """
        Disconnect from chat.
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )



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
