from decouple import config
from django.test import TestCase
from mongoengine import connect, disconnect

from .models import ChatRoom, search_chat_room
from datetime import datetime


class ChatRoomModelTest(TestCase):

    def setUp(self):
        """
        ChatRoom instance setup.
        :return:
        """
        self.chatroom = ChatRoom(
            topic='Test Topic',
            creator_age='25-34',
            creator_gender='Male',
            search_gender='Female'
        )
        self.chatroom.save()

    def test_create_chatroom(self):
        """
        Tests that chatroom was created successfully.
        :return:
        """
        self.assertIsNotNone(self.chatroom.room_id)
        self.assertEqual(self.chatroom.topic, 'Test Topic')
        self.assertEqual(self.chatroom.creator_age, '25-34')
        self.assertEqual(self.chatroom.creator_gender, 'Male')
        self.assertEqual(self.chatroom.search_gender, 'Female')
        self.assertIsInstance(self.chatroom.created_at, datetime)
        self.assertFalse(self.chatroom.second_user_joined)

    def test_room_id_uniqueness(self):
        """
        Tests room_id uniqueness.
        :return:
        """
        chatroom2 = ChatRoom(
            topic='Flirt',
            creator_age='18-24',
            creator_gender='Female',
            search_gender='Male'
        )
        chatroom2.save()

        self.assertNotEqual(self.chatroom.room_id, chatroom2.room_id)

    def test_join_second_user(self):
        """
        Tests join_second_user method.
        :return:
        """
        self.chatroom.join_second_user()
        self.assertTrue(self.chatroom.second_user_joined)

    def tearDown(self):
        """
        Deletes chatroom after tests.
        :return:
        """
        ChatRoom.objects.all().delete()


class ChatRoomSearchTest(TestCase):

    topic1 = 'chat'
    topic2 = 'flirt'
    g_male = 'male'
    g_female = 'female'
    g_nqkoi = 'not-specified'

    @classmethod
    def setUpTestData(cls):
        """
        Setups test data.
        :return:
        """
        cls.chatroom_male_female = ChatRoom.objects.create(
            topic=cls.topic1,
            # creator_age='18-24',
            creator_gender=cls.g_male,
            search_gender=cls.g_female
        )
        cls.chatroom_nqkoi = ChatRoom.objects.create(
            topic=cls.topic1,
            creator_gender=cls.g_nqkoi,
            search_gender=cls.g_nqkoi
        )
        ChatRoom.objects.create(
            topic='flirt',
            # creator_age='18-24',
            creator_gender=cls.g_female,
            search_gender=cls.g_male
        )

        ChatRoom.objects.create(
            topic='flirt',
            # creator_age='18-24',
            creator_gender=cls.g_nqkoi,
            search_gender=cls.g_nqkoi
        )

    def test_search_chat_room_male_female(self):
        """
        Tests search room with topic chat and filter male/female.
        :return:
        """
        found_room = search_chat_room(self.topic1, my_gender=self.g_female, search_gender=self.g_male)
        self.assertEqual(self.chatroom_male_female, found_room)

        found_room = search_chat_room(self.topic1, my_gender=self.g_female, search_gender=self.g_nqkoi)
        self.assertEqual(self.chatroom_male_female, found_room)

        found_room = search_chat_room(self.topic1, my_gender=self.g_male, search_gender=self.g_female)
        self.assertNotEqual(self.chatroom_male_female, found_room)

        found_room = search_chat_room(self.topic1, my_gender=self.g_male, search_gender=self.g_nqkoi)
        self.assertNotEqual(self.chatroom_male_female, found_room)

        found_room = search_chat_room(self.topic1, my_gender=self.g_nqkoi, search_gender=self.g_nqkoi)
        self.assertNotEqual(self.chatroom_male_female, found_room)

    def test_search_chat_room_nqkoi(self):
        """
        Tests search room with topic chat and filter nqkoi.
        :return:
        """
        found_room = search_chat_room(self.topic1, my_gender=self.g_nqkoi, search_gender=self.g_nqkoi)
        self.assertEqual(self.chatroom_nqkoi, found_room)

        found_room = search_chat_room(self.topic1, my_gender=self.g_male, search_gender=self.g_nqkoi)
        self.assertNotEqual(self.chatroom_nqkoi, found_room)



    @classmethod
    def tearDownClass(cls):
        """DB clear after tests."""
        ChatRoom.objects.all().delete()
