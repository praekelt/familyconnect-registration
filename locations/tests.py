from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
import responses
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from seed_services_client import IdentityStoreApiClient

from .models import Parish
from .tasks import sync_locations


class TestLocations(APITestCase):
    def login(self):
        """
        Creates a user, creates a token for that user, and attaches that token
        to the http client, so that all future requests are authorized.
        """
        user = User.objects.create_user(
            'user', 'testuser@example.org', 'password')
        token = Token.objects.create(user=user)
        self.client.credentials(
            HTTP_AUTHORIZATION='Token {}'.format(token.key))

    def test_parish_string_representation(self):
        """
        The Parish model should have an appropriate string representation.
        """
        parish = Parish.objects.create(name='Kawaaga')
        self.assertEqual(str(parish), 'Kawaaga')

    def test_search_authorization_required(self):
        """
        If no autorization token is provided, the client should not be able to
        access the view.
        """
        response = self.client.get(
            reverse('locations-list'), {'name': 'foo'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_no_results(self):
        """
        An empty list should be returned if there are no search results.
        """
        self.login()
        response = self.client.get(
            reverse('locations-list'), {'name': 'Kawaaga'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_search_with_results(self):
        """
        If there are multiple results, they should be returned. Unrelated
        locations should not be returned. They should be returned in order
        of relevance.
        """
        self.login()

        Parish.objects.create(name='Kawakawa'),
        Parish.objects.create(name='Kawaaga'),
        Parish.objects.create(name='Naluwoli'),

        response = self.client.get(
            reverse('locations-list'), {'name': 'kawaga'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [
            {'name': 'Kawaaga'}, {'name': 'Kawakawa'}])

    def test_search_no_query_parameter(self):
        """
        If no query parameter is present to search on, then no results should
        be returned.
        """
        self.login()

        Parish.objects.create(name='Kawakawa'),
        Parish.objects.create(name='Kawaaga'),
        Parish.objects.create(name='Naluwoli'),

        response = self.client.get(reverse('locations-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])


class TestTasks(TestCase):
    identity_list_page_one = {
        'next':
            'http://localhost:8001/api/v1/identities/?limit=2&offset=2',
        'results': [
            {'details': {'parish': 'Kawaaga'}},
            {'details': {}},
        ],
    }

    identity_list_page_two = {
        'next': None,
        'results': [
            {'details': {'parish': 'Naluwoli'}},
            {'details': {'parish': 'Kawaaga'}},
        ],
    }

    identity_list_caps = {
        'next': None,
        'results': [
            {'details': {'parish': 'naluwoli'}},
            {'details': {'parish': 'KAWAAGA'}},
        ],
    }

    @responses.activate
    def test_sync_locations_get_identities(self):
        """
        get_identities should iterate through the identities, even if split
        over multiple pages.
        """
        responses.add(
            responses.GET, 'http://localhost:8001/api/v1/identities/',
            json=self.identity_list_page_one, match_querystring=True
        )
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/?limit=2&offset=2',
            json=self.identity_list_page_two, match_querystring=True
        )

        client = IdentityStoreApiClient('foo', 'http://localhost:8001/api/v1')
        identities = list(sync_locations.get_identities(client))
        self.assertEqual(identities, [
            {'details': {'parish': 'Kawaaga'}},
            {'details': {}},
            {'details': {'parish': 'Naluwoli'}},
            {'details': {'parish': 'Kawaaga'}},
        ])

    @responses.activate
    def test_sync_locations_creates_objects(self):
        """
        Running the sync_locations task should create the applicable locations
        """
        responses.add(
            responses.GET, 'http://localhost:8001/api/v1/identities/',
            json=self.identity_list_page_one, match_querystring=True
        )
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/?limit=2&offset=2',
            json=self.identity_list_page_two, match_querystring=True
        )

        self.assertEqual(Parish.objects.count(), 0)

        result = sync_locations.apply_async()

        self.assertEqual(int(result.get()), 2)
        self.assertEqual(Parish.objects.count(), 2)
        self.assertTrue(Parish.objects.filter(name='Kawaaga').exists())
        self.assertTrue(Parish.objects.filter(name='Naluwoli').exists())

    @responses.activate
    def test_sync_locations_name_normalised(self):
        """
        When syncing locations, the names of the locations should be synced
        to title case.
        """
        responses.add(
            responses.GET, 'http://localhost:8001/api/v1/identities/',
            json=self.identity_list_caps, match_querystring=True
        )

        self.assertEqual(Parish.objects.count(), 0)

        result = sync_locations.apply_async()

        self.assertEqual(int(result.get()), 2)
        self.assertEqual(Parish.objects.count(), 2)
        self.assertTrue(Parish.objects.filter(name='Kawaaga').exists())
        self.assertTrue(Parish.objects.filter(name='Naluwoli').exists())
