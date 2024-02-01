import uuid

from mongoengine import Document, StringField, ListField, DateTimeField, ReferenceField, CASCADE, UUIDField, \
    BooleanField
from datetime import datetime


class ChatRoom(Document):
    room_id = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    second_user_joined = BooleanField(default=False)
    topic = StringField(max_length=50, required=True)

    age_range = ListField(StringField(max_length=15), default=list)
    creator_age = StringField(max_length=15)
    creator_gender = StringField(max_length=15)
    search_gender = StringField(max_length=15)
    # allowed_genders = ListField(StringField(max_length=20), default=list)

    created_at = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            {'fields': ['room_id'], 'name': 'room_id_index'},
            'topic',
            'age_range',
            'creator_age',
            'search_gender',
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
    content = StringField(required=True)
    timestamp = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            'timestamp',
            # 'session_id',
            'room',

            ('room', 'timestamp'),
        ],
        'ordering': ['-timestamp']
    }


def search_chat_room(topic, my_gender, search_gender=None, partner_age=None):
    if my_gender == 'not-specified':
        chat_room = ChatRoom.objects.filter(topic=topic, search_gender='not-specified', second_user_joined=False).first()
    elif search_gender == 'not-specified':
        chat_room = ChatRoom.objects.filter(topic=topic, second_user_joined=False).first()
    else:
        # all filters
        chat_room = ChatRoom.objects.filter(
            topic=topic,
            creator_gender=search_gender,
            search_gender__in=['not-specified', my_gender],
            second_user_joined=False,
            # age_range=partner_age
        ).first()

    return chat_room


def create_chat_room(topic, my_gender, search_gender=None,):
    new_room = ChatRoom(
        topic=topic,
        creator_gender=my_gender,
        search_gender=search_gender
        # allowed_genders=[my_gender] if my_gender != 'някой' else ['някой'],
        # age_range=partner_age
    )
    new_room.save()
    return new_room
