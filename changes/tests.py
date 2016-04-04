import datetime
import json
import responses

from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved

from familyconnect_registration import utils
from registrations.models import (Source, Registration, SubscriptionRequest,
                                  registration_post_save)
from .models import Change, change_post_save
from .tasks import implement_action


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()
        self.otherclient = APIClient()
        utils.get_today = override_get_today


class AuthenticatedAPITestCase(APITestCase):

    def _replace_post_save_hooks_change(self):
        def has_listeners():
            return post_save.has_listeners(Change)
        assert has_listeners(), (
            "Change model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=change_post_save,
                             sender=Change)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Change model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_change(self):
        def has_listeners():
            return post_save.has_listeners(Change)
        assert not has_listeners(), (
            "Change model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(change_post_save, sender=Change)

    def _replace_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
        assert has_listeners(), (
            "Registration model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=registration_post_save,
                             sender=Registration)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Registration model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_registration(self):
        def has_listeners():
            return post_save.has_listeners(Registration)
        assert not has_listeners(), (
            "Registration model still has post_save listeners. Make sure"
            " helpers removed them properly in earlier tests.")
        post_save.connect(registration_post_save, sender=Registration)

    def make_source_adminuser(self):
        data = {
            "name": "test_source_adminuser",
            "authority": "hw_full",
            "user": User.objects.get(username='testadminuser')
        }
        return Source.objects.create(**data)

    def make_source_normaluser(self):
        data = {
            "name": "test_source_normaluser",
            "authority": "patient",
            "user": User.objects.get(username='testnormaluser')
        }
        return Source.objects.create(**data)

    def make_change_adminuser(self):
        data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "change_language",
            "data": {"test_adminuser_change": "test_adminuser_changed"},
            "source": self.make_source_adminuser()
        }
        return Change.objects.create(**data)

    def make_change_normaluser(self):
        data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "change_language",
            "data": {"test_normaluser_change": "test_normaluser_changed"},
            "source": self.make_source_normaluser()
        }
        return Change.objects.create(**data)

    def make_registration_mother(self):
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {
                "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
                "receiver_id": "mother01-63e2-4acc-9b94-26663b9bc267",
                "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
                "language": "eng_UG",
                "msg_type": "text",
                "last_period_date": "20150202",
                "msg_receiver": "mother_to_be",
                "hoh_name": "bob",
                "hoh_surname": "the builder",
                "mama_name": "sue",
                "mama_surname": "zin",
                "mama_id_type": "ugandan_id",
                "mama_id_no": "12345"
            },
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**registration_data)

    def make_registration_hoh(self):
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {
                "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
                "receiver_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
                "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
                "language": "eng_UG",
                "msg_type": "text",
                "last_period_date": "20150202",
                "msg_receiver": "head_of_household",
                "hoh_name": "bob",
                "hoh_surname": "the builder",
                "mama_name": "sue",
                "mama_surname": "zin",
                "mama_id_type": "ugandan_id",
                "mama_id_no": "12345"
            },
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**registration_data)

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self._replace_post_save_hooks_change()
        self._replace_post_save_hooks_registration()

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
        self._restore_post_save_hooks_change()
        self._restore_post_save_hooks_registration()


class TestLogin(AuthenticatedAPITestCase):

    def test_login_normaluser(self):
        """ Test that normaluser can login successfully
        """
        # Setup
        post_auth = {"username": "testnormaluser",
                     "password": "testnormalpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNotNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(
            request.status_code, 200,
            "Status code on /api/token-auth was %s (should be 200)."
            % request.status_code)

    def test_login_adminuser(self):
        """ Test that adminuser can login successfully
        """
        # Setup
        post_auth = {"username": "testadminuser",
                     "password": "testadminpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNotNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(
            request.status_code, 200,
            "Status code on /api/token-auth was %s (should be 200)."
            % request.status_code)

    def test_login_adminuser_wrong_password(self):
        """ Test that adminuser cannot log in with wrong password
        """
        # Setup
        post_auth = {"username": "testadminuser",
                     "password": "wrongpass"}
        # Execute
        request = self.client.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(request.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_otheruser(self):
        """ Test that an unknown user cannot log in
        """
        # Setup
        post_auth = {"username": "testotheruser",
                     "password": "testotherpass"}
        # Execute
        request = self.otherclient.post(
            '/api/token-auth/', post_auth)
        token = request.data.get('token', None)
        # Check
        self.assertIsNone(
            token, "Could not receive authentication token on login post.")
        self.assertEqual(request.status_code, status.HTTP_400_BAD_REQUEST)


class TestChangeAPI(AuthenticatedAPITestCase):

    def test_get_change_adminuser(self):
        # Setup
        change = self.make_change_adminuser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/change/%s/' % change.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_change_normaluser(self):
        # Setup
        change = self.make_change_normaluser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/change/%s/' % change.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_change_adminuser(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/change/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_change_normaluser(self):
        # Setup
        self.make_source_normaluser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.normalclient.post('/api/v1/change/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_normaluser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_change_set_readonly_field(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": "change_language",
            "data": {"test_key1": "test_value1"},
            "validated": True
        }
        # Execute
        response = self.adminclient.post('/api/v1/change/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Change.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.action, 'change_language')
        self.assertEqual(d.validated, False)  # Should ignore True post_data
        self.assertEqual(d.data, {"test_key1": "test_value1"})


class TestRegistrationCreation(AuthenticatedAPITestCase):

    def test_make_registration_mother(self):
        # Setup
        # Execute
        self.make_registration_mother()
        # Test
        d = Registration.objects.last()
        self.assertEqual(d.mother_id, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.data["msg_receiver"], "mother_to_be")


class TestChangeBaby(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_change_baby(self):
        # Setup
        # make registration
        self.make_registration_mother()
        # make change object
        change_data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "change_baby",
            "data": {},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "subscription1-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_UG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % change_data[
                "mother_id"],
            json={
                "id": change_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+256720000222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "preferred_language": "eng_UG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=postbirth.mother.hw_full'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 3,
                    "short_name": 'postbirth.mother.hw_full',
                    "default_schedule": 3
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/3/',
            json={"id": 3, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change baby completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.contact, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.messageset, 3)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "eng_UG")
        self.assertEqual(d.schedule, 3)


class TestChangeLanguage(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_change_language(self):
        # Setup
        # make registration
        self.make_registration_mother()
        # make change object
        change_data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "change_language",
            "data": {
                "new_language": "cgg_UG"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "subscription1-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_UG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"lang": "cgg_UG"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change language completed")
        assert len(responses.calls) == 2


class TestChangeUnsubscribe(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_unsubscribe(self):
        # Setup
        # make registration
        self.make_registration_mother()
        # make change object
        change_data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "unsubscribe",
            "data": {
                "reason": "miscarriage"
            },
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "subscription1-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_UG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Unsubscribe completed")
        assert len(responses.calls) == 2


class TestChangeLoss(AuthenticatedAPITestCase):

    @responses.activate
    def test_mother_change_loss(self):
        # Setup
        # make registration
        self.make_registration_mother()
        # make change object
        change_data = {
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "action": "change_loss",
            "data": {"reason": "stillborn"},
            "source": self.make_source_adminuser()
        }
        change = Change.objects.create(**change_data)
        # mock get subscription request
        subscription_id = "subscription1-4bf1-8779-c47b428e89d0"
        query_string = '?active=True&id=%s' % change_data["mother_id"]
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/subscriptions/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": subscription_id,
                    "identity": change_data["mother_id"],
                    "active": True,
                    "lang": "eng_UG"
                }],
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock patch subscription request
        responses.add(
            responses.PATCH,
            'http://localhost:8005/api/v1/subscriptions/%s/' % subscription_id,
            json={"active": False},
            status=200, content_type='application/json',
        )
        # mock identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % change_data[
                "mother_id"],
            json={
                "id": change_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {
                            "+256720000222": {}
                        }
                    },
                    "receiver_role": "mother",
                    "preferred_language": "eng_UG"
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json',
        )
        # mock mother messageset lookup
        query_string = '?short_name=loss.mother.hw_full'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 5,
                    "short_name": 'loss.mother.hw_full',
                    "default_schedule": 5
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock mother schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/5/',
            json={"id": 5, "day_of_week": "1,3"},
            status=200, content_type='application/json',
        )

        # Execute
        result = implement_action.apply_async(args=[change.id])

        # Check
        self.assertEqual(result.get(), "Change loss completed")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.contact, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.messageset, 5)
        self.assertEqual(d.next_sequence_number, 1)
        self.assertEqual(d.lang, "eng_UG")
        self.assertEqual(d.schedule, 5)
