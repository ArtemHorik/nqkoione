import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ChatRoom, Message


def index(request):
    """
    Main page view.
    :param request:
    :return:
    """
    return render(request, 'index.html')

def room(request, room_name):
    """
    Chat room view.
    :param request:
    :param room_name:
    :return:
    """
    return render(request, 'room.html', {
        'room_name': room_name
    })

@require_POST
def create_chat_room(request):
    """
    Creating chat room.
    :param request:
    :return:
    """
    data = request.POST
    room_title = data.get('title')
    topic = data.get('topic')
    allowed_genders = data.get('allowedGenders', [])
    age_range = data.get('ageRange', [])

    new_room = ChatRoom(
        title=room_title,
        topic=topic,
        allowed_genders=allowed_genders,
        age_range=age_range
    )
    new_room.save()

    return JsonResponse({'status': 'success', 'room_id': str(new_room.id)})


@require_POST
def search_chat_rooms(request):
    """
    Searching chat room.
    :param request:
    :return:
    """
    try:
        data = json.loads(request.body)
        topic = data.get('topic')
        gender = data.get('gender')
        partner_gender = data.get('partnerGender')
        partner_ages = data.get('partnerAges', [])

        # Find matching chat rooms
        query = {
            'topic': topic,
            'allowed_genders__in': [partner_gender, 'X']
        }

        # Age filter if partner_ages are provided
        if partner_ages:
            query['age_range__in'] = partner_ages

        chat_rooms = ChatRoom.objects(**query)

        # Serialize the chat rooms data for the response
        chat_rooms_data = [{
            'title': room.title,
            'created_at': room.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for room in chat_rooms]

        return JsonResponse({'chat_rooms': chat_rooms_data})
    except Exception as e:
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

@require_POST
def get_messages(request, room_id):
    """
    Retrieves messages for room.
    :param request:
    :param room_id:
    :return:
    """
    try:
        messages = Message.objects.filter(room__id=room_id).order_by('-timestamp')

        messages_data = [{
            'session_id': message.session_id,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for message in messages]

        return JsonResponse({'status': 'success', 'messages': messages_data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
