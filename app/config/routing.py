from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from app.chat.consumers import ChatConsumer

websocket_urlpatterns = [
    path('ws/chat/<room_name>/', ChatConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': URLRouter(websocket_urlpatterns)
})
