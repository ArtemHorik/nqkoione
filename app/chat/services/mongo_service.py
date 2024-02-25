from asgiref.sync import sync_to_async
from bson import ObjectId
from mongoengine import DoesNotExist

from chat.models import ChatRoom, Message


class MongoService:

    @staticmethod
    def delete_room_by_id(room_id: str):
        try:
            room = ChatRoom.objects.get(id=room_id)
            room.delete()
            print(f'ROOM {room_id} DELETED FROM DB')
        except DoesNotExist:
            pass

    @staticmethod
    def save_message(message: str, room_id: str, session_id: str):
        if room_id:
            room = ChatRoom.objects.get(id=room_id)
            Message(room=room, content=message, session_id=session_id).save()

    @staticmethod
    def get_room_by_id(room_id: str):
        room_id_obj = ObjectId(room_id)
        try:
            return ChatRoom.objects.get(id=room_id_obj)
        except DoesNotExist:
            return None


class AsyncMongoService:

    @staticmethod
    async def delete_room_by_id(room_id):
        await sync_to_async(MongoService.delete_room_by_id)(room_id)

    @staticmethod
    async def save_message(message, room_id, session_id):
        await sync_to_async(MongoService.save_message)(message, room_id, session_id)

    @staticmethod
    async def get_room_by_id(room_id):
        return await sync_to_async(MongoService.get_room_by_id)(room_id)

    @staticmethod
    async def join_second_user(room: ChatRoom):
        await sync_to_async(room.join_second_user)()
