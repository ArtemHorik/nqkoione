from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('room/<str:room_id>/', views.room, name='room'),
    path('search', views.search_or_create_chat_room, name='search'),
    path('post_message/', views.post_message, name='post_message'),
    path('get_messages/<room_id>/', views.get_messages, name='get_messages'),

    path('api/check_room_status/<int:room_id>/', views.check_room_status, name='check_room_status'),
    path('api/join_room/<int:room_id>/', views.join_room, name='join_room'),
    path('api/end_chat/', views.end_chat, name='end_chat'),
    path('api/get_users_in_chat/', views.get_users_in_chat, name='get_users_in_chat')
]
