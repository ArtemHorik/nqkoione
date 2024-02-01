import json

from django.test import TestCase, Client
from django.urls import reverse

from .models import ChatRoom, search_chat_room, create_chat_room
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


class IndexViewTests(TestCase):
    def setUp(self):
        """Setups Client for views tests."""
        self.client = Client()

    def test_index_view_template(self):
        """Tests template of index page view."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')


class SearchOrCreateChatRoomTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.topic = "chat"
        self.gender = "male"
        self.search_gender = "female"

    def test_search_existing_chat_room(self):
        """
        Tests existing chat room search
        :return:
        """
        existing_room = create_chat_room(topic=self.topic, my_gender=self.gender, search_gender=self.search_gender)

        data = json.dumps({
            'topic': self.topic,
            'my_gender': self.search_gender,
            'search_gender': self.gender
        })

        response = self.client.post(reverse('search'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)

        self.assertIn('room_id', response_data, "Response does not contain 'room_id'.")

        # Comparing room_id
        self.assertEqual(str(existing_room.id), response_data['room_id'],
                         "The room_id in the response does not match the existing room.")

    def test_create_new_chat_room(self):
        """
        Tests creating new chat with flirt theme
        :return:
        """
        new_topic = "flirt"
        data = json.dumps({
            'topic': new_topic,
            'my_gender': self.gender,
            'search_gender': self.search_gender
        })
        response = self.client.post(reverse('search'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # Check that new room was created
        created_room = ChatRoom.objects.filter(topic=new_topic, creator_gender=self.gender,
                                               search_gender=self.search_gender).first()
        self.assertIsNotNone(created_room, "The chat room was not created.")

    @classmethod
    def tearDownClass(cls):
        """DB clear after tests."""
        ChatRoom.objects.all().delete()
