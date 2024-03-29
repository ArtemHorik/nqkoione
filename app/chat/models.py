import uuid

from mongoengine import Document, StringField, ListField, DateTimeField, ReferenceField, CASCADE, UUIDField, \
    BooleanField
from datetime import datetime


class ChatRoom(Document):
    room_id = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    second_user_joined = BooleanField(default=False)

    topic = StringField(max_length=50, required=True)

    creator_gender = StringField(max_length=15)
    search_gender = StringField(max_length=15)

    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['room_id'], 'name': 'room_id_index'},
            'topic',
            # 'age_range',
            # 'creator_age',
            'search_gender',
            'creator_gender',
            'second_user_joined'
        ]
    }

    def join_second_user(self):
        if not self.second_user_joined:
            self.second_user_joined = True
            self.save()

    def is_full(self):
        return self.second_user_joined


class Message(Document):
    room = ReferenceField(ChatRoom, required=True, reverse_delete_rule=CASCADE)
    session_id = StringField(max_length=255, required=True)
    content = StringField(required=True, max_length=1500)
    timestamp = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            'timestamp',
            'room',

            ('room', 'timestamp'),
        ],
        'ordering': ['-timestamp']
    }


def search_chat_room(topic, my_gender, search_gender=None):
    print(topic, my_gender, search_gender)
    if my_gender == 'not-specified':
        chat_room = ChatRoom.objects.filter(topic=topic, creator_gender=my_gender,
                                            second_user_joined=False).first()
    elif search_gender == 'not-specified':
        chat_room = ChatRoom.objects.filter(topic=topic, creator_gender__in=['male', 'female'],
                                            search_gender__in=['not-specified', my_gender],
                                            second_user_joined=False).first()
    else:
        # all filters
        chat_room = ChatRoom.objects.filter(
            topic=topic,
            creator_gender=search_gender,
            search_gender__in=['not-specified', my_gender],
            second_user_joined=False,
        ).first()

    return chat_room


def create_chat_room(topic, my_gender, search_gender=None, ):
    new_room = ChatRoom(
        topic=topic,
        creator_gender=my_gender,
        search_gender=search_gender
    )
    new_room.save()
    return new_room
