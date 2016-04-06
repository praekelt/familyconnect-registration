import json

from django.test import TestCase
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from .models import Record


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()


class AuthenticatedAPITestCase(APITestCase):

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()

        # Normal User setup
        self.normalusername = 'testnormaluser'
        self.normalpassword = 'testnormalpass'
        self.normaluser = User.objects.create_user(
            self.normalusername,
            'testnormaluser@example.com',
            self.normalpassword)
        normaltoken = Token.objects.create(user=self.normaluser)
        self.normaltoken = normaltoken.key
        self.normalclient.credentials(
            HTTP_AUTHORIZATION='Token ' + self.normaltoken)

        # Admin User setup
        self.adminusername = 'testadminuser'
        self.adminpassword = 'testadminpass'
        self.adminuser = User.objects.create_superuser(
            self.adminusername,
            'testadminuser@example.com',
            self.adminpassword)
        admintoken = Token.objects.create(user=self.adminuser)
        self.admintoken = admintoken.key
        self.adminclient.credentials(
            HTTP_AUTHORIZATION='Token ' + self.admintoken)

    def tearDown(self):
        pass


class TestRecordCreation(AuthenticatedAPITestCase):

    def test_record_create_unique_ten_digit(self):
        # Setup
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "health_id"
        }
        # Execute
        Record.objects.create(**data)
        # Check
        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 10)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")
        self.assertEqual(d.length, 10)
        self.assertEqual(d.write_to, "health_id")

    def test_record_create_unique_ten_digit_two(self):
        # Setup
        data = {
            "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
            "write_to": "health_id"
        }
        Record.objects.create(**data)
        data2 = {
            "identity": "c304f463-6db4-4f89-a095-46319da06ac9",
            "write_to": "health_id"
        }
        # Execute
        Record.objects.create(**data2)
        # Check
        self.assertEqual(Record.objects.all().count(), 2)


class TestRecordAPI(AuthenticatedAPITestCase):

    def test_webook_api_create_unique_ten_digit(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.added",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
                "write_to": "health_id"
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 10)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")

    def test_webook_api_create_unique_twelve_digit(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.added",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "identity": "9d02ae1a-16e4-4674-abdc-daf9cce9c52d",
                "write_to": "health_id",
                "length": 12
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Record.objects.last()
        self.assertIsNotNone(d.id)
        self.assertEqual(len(str(d.id)), 12)
        self.assertEqual(str(d.identity),
                         "9d02ae1a-16e4-4674-abdc-daf9cce9c52d")

    def test_webook_api_missing_identity(self):
        # Setup
        post_webhook = {
            "hook": {
                "id": 2,
                "event": "identity.added",
                "target": "http://example.com/api/v1/uniqueid/"
            },
            "data": {
                "frank": "bob",
                "write_to": "health_id"
            }
        }
        # Execute
        response = self.normalclient.post('/api/v1/uniqueid/',
                                          json.dumps(post_webhook),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'identity': [
            'This field is required.']})
