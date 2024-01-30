from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('room/<str:room_name>/', views.room, name='room'),
    path('search', views.search_chat_rooms, name='search'),
    path('post_message/', views.post_message, name='post_message'),
    path('get_messages/<str:room_id>/', views.get_messages, name='get_messages'),
]
