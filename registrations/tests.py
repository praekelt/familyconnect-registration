import json
import uuid
import datetime
import responses

from django.contrib.auth.models import User
from django.test import TestCase
from django.db.models.signals import post_save
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_hooks.models import model_saved, Hook

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from .models import (Source, Registration, SubscriptionRequest,
                     registration_post_save)
from .tasks import (
    validate_registration, send_location_reminders,
    is_valid_date, is_valid_uuid, is_valid_lang, is_valid_msg_type,
    is_valid_msg_receiver, is_valid_loss_reason, is_valid_name)
from familyconnect_registration import utils


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


REG_FIELDS = {
    "hw_pre": [
        "hoh_id", "operator_id", "language", "msg_type",
        "last_period_date", "msg_receiver", "hoh_name", "hoh_surname",
        "mama_name", "mama_surname"],
}

REG_DATA = {
    "hw_pre_hoh": {
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
    },
    "hw_pre_mother": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "mother01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",  # 28 weeks pregnant
        "msg_receiver": "mother_to_be",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
    },
    "hw_pre_family": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",
        "msg_receiver": "family_member",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
    },
    "hw_pre_friend": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
    },
    "pbl_pre": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "mother01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": None,
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",
        "msg_receiver": "mother_to_be",
        "parish": "Kawaaga",
        "vht_id": "vht00001-63e2-4acc-9b94-26663b9bc267"
    },
    "pbl_loss": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "loss_reason": "miscarriage"
    },
    "bad_data_combination": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
    },
    "bad_fields": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "2015020",
        "msg_receiver": "trusted friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
    },
    "bad_lmp": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20140202",
        "msg_receiver": "trusted_friend",
        "hoh_name": "bob",
        "hoh_surname": "the builder",
        "mama_name": "sue",
        "mama_surname": "zin",
    },
}


class APITestCase(TestCase):

    def setUp(self):
        self.adminclient = APIClient()
        self.normalclient = APIClient()
        self.otherclient = APIClient()
        utils.get_today = override_get_today


class AuthenticatedAPITestCase(APITestCase):

    def _replace_post_save_hooks(self):
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

    def _restore_post_save_hooks(self):
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

    def make_registration_adminuser(self):
        data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {"test_adminuser_reg_key": "test_adminuser_reg_value"},
            "source": self.make_source_adminuser()
        }
        return Registration.objects.create(**data)

    def make_registration_normaluser(self):
        data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {"test_normaluser_reg_key": "test_normaluser_reg_value"},
            "source": self.make_source_normaluser()
        }
        return Registration.objects.create(**data)

    def setUp(self):
        super(AuthenticatedAPITestCase, self).setUp()
        self._replace_post_save_hooks()

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
        self._restore_post_save_hooks()


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


class TestSourceAPI(AuthenticatedAPITestCase):

    def test_get_source_adminuser(self):
        # Setup
        source = self.make_source_adminuser()
        # Execute
        response = self.adminclient.get('/api/v1/source/%s/' % source.id,
                                        format='json',
                                        content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["authority"], "hw_full")
        self.assertEqual(response.data["name"], "test_source_adminuser")

    def test_get_source_normaluser(self):
        # Setup
        source = self.make_source_normaluser()
        # Execute
        response = self.normalclient.get('/api/v1/source/%s/' % source.id,
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_source_adminuser(self):
        # Setup
        user = User.objects.get(username='testadminuser')
        post_data = {
            "name": "test_source_name",
            "authority": "patient",
            "user": "/api/v1/user/%s/" % user.id
        }
        # Execute
        response = self.adminclient.post('/api/v1/source/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Source.objects.last()
        self.assertEqual(d.name, 'test_source_name')
        self.assertEqual(d.authority, "patient")

    def test_create_source_normaluser(self):
        # Setup
        user = User.objects.get(username='testnormaluser')
        post_data = {
            "name": "test_source_name",
            "authority": "hw_full",
            "user": "/api/v1/user/%s/" % user.id
        }
        # Execute
        response = self.normalclient.post('/api/v1/source/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestRegistrationAPI(AuthenticatedAPITestCase):

    def test_get_registration_adminuser(self):
        # Setup
        registration = self.make_registration_adminuser()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/%s/' % registration.id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stage"], "prebirth")
        self.assertEqual(response.data["data"]["test_adminuser_reg_key"],
                         "test_adminuser_reg_value")

    def test_get_registration_normaluser(self):
        # Setup
        registration = self.make_registration_normaluser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/registrations/%s/' % registration.id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stage"], "prebirth")
        self.assertEqual(response.data["data"]["test_normaluser_reg_key"],
                         "test_normaluser_reg_value")

    def test_create_registration_adminuser(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.adminclient.post('/api/v1/registration/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.stage, 'prebirth')
        self.assertEqual(d.mother_id, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_registration_normaluser(self):
        # Setup
        self.make_source_normaluser()
        post_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {"test_key1": "test_value1"}
        }
        # Execute
        response = self.normalclient.post('/api/v1/registration/',
                                          json.dumps(post_data),
                                          content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_normaluser')
        self.assertEqual(d.stage, 'prebirth')
        self.assertEqual(d.mother_id, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.validated, False)
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_create_registration_set_readonly_field(self):
        # Setup
        self.make_source_adminuser()
        post_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": {"test_key1": "test_value1"},
            "validated": True
        }
        # Execute
        response = self.adminclient.post('/api/v1/registration/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        d = Registration.objects.last()
        self.assertEqual(d.source.name, 'test_source_adminuser')
        self.assertEqual(d.stage, 'prebirth')
        self.assertEqual(d.mother_id, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.validated, False)  # Should ignore True post_data
        self.assertEqual(d.data, {"test_key1": "test_value1"})

    def test_list_registrations(self):
        # Setup
        registration1 = self.make_registration_normaluser()
        registration2 = self.make_registration_adminuser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/registrations/', content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        result1, result2 = response.data["results"]
        self.assertEqual(result1["id"], str(registration1.id))
        self.assertEqual(result2["id"], str(registration2.id))

    def make_different_registrations(self):
        self.make_source_adminuser()
        registration1_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_hoh"].copy(),
            "source": self.make_source_adminuser(),
            "validated": True
        }
        registration1 = Registration.objects.create(**registration1_data)
        registration2_data = {
            "stage": "postbirth",
            "mother_id": "mother02-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_hoh"].copy(),
            "source": self.make_source_normaluser(),
            "validated": False
        }
        registration2 = Registration.objects.create(**registration2_data)

        return (registration1, registration2)

    def test_filter_registration_mother_id(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?mother_id=%s' % registration1.mother_id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration1.id))

    def test_filter_registration_stage(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?stage=%s' % registration2.stage,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration2.id))

    def test_filter_registration_validated(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?validated=%s' % registration1.validated,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration1.id))

    def test_filter_registration_source(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?source=%s' % registration2.source.id,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration2.id))

    def test_filter_registration_created_after(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # While the '+00:00' is valid according to ISO 8601, the version of
        # django-filter we are using does not support it
        date_string = registration2.created_at.isoformat().replace(
            "+00:00", "Z")
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?created_after=%s' % date_string,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration2.id))

    def test_filter_registration_created_before(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # While the '+00:00' is valid according to ISO 8601, the version of
        # django-filter we are using does not support it
        date_string = registration1.created_at.isoformat().replace(
            "+00:00", "Z")
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?created_before=%s' % date_string,
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(registration1.id))

    def test_filter_registration_no_matches(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?mother_id=test_id',
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_filter_registration_unknown_filter(self):
        # Setup
        registration1, registration2 = self.make_different_registrations()
        # Execute
        response = self.adminclient.get(
            '/api/v1/registrations/?something=test_id',
            content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class TestFieldValidation(AuthenticatedAPITestCase):

    def test_is_valid_date(self):
        # Setup
        good_date = "19820315"
        invalid_date = "19830229"
        bad_date = "1234"
        # Execute
        # Check
        self.assertEqual(is_valid_date(good_date), True)
        self.assertEqual(is_valid_date(invalid_date), False)
        self.assertEqual(is_valid_date(bad_date), False)

    def test_is_valid_uuid(self):
        # Setup
        valid_uuid = str(uuid.uuid4())
        invalid_uuid = "f9bfa2d7-5b62-4011-8eac-76bca34781a"
        # Execute
        # Check
        self.assertEqual(is_valid_uuid(valid_uuid), True)
        self.assertEqual(is_valid_uuid(invalid_uuid), False)

    def test_is_valid_lang(self):
        # Setup
        valid_lang = "lug_UG"
        invalid_lang = "lusoga"
        # Execute
        # Check
        self.assertEqual(is_valid_lang(valid_lang), True)
        self.assertEqual(is_valid_lang(invalid_lang), False)

    def test_is_valid_msg_type(self):
        # Setup
        valid_msg_type = "text"
        invalid_msg_type = "voice"
        # Execute
        # Check
        self.assertEqual(is_valid_msg_type(valid_msg_type), True)
        self.assertEqual(is_valid_msg_type(invalid_msg_type), False)

    def test_is_valid_msg_receiver(self):
        # Setup
        valid_msg_receiver = "head_of_household"
        invalid_msg_receiver = "mama"
        # Execute
        # Check
        self.assertEqual(is_valid_msg_receiver(valid_msg_receiver), True)
        self.assertEqual(is_valid_msg_receiver(invalid_msg_receiver), False)

    def test_is_valid_loss_reason(self):
        # Setup
        valid_loss_reason = "miscarriage"
        invalid_loss_reason = "other"
        # Execute
        # Check
        self.assertEqual(is_valid_loss_reason(valid_loss_reason), True)
        self.assertEqual(is_valid_loss_reason(invalid_loss_reason), False)

    def test_is_valid_name(self):
        # Setup
        valid_name1 = "Namey"
        valid_name2 = "Zoé"
        valid_name3 = "1234"
        invalid_name = 10375075
        # Execute
        # Check
        self.assertEqual(is_valid_name(valid_name1), True)
        self.assertEqual(is_valid_name(valid_name2), True)
        self.assertEqual(is_valid_name(valid_name3), True)  # TODO reject
        self.assertEqual(is_valid_name(invalid_name), False)

    def test_check_field_values(self):
        # Setup
        valid_hw_pre_registration_data = REG_DATA["hw_pre_mother"]
        invalid_hw_pre_registration_data = REG_DATA[
            "hw_pre_mother"].copy()
        invalid_hw_pre_registration_data["msg_receiver"] = "somebody"
        # Execute
        cfv_valid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre"], valid_hw_pre_registration_data)
        cfv_invalid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre"], invalid_hw_pre_registration_data)
        # Check
        self.assertEqual(cfv_valid, [])
        self.assertEqual(cfv_invalid, ['msg_receiver'])


class TestRegistrationValidation(AuthenticatedAPITestCase):

    def test_validate_hw_prebirth_hoh(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_hoh"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_mother(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_family(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_family"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_friend(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    @responses.activate
    def test_validate_pbl_prebirth_vht(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["pbl_pre"].copy(),
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)

        # mock vht identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % registration_data[
                "data"]["vht_id"],
            json={"id": "vht00001-63e2-4acc-9b94-26663b9bc267"}
        )
        # mock mother address lookup
        responses.add(
            responses.GET,
            ('http://localhost:8001/api/v1/identities/%s/addresses/msisdn?'
             'default=True') % registration_data["mother_id"],
            json={"results": [{"address": "+4321"}]},
            match_querystring=True,
        )
        # mock vht address lookup
        responses.add(
            responses.GET,
            ('http://localhost:8001/api/v1/identities/%s/addresses/msisdn?'
             'default=True') % registration_data["data"]["vht_id"],
            json={"results": [{"address": "+1234"}]},
            match_querystring=True,
        )
        # moch message send
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            json={'id': 1})

        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)
        sms_http_call = responses.calls[-1].request
        self.assertEqual(sms_http_call.body, json.dumps({
            "content": (
                "There is a new pregnancy in your parish. "
                "Call +4321 and visit the mother to update her registration."),
            "to_addr": "+1234",
            "metadata": {}}))

    @responses.activate
    def test_validate_pbl_prebirth_location(self):
        # Setup
        data = REG_DATA["pbl_pre"].copy()
        data.pop('vht_id')
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": data,
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)

        # mock vht identities lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/search?details__has_key'
            '=personnel_code&details_parish=%s' % registration_data[
                "data"]["parish"],
            json={"results": [
                {"id": "vht00001-63e2-4acc-9b94-26663b9bc267"},
                {"id": "vht00002-63e2-4acc-9b94-26663b9bc267"},
            ]},
            match_querystring=True,
        )
        # mock mother address lookup
        responses.add(
            responses.GET,
            ('http://localhost:8001/api/v1/identities/%s/addresses/msisdn?'
             'default=True') % registration_data["mother_id"],
            json={"results": [{"address": "+4321"}]},
            match_querystring=True,
        )
        # mock vht1 address lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/vht00001-63e2-4acc-9b94'
            '-26663b9bc267/addresses/msisdn?default=True',
            json={"results": [{"address": "+1234"}]},
            match_querystring=True,
        )
        # mock vht2 address lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/vht00002-63e2-4acc-9b94'
            '-26663b9bc267/addresses/msisdn?default=True',
            json={"results": [{"address": "+2234"}]},
            match_querystring=True,
        )
        # moch message send
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            json={'id': 1})

        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)
        [sms01, sms02] = filter(
            lambda r: r.request.url == 'http://localhost:8006/api/v1/'
            'outbound/', responses.calls)
        self.assertEqual(sms01.request.body, json.dumps({
            "content": (
                "There is a new pregnancy in your parish. "
                "Call +4321 and visit the mother to update her registration."),
            "to_addr": "+1234",
            "metadata": {}}))
        self.assertEqual(sms02.request.body, json.dumps({
            "content": (
                "There is a new pregnancy in your parish. "
                "Call +4321 and visit the mother to update her registration."),
            "to_addr": "+2234",
            "metadata": {}}))

    def test_validate_pbl_loss(self):
        # Setup
        registration_data = {
            "stage": "loss",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["pbl_loss"].copy(),
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_loss")
        self.assertEqual(registration.validated, True)

    def test_validate_pregnancy_too_long(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20130101"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    def test_validate_pregnancy_too_short(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration_data["data"]["last_period_date"] = "20150816"
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, False)
        self.assertEqual(registration.validated, False)

    @responses.activate
    def test_validate_registration_run_success(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # mock messageset lookup
        query_string = '?short_name=prebirth.mother.hw_full'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 1,
                    "short_name": 'prebirth.mother.hw_full',
                    "default_schedule": 1
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/1/',
            json={"id": 1, "day_of_week": "1,4"},
            status=200, content_type='application/json',
        )
        # mock mother identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % registration_data[
                "mother_id"],
            json={
                "id": registration_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {}
                    },
                    "receiver_role": "mother_to_be",
                    "health_id": 9999999999
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json'
        )
        # mock Mother MSISDN lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/mother01-63e2-4acc-9b94-26663b9bc267/addresses/msisdn?default=True',  # noqa
            json={
                "count": 1, "next": None, "previous": None,
                "results": [{"address": "+256123"}]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock SMS send
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            json={"id": 1},
            status=200, content_type='application/json',
        )
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Success")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.messageset, 1)
        self.assertEqual(d.next_sequence_number, 48)  # (28-4)*2
        self.assertEqual(d.lang, "eng_UG")
        self.assertEqual(d.schedule, 1)

    def test_validate_registration_run_failure_bad_combination(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["bad_data_combination"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"],
                         "Invalid combination of fields")

    def test_validate_registration_run_failure_bad_fields(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["bad_fields"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(sorted(d.data["invalid_fields"]),
                         sorted(["msg_receiver", "last_period_date"]))

    def test_validate_registration_run_failure_bad_lmp(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["bad_lmp"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        result = validate_registration.apply_async(args=[registration.id])
        # Check
        self.assertEqual(result.get(), "Validation completed - Failure")
        d = Registration.objects.get(id=registration.id)
        self.assertEqual(d.data["invalid_fields"],
                         ["last_period_date out of range"])


class TestSubscriptionRequest(AuthenticatedAPITestCase):

    @responses.activate
    def test_hoh_prebirth_patient(self):
        # Setup
        # prepare registration data
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_hoh"].copy(),
            "source": self.make_source_normaluser()
        }
        registration_data["data"]["preg_week"] = 15
        registration = Registration.objects.create(**registration_data)
        # mock messageset lookup
        query_string = '?short_name=prebirth.household.patient'
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/messageset/%s' % query_string,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 2,
                    "short_name": 'prebirth.household.patient',
                    "default_schedule": 2
                }]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock schedule lookup
        responses.add(
            responses.GET,
            'http://localhost:8005/api/v1/schedule/2/',
            json={"id": 2, "day_of_week": "1"},
            status=200, content_type='application/json',
        )

        # mock mother identity lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/%s/' % registration_data[
                "mother_id"],
            json={
                "id": registration_data["mother_id"],
                "version": 1,
                "details": {
                    "default_addr_type": "msisdn",
                    "addresses": {
                        "msisdn": {}
                    },
                    "receiver_role": "mother_to_be",
                    "health_id": 7777777777
                },
                "created_at": "2015-07-10T06:13:29.693272Z",
                "updated_at": "2015-07-10T06:13:29.693298Z"
            },
            status=200, content_type='application/json'
        )
        # mock HOH MSISDN lookup
        responses.add(
            responses.GET,
            'http://localhost:8001/api/v1/identities/hoh00001-63e2-4acc-9b94-26663b9bc267/addresses/msisdn?default=True',  # noqa
            json={
                "count": 1, "next": None, "previous": None,
                "results": [{"address": "+256124"}]
            },
            status=200, content_type='application/json',
            match_querystring=True
        )
        # mock SMS send
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            json={"id": 1},
            status=200, content_type='application/json',
        )

        # Execute
        result = validate_registration.create_subscriptionrequests(
            registration)
        # Check
        self.assertEqual(result, "SubscriptionRequest created")
        d = SubscriptionRequest.objects.last()
        self.assertEqual(d.identity, "mother01-63e2-4acc-9b94-26663b9bc267")
        self.assertEqual(d.messageset, 2)
        self.assertEqual(d.next_sequence_number, 11)  # (15-4)*1
        self.assertEqual(d.lang, "eng_UG")
        self.assertEqual(d.schedule, 2)


class TestSubscriptionRequestWebhook(AuthenticatedAPITestCase):

    def test_create_webhook(self):
        # Setup
        user = User.objects.get(username='testadminuser')
        post_data = {
            "target": "http://example.com/registration/",
            "event": "subscriptionrequest.added"
        }
        # Execute
        response = self.adminclient.post('/api/v1/webhook/',
                                         json.dumps(post_data),
                                         content_type='application/json')
        # Check
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = Hook.objects.last()
        self.assertEqual(d.target, 'http://example.com/registration/')
        self.assertEqual(d.user, user)

    # This test is not working despite the code working fine
    # If you run these same steps below interactively the webhook will fire
    # @responses.activate
    # def test_mother_only_webhook(self):
    #     # Setup
    #     post_save.connect(receiver=model_saved, sender=SubscriptionRequest,
    #                       dispatch_uid='instance-saved-hook')
    #     Hook.objects.create(user=self.adminuser,
    #                         event='subscriptionrequest.added',
    #                         target='http://example.com/registration/')
    #
    #     expected_webhook = {
    #         "hook": {
    #             "target": "http://example.com/registration/",
    #             "event": "subscriptionrequest.added",
    #             "id": 3
    #         },
    #         "data": {
    #             "messageset": 1,
    #             "updated_at": "2016-02-17T07:59:42.831568+00:00",
    #             "identity": "mother01-63e2-4acc-9b94-26663b9bc267",
    #             "lang": "eng_NG",
    #             "created_at": "2016-02-17T07:59:42.831533+00:00",
    #             "id": "5282ed58-348f-4a54-b1ff-f702e36ec3cc",
    #             "next_sequence_number": 1,
    #             "schedule": 1
    #         }
    #     }
    #     responses.add(
    #         responses.POST,
    #         "http://example.com/registration/",
    #         json.dumps(expected_webhook),
    #         status=200, content_type='application/json')
    #     registration_data = {
    #         "stage": "prebirth",
    #         "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
    #         "data": REG_DATA["hw_pre_id_mother"].copy(),
    #         "source": self.make_source_adminuser()
    #     }
    #     registration = Registration.objects.create(**registration_data)
    #     # Execute
    #     result = validate_registration.create_subscriptionrequests(
    #         registration)
    #     # Check
    #     self.assertEqual(result, "SubscriptionRequest created")
    #     d = SubscriptionRequest.objects.last()
    #     self.assertEqual(d.identity,
    #                      "mother01-63e2-4acc-9b94-26663b9bc267")
    #     self.assertEqual(d.messageset, 1)
    #     self.assertEqual(d.next_sequence_number, 1)
    #     self.assertEqual(d.lang, "eng_NG")
    #     self.assertEqual(d.schedule, 1)
    #     self.assertEqual(responses.calls[0].request.url,
    #                      "http://example.com/registration/")


class TestRegistrationModel(AuthenticatedAPITestCase):
    def test_validated_filter(self):
        """
        The validated queryset filter should only return validated
        registrations.
        """
        r1 = self.make_registration_adminuser()
        r1.validated = True
        r1.save()
        r2 = self.make_registration_adminuser()
        self.assertFalse(r2.validated)

        [reg] = Registration.objects.validated()
        self.assertEqual(reg.pk, r1.pk)

    def test_public_registrations_filter(self):
        """
        The public registrations filter should only return registrations
        make through public sources.
        """
        r1 = self.make_registration_normaluser()
        self.assertEqual(r1.source.authority, 'patient')
        r2 = self.make_registration_adminuser()
        self.assertEqual(r2.source.authority, 'hw_full')

        [reg] = Registration.objects.public_registrations()
        self.assertEqual(reg.pk, r1.pk)


class TestSendLocationRemindersTask(AuthenticatedAPITestCase):
    @responses.activate
    def test_send_location_reminder(self):
        """
        The send_location_reminder should send the correct message according
        to the given recipient and language.
        """
        responses.add(
            responses.POST,
            'http://localhost:8006/api/v1/outbound/',
            json={'id': 1})
        responses.add(
            responses.GET,
            ('http://localhost:8001/api/v1/identities/%s/addresses/msisdn?'
             'default=True') % 'mother01-63e2-4acc-9b94-26663b9bc267',
            json={"results": [{"address": "+4321"}]},
            match_querystring=True,
        )

        send_location_reminders.send_location_reminder(
            'mother01-63e2-4acc-9b94-26663b9bc267', 'eng_UG')

        sms_http_call = responses.calls[-1].request
        self.assertEqual(sms_http_call.body, json.dumps({
            "content": (
                "To make sure you can receive care from your local VHT, please"
                " dial in to *XXX*X# and add your location. FamilyConnect"),
            "to_addr": "+4321",
            "metadata": {}}))

    def test_send_locations_task(self):
        """
        The send_locations_reminder task should look up registrations, and send
        messages to the correct ones.
        """
        # Should be called
        r1 = self.make_registration_normaluser()
        r1.validated = True
        r1.data['receiver_id'] = 'mother01-63e2-4acc-9b94-26663b9bc267'
        r1.data['language'] = 'eng_UG'
        r1.save()
        # Not public, shouldn't be called
        r2 = self.make_registration_adminuser()
        self.assertEqual(r2.source.authority, 'hw_full')
        # Should be called
        r3 = self.make_registration_normaluser()
        r3.validated = True
        r3.data['receiver_id'] = 'mother03-63e2-4acc-9b94-26663b9bc267'
        r3.data['language'] = 'cgg_UG'
        r3.data['parish'] = None
        r3.save()
        # Not validated, shouldn't be called
        r4 = self.make_registration_normaluser()
        self.assertFalse(r4.validated)
        # Has location, shouldn't be called
        r5 = self.make_registration_normaluser()
        r5.validated = True
        r5.data['parish'] = 'Kawaaga'
        r5.save()

        with patch.object(send_location_reminders, 'send_location_reminder') \
                as send_location_reminder:
            send_location_reminders.run()

        self.assertEqual(send_location_reminder.call_count, 2)
        send_location_reminder.assert_any_call(
            'mother01-63e2-4acc-9b94-26663b9bc267', 'eng_UG')
        send_location_reminder.assert_any_call(
            'mother03-63e2-4acc-9b94-26663b9bc267', 'cgg_UG')
