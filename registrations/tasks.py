import datetime
import six  # for Python 2 and 3 string type compatibility
import requests
import json
import uuid

import pika
from django.conf import settings
from django.db.models import Q
from celery.task import Task
from celery.utils.log import get_task_logger
from go_http.metrics import MetricsApiClient

from .models import Registration, SubscriptionRequest
from familyconnect_registration import utils
from .graphite import RetentionScheme
from .metrics import MetricGenerator, send_metric


logger = get_task_logger(__name__)


def is_valid_date(date):
    try:
        datetime.datetime.strptime(date, "%Y%m%d")
        return True
    except:
        return False


def is_valid_uuid(id):
    return len(id) == 36 and id[14] == '4' and id[19] in ['a', 'b', '8', '9']


def is_valid_lang(lang):
    return lang in settings.LANGUAGES


def is_valid_msg_type(msg_type):
    return msg_type in ["text"]  # currently text only


def is_valid_msg_receiver(msg_receiver):
    return msg_receiver in ["head_of_household", "mother_to_be",
                            "family_member", "trusted_friend"]


def is_valid_loss_reason(loss_reason):
    return loss_reason in ['miscarriage', 'stillborn', 'baby_died']


def is_valid_name(name):
    return isinstance(name, six.string_types)  # TODO reject non-letters


class ValidateRegistration(Task):
    """ Task to validate a registration model entry's registration
    data.
    """
    name = "familyconnect_registration.registrations.tasks.\
    validate_registration"

    def check_field_values(self, fields, registration_data):
        failures = []
        for field in fields:
            if field in ["hoh_id", "receiver_id", "operator_id"]:
                if not is_valid_uuid(registration_data[field]):
                    failures.append(field)
            if field == "language":
                if not is_valid_lang(registration_data[field]):
                    failures.append(field)
            if field == "msg_type":
                if not is_valid_msg_type(registration_data[field]):
                    failures.append(field)
            if field in ["last_period_date", "baby_dob"]:
                if not is_valid_date(registration_data[field]):
                    failures.append(field)
                else:
                    # Check last_period_date is in the past and < 42 weeks ago
                    if field == "last_period_date":
                        preg_weeks = utils.calc_pregnancy_week_lmp(
                            utils.get_today(), registration_data[field])
                        if not (2 <= preg_weeks <= 42):
                            failures.append("last_period_date out of range")
            if field == "msg_receiver":
                if not is_valid_msg_receiver(registration_data[field]):
                    failures.append(field)
            if field == "loss_reason":
                if not is_valid_loss_reason(registration_data[field]):
                    failures.append(field)
            if field in ["hoh_name", "hoh_surname", "mama_name",
                         "mama_surname"]:
                if not is_valid_name(registration_data[field]):
                    failures.append(field)
        return failures

    def send_vht_sms(self, mother_id, parish, vht_id=None):
        """Sends an sms to the specific VHT, or if there is no VHT specified,
        sends an sms to all VHTs in the parish."""
        if vht_id is not None:
            vhts = (utils.get_identity(vht_id),)
        else:
            vhts = utils.get_vhts_for_parish(parish)

        mother_address = utils.get_identity_address(mother_id)
        sms_text = settings.VHT_PUBLIC_REGISTRATION_NOTIFICATION_TEXT.format(
            mother=mother_address)
        for vht in vhts:
            utils.post_message({
                'to_addr': utils.get_identity_address(vht['id']),
                'content': sms_text,
                'metadata': {},
            })

    def validate(self, registration):
        """ Validates that all the required info is provided for a
        prebirth registration.
        """
        data_fields = registration.data.keys()
        fields_general = ["hoh_id", "receiver_id", "language",
                          "msg_type"]
        fields_prebirth = ["last_period_date", "msg_receiver"]
        fields_loss = ["loss_reason"]
        fields_hw = [
            "operator_id", "hoh_name", "hoh_surname", "mama_name",
            "mama_surname",
        ]

        # Perhaps the below should rather be hardcoded to save a tiny bit of
        # processing time for each registration
        hw_pre = list(
            set(fields_general) | set(fields_prebirth) | set(fields_hw))
        pbl_pre = list(set(fields_general) | set(fields_prebirth))
        pbl_loss = list(set(fields_general) | set(fields_loss))

        # Check if mother_id is a valid UUID
        if not is_valid_uuid(registration.mother_id):
            registration.data["invalid_fields"] = "Invalid UUID mother_id"
            registration.save()
            return False

        if "msg_receiver" in registration.data.keys():
            # Reject registrations where the hoh is the receiver but the
            # hoh_id and receiver_id differs
            if (registration.data["msg_receiver"] == "head_of_household" and
               registration.data["hoh_id"] != registration.data[
                    "receiver_id"]):
                registration.data["invalid_fields"] = "hoh_id should be " \
                    "the same as receiver_id"
                registration.save()
                return False
            # Reject registrations where the mother is the receiver but the
            # mother_id and receiver_id differs
            elif (registration.data["msg_receiver"] == "mother_to_be" and
                  registration.mother_id != registration.data["receiver_id"]):
                registration.data["invalid_fields"] = "mother_id should be " \
                    "the same as receiver_id"
                registration.save()
                return False
            # Reject registrations where the family / friend is the receiver
            # but the receiver_id is the same as the mother_id or hoh_id
            elif (registration.data["msg_receiver"] in
                  ["family_member", "trusted_friend"] and (
                    registration.data["receiver_id"] ==
                    registration.data["hoh_id"] or (
                    registration.data["receiver_id"] ==
                    registration.mother_id))):
                registration.data["invalid_fields"] = "receiver_id should" \
                    "differ from hoh_id and mother_id"
                registration.save()
                return False

        # HW registration, prebirth
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre).issubset(data_fields)):  # ignore extra data
            invalid_fields = self.check_field_values(
                hw_pre, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "hw_pre"
                registration.data["preg_week"] = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        # Public registration (currently only prebirth)
        elif (registration.stage == "prebirth" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_pre).issubset(data_fields)):
            invalid_fields = self.check_field_values(
                pbl_pre, registration.data)
            if invalid_fields == []:
                if registration.data.get('parish') is not None:
                    self.send_vht_sms(
                        mother_id=registration.data['receiver_id'],
                        parish=registration.data['parish'],
                        vht_id=registration.data.get('vht_id'))

                registration.data["reg_type"] = "pbl_pre"
                registration.data["preg_week"] = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        # Loss registration
        elif (registration.stage == "loss" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_loss).issubset(data_fields)):
            invalid_fields = self.check_field_values(
                pbl_loss, registration.data)
            if invalid_fields == []:
                registration.data["reg_type"] = "pbl_loss"
                registration.validated = True
                registration.save()
                return True
            else:
                registration.data["invalid_fields"] = invalid_fields
                registration.save()
                return False
        else:
            registration.data[
                "invalid_fields"] = "Invalid combination of fields"
            registration.save()
            return False

    def create_subscriptionrequests(self, registration):
        """ Create SubscriptionRequest(s) based on the
        validated registration.
        """

        # Create subscription
        if 'preg_week' in registration.data:
            weeks = registration.data["preg_week"]
        else:
            weeks = registration.data["baby_age"]

        short_name = utils.get_messageset_short_name(
            registration.data["msg_receiver"], registration.stage,
            registration.source.authority
        )

        msgset_id, msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(
                short_name, weeks)

        mother_sub = {
            "identity": registration.mother_id,
            "messageset": msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": registration.data["language"],
            "schedule": msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        # Send registration welcome SMS
        if registration.data["msg_receiver"] == "mother_to_be":
            if "hw" in registration.source.authority:
                sms = settings.MOTHER_HW_WELCOME_TEXT_UG_ENG
            else:
                sms = settings.MOTHER_PUBLIC_WELCOME_TEXT_UG_ENG

            # Insert the mother's name in the SMS
            sms = sms.replace(
                '[mother_first_name]', registration.data["mama_name"])
        else:
            if "hw" in registration.source.authority:
                sms = settings.HOUSEHOLD_HW_WELCOME_TEXT_UG_ENG
            else:
                sms = settings.HOUSEHOLD_PUBLIC_WELCOME_TEXT_UG_ENG
        # Insert the mother's health_id in the SMS
        mother = utils.get_identity(registration.mother_id)
        if mother["details"]["health_id"]:
            sms = sms.replace(
                '[health_id]', str(mother["details"]["health_id"]))
        else:
            # TODO: #13
            pass

        payload = {
            "to_addr": utils.get_identity_address(
                registration.data["receiver_id"]),
            "content": sms,
            "metadata": {}
        }
        utils.post_message(payload)

        return "SubscriptionRequest created"

    def run(self, registration_id, **kwargs):
        """ Sets the registration's validated field to True if
        validation is successful.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up the registration")
        registration = Registration.objects.get(id=registration_id)
        reg_validates = self.validate(registration)

        validation_string = "Validation completed - "
        if reg_validates:
            validation_string += "Success"
            self.create_subscriptionrequests(registration)
        else:
            validation_string += "Failure"

        return validation_string

validate_registration = ValidateRegistration()


class DeliverHook(Task):
    def run(self, target, payload, instance_id=None, hook_id=None, **kwargs):
        """
        target:     the url to receive the payload.
        payload:    a python primitive data structure
        instance_id:   a possibly None "trigger" instance ID
        hook_id:       the ID of defining Hook object
        """
        requests.post(
            url=target,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Token %s' % settings.HOOK_AUTH_TOKEN
            }
        )


def deliver_hook_wrapper(target, payload, instance, hook):
    if instance is not None:
        if isinstance(instance.id, uuid.UUID):
            instance_id = str(instance.id)
        else:
            instance_id = instance.id
    else:
        instance_id = None
    kwargs = dict(target=target, payload=payload,
                  instance_id=instance_id, hook_id=hook.id)
    DeliverHook.apply_async(kwargs=kwargs)


class SendLocationReminders(Task):
    def send_location_reminder(self, recipient, language):
        """
        Sends a location reminder to the receiver specified by the registration
        """
        content = getattr(
            settings,
            'LOCATION_UPDATE_REMINDER_TEXT_{}'.format(language.upper()))
        utils.post_message({
            'to_addr': utils.get_identity_address(recipient),
            'content': content,
            'metadata': {},
        })

    def run(self, **kwargs):
        """
        Looks up registrations that don't have their location set, and sends
        a reminder SMS to the receiver to update their location.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up registrations that don't have locations")

        registrations = Registration.objects \
            .validated() \
            .public_registrations() \
            .filter(
                ~Q(data__has_key='parish') |
                Q(data__contains={'parish': None}) |
                Q(data__contains={'parish': ""})
            )

        for registration in registrations:
            self.send_location_reminder(
                registration.data['receiver_id'],
                registration.data['language'])

send_location_reminders = SendLocationReminders()


def get_metric_client(session=None):
    return MetricsApiClient(
        auth_token=settings.METRICS_AUTH_TOKEN,
        api_url=settings.METRICS_URL,
        session=session)


class FireMetric(Task):

    """ Fires a metric using the MetricsApiClient
    """
    name = "hellomama_registration.tasks.fire_metric"

    def run(self, metric_name, metric_value, session=None, **kwargs):
        metric_value = float(metric_value)
        metric = {
            metric_name: metric_value
        }
        metric_client = get_metric_client(session=session)
        metric_client.fire(metric)
        return "Fired metric <%s> with value <%s>" % (
            metric_name, metric_value)

fire_metric = FireMetric()


class RepopulateMetrics(Task):
    """
    Repopulates historical metrics.
    """
    name = 'registrations.tasks.repopulate_metrics'

    def generate_and_send(
            self, amqp_url, prefix, metric_name, start, end):
        """
        Generates the value for the specified metric, and sends it.
        """
        value = MetricGenerator().generate_metric(metric_name, start, end)

        timestamp = start + (end - start) / 2
        send_metric(amqp_url, prefix, metric_name, value, timestamp)

    def run(
            self, amqp_url, prefix, metric_names, graphite_retentions,
            **kwargs):
        parameters = pika.URLParameters(amqp_url)
        connection = pika.BlockingConnection(parameters)
        amqp_channel = connection.channel()

        ret = RetentionScheme(graphite_retentions)
        for start, end in ret.get_buckets():
            for metric in metric_names:
                self.generate_and_send(
                    amqp_channel, prefix, metric, start, end)

        connection.close()

repopulate_metrics = RepopulateMetrics()
