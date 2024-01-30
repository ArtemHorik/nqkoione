import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    """
     WebSocket connections and messages handler for chat rooms.
    """
    async def connect(self):
        """
        Called when the websocket is handshaking as part of the connection process.
        """
        # Extract room name from the URL route
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

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

        # Send message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    async def chat_message(self, event):
        """
        Sends message to the WebSocket.
        """
        message = event['message']

        await self.send(text_data=json.dumps({
            'message': message
        }))
