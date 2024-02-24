import json

from bson import ObjectId
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from mongoengine import DoesNotExist, ValidationError

from .models import ChatRoom, Message, search_chat_room, create_chat_room


def index(request):
    """
    Main page view.
    :param request:
    :return:
    """
    request.session.create()
    return render(request, 'index.html', {'users_in_chat': ChatRoom.objects.count()})


def room(request, room_id):
    """
    Chat room view.
    :param request:
    :param room_id:
    :return:
    """
    try:
        chat_room: ChatRoom = ChatRoom.objects.get(id=room_id)
    except DoesNotExist:
        return redirect('index')

    return render(request, 'room.html', {
        'room_id': room_id,
        'session_key': request.session.session_key,
        'filter_data': request.session['filter_data']
    })


@require_POST
def search_or_create_chat_room(request):
    """
    Searching chat room.
    :param request:
    :return:
    """
    try:
        data = json.loads(request.body)
        topic = data.get('topic')
        creator_gender = data.get('my_gender')
        search_gender = data.get('search_gender')
        request.session['filter_data'] = data

        print(data)

        chat_room = search_chat_room(topic, creator_gender, search_gender)
        if not chat_room or chat_room.is_full():
            chat_room = create_chat_room(topic, creator_gender, search_gender)

        return JsonResponse({'status': 'success', 'room_id': str(chat_room.id)})

    except Exception as e:
        print(e)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
def post_message(request):
    """
    Posting a new message to a room.
    :param request:
    :return:
    """
    try:
        data = json.loads(request.body)
        room_id = data['room_id']
        session_id = data['session_id']
        content = data['content']

        room = ChatRoom.objects.get(id=room_id)

        # Create and save the new message
        message = Message(room=room, session_id=session_id, content=content)
        message.save()

        return JsonResponse({'status': 'success', 'message_id': str(message.id)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def check_room_status(request, room_id):
    try:
        room = ChatRoom.objects.get(id=room_id)
        return JsonResponse({'second_user_joined': room.second_user_joined})
    except DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)


def join_room(request, room_id):
    try:
        room = ChatRoom.objects.get(id=room_id)
        room.join_second_user()
        return JsonResponse({'success': 'User joined the room'})
    except DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)


def get_messages(request, room_id):
    """
    Retrieves messages for room.
    :param request:
    :param room_id:
    :return:
    """
    try:
        try:
            room_id_obj = ObjectId(room_id)
        except ValidationError:
            return JsonResponse({'error': 'Invalid room ID'}, status=400)

        try:
            room = ChatRoom.objects.get(id=room_id_obj)
        except DoesNotExist:
            return JsonResponse({'error': 'Room not found'}, status=404)

        messages = Message.objects.filter(room=room).order_by('timestamp')

        messages_data = [{
            'session_id': message.session_id,
            'message': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for message in messages]

        return JsonResponse(
            {'status': 'success', 'messages': messages_data, 'second_user_joined': room.second_user_joined})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def end_chat(request):
    """
    Ends chat.
    :param request:
    :return:
    """
    try:
        data = json.loads(request.body)
        room_id = data['room_id']
        chat = ChatRoom.objects.get(id=room_id)
        chat.is_active = False
        chat.save()
    except DoesNotExist:
        return JsonResponse({'statur': 'error', 'message': 'Room does not exists'}, status=500)
    return JsonResponse({'status': 'success'})


def get_users_in_chat(request):
    """
    Returns HTML span with chats online count.
    :param request:
    :return:
    """
    return HttpResponse(f'<span style="padding-left: 5px">{ChatRoom.objects.count()}</span>')
