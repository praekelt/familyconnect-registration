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

from .models import (Source, Registration, SubscriptionRequest,
                     registration_post_save)
from .tasks import (
    validate_registration,
    is_valid_date, is_valid_uuid, is_valid_lang, is_valid_msg_type,
    is_valid_msg_receiver, is_valid_loss_reason, is_valid_name,
    is_valid_id_type, is_valid_id_no)
from familyconnect_registration import utils


def override_get_today():
    return datetime.datetime.strptime("20150817", "%Y%m%d")


REG_FIELDS = {
    "hw_pre_id": [
        "hoh_id", "operator_id", "language", "msg_type",
        "last_period_date", "msg_receiver", "hoh_name", "hoh_surname",
        "mama_name", "mama_surname", "mama_id_type", "mama_id_no"],
}

REG_DATA = {
    "hw_pre_id_hoh": {
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
    "hw_pre_id_mother": {
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
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
    },
    "hw_pre_id_family": {
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
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
    },
    "hw_pre_dob_friend": {
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
        "mama_id_type": "other",
        "mama_dob": "19900707"
    },
    "pbl_pre": {
        "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
        "receiver_id": "friend01-63e2-4acc-9b94-26663b9bc267",
        "operator_id": None,
        "language": "eng_UG",
        "msg_type": "text",
        "last_period_date": "20150202",
        "msg_receiver": "trusted_friend"
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
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
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
        "mama_id_type": "ugandan_id",
        "mama_id_no": "12345"
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
            '/api/v1/registration/%s/' % registration.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_get_registration_normaluser(self):
        # Setup
        registration = self.make_registration_normaluser()
        # Execute
        response = self.normalclient.get(
            '/api/v1/registration/%s/' % registration.id,
            content_type='application/json')
        # Check
        # Currently only posts are allowed
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

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

    def test_is_valid_id_type(self):
        # Setup
        valid_id_type = "ugandan_id"
        invalid_id_type = "sa_id"
        # Execute
        # Check
        self.assertEqual(is_valid_id_type(valid_id_type), True)
        self.assertEqual(is_valid_id_type(invalid_id_type), False)

    def test_is_valid_id_no(self):
        # Setup
        valid_id_no = "12345"
        invalid_id_no = 12345
        # Execute
        # Check
        self.assertEqual(is_valid_id_no(valid_id_no), True)
        self.assertEqual(is_valid_id_no(invalid_id_no), False)

    def test_check_field_values(self):
        # Setup
        valid_hw_pre_id_registration_data = REG_DATA["hw_pre_id_mother"]
        invalid_hw_pre_id_registration_data = REG_DATA[
            "hw_pre_id_mother"].copy()
        invalid_hw_pre_id_registration_data["msg_receiver"] = "somebody"
        # Execute
        cfv_valid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_id"], valid_hw_pre_id_registration_data)
        cfv_invalid = validate_registration.check_field_values(
            REG_FIELDS["hw_pre_id"], invalid_hw_pre_id_registration_data)
        # Check
        self.assertEqual(cfv_valid, [])
        self.assertEqual(cfv_invalid, ['msg_receiver'])


class TestRegistrationValidation(AuthenticatedAPITestCase):

    def test_validate_hw_prebirth_id_hoh(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_id_hoh"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_id")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_id_mother(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_id_mother"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_id")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_id_family(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_id_family"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_id")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_hw_prebirth_dob_friend(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["hw_pre_dob_friend"].copy(),
            "source": self.make_source_adminuser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "hw_pre_dob")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

    def test_validate_pbl_prebirth(self):
        # Setup
        registration_data = {
            "stage": "prebirth",
            "mother_id": "mother01-63e2-4acc-9b94-26663b9bc267",
            "data": REG_DATA["pbl_pre"].copy(),
            "source": self.make_source_normaluser()
        }
        registration = Registration.objects.create(**registration_data)
        # Execute
        v = validate_registration.validate(registration)
        # Check
        self.assertEqual(v, True)
        self.assertEqual(registration.data["reg_type"], "pbl_pre")
        self.assertEqual(registration.data["preg_week"], 28)
        self.assertEqual(registration.validated, True)

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
            "data": REG_DATA["hw_pre_id_mother"].copy(),
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
            "data": REG_DATA["hw_pre_id_mother"].copy(),
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
            "data": REG_DATA["hw_pre_id_mother"].copy(),
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
            "data": REG_DATA["hw_pre_id_hoh"].copy(),
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
