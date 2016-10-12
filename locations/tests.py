from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Parish


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
