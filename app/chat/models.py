from mongoengine import Document, StringField, ListField, DateTimeField, ReferenceField, CASCADE
from datetime import datetime


class ChatRoom(Document):
    title = StringField(max_length=255, required=True)
    topic = StringField(max_length=50, required=True)
    allowed_genders = ListField(StringField(max_length=1), default=list)
    age_range = ListField(StringField(max_length=10), default=list)

    created_at = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            'title',
            'topic',
            'allowed_genders',
            ('age_range', 'allowed_genders'),
        ]
    }


class Message(Document):
    room = ReferenceField(ChatRoom, required=True, reverse_delete_rule=CASCADE)
    session_id = StringField(max_length=255, required=True)
    content = StringField(required=True)
    timestamp = DateTimeField(default=datetime.now)

    meta = {
        'indexes': [
            'timestamp',
            'session_id',
            'room',

            ('room', 'timestamp'),
        ],
        'ordering': ['-timestamp']
    }
