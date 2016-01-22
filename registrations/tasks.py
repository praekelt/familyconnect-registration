import datetime
import uuid
import six  # for Python 2 and 3 string type compatibility

from celery.task import Task
from celery.utils.log import get_task_logger

from .models import Registration


logger = get_task_logger(__name__)


def is_valid_date(date):
    try:
        datetime.datetime.strptime(date, "%Y%m%d")
        return True
    except:
        return False


def is_valid_uuid(id):
    return type(id) is uuid.UUID


def is_valid_lang(lang):
    return lang in ["english", "runyakore", "lusoga"]


def is_valid_msg_type(msg_type):
    return msg_type in ["sms"]  # currently sms-only


def is_valid_msg_receiver(msg_receiver):
    return msg_receiver in ["head_of_household", "mother_to_be",
                            "family_member", "trusted_friend"]


def is_valid_loss_reason(loss_reason):
    return loss_reason in ['miscarriage', 'stillborn', 'baby_died']


def is_valid_name(name):
    return isinstance(name, six.string_types)  # TODO reject non-letters


def is_valid_id_type(id_type):
    return id_type in ["ugandan_id", "other"]


def is_valid_id_no(id_no):
    return isinstance(id_no, six.string_types)  # TODO proper id validation


class ValidateRegistration(Task):
    """ Task to validate a registration model entry's registration
    data.
    """
    name = "familyconnect_registration.registrations.tasks.\
    validate_registration"

    def check_field_values(self, fields, registration_data):
        for field in fields:
            if field in ["contact", "registered_by"]:
                if not is_valid_uuid(registration_data[field]):
                    return False
            if field == "language":
                if not is_valid_lang(registration_data[field]):
                    return False
            if field == "msg_type":
                if not is_valid_msg_type(registration_data[field]):
                    return False
            if field in ["last_period_date", "baby_dob", "mama_dob"]:
                if not is_valid_date(registration_data[field]):
                    return False
            if field == "msg_receiver":
                if not is_valid_msg_receiver(registration_data[field]):
                    return False
            if field == "loss_reason":
                if not is_valid_loss_reason(registration_data[field]):
                    return False
            if field in ["hoh_name", "hoh_surname", "mama_name",
                         "mama_surname"]:
                if not is_valid_name(registration_data[field]):
                    return False
            if field == "mama_id_type":
                if not is_valid_id_type(registration_data[field]):
                    return False
            if field == "mama_id_no":
                if not is_valid_id_no(registration_data[field]):
                    return False
        return True

    def validate(self, registration):
        """ Validates that all the required info is provided for a
        prebirth registration.
        """
        data_fields = registration.data.keys()
        fields_general = ["contact", "registered_by", "language", "msg_type"]
        fields_prebirth = ["last_period_date", "msg_receiver"]
        fields_postbirth = ["baby_dob", "msg_receiver"]
        fields_loss = ["loss_reason"]
        fields_hw_id = ["hoh_name", "hoh_surname", "mama_name", "mama_surname",
                        "mama_id_type", "mama_id_no"]
        fields_hw_dob = ["hoh_name", "hoh_surname", "mama_name",
                         "mama_surname", "mama_id_type", "mama_dob"]
        hw_pre_id = list(set(fields_general) | set(fields_prebirth |
                         set(fields_hw_id)))
        hw_pre_dob = list(set(fields_general) | set(fields_prebirth |
                          set(fields_hw_dob)))
        hw_post_id = list(set(fields_general) | set(fields_postbirth |
                          set(fields_hw_id)))
        hw_post_dob = list(set(fields_general) | set(fields_postbirth |
                           set(fields_hw_dob)))
        pbl_pre = list(set(fields_general) | set(fields_prebirth))
        pbl_loss = list(set(fields_general) | set(fields_loss))

        # HW registration, prebirth, id
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_id).issubset(data_fields)):
            if self.check_field_values(hw_pre_id, registration.data):
                print('super')
                pass
            print('1')
        # HW registration, prebirth, dob
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_dob).issubset(data_fields)):
            print('2')
        # HW registration, postbirth, id
        elif (registration.stage == "postbirth" and
              registration.source.authority in ["hw_limited", "hw_full"] and
              set(hw_post_id).issubset(data_fields)):
            print('3')
        # HW registration, postbirth, dob
        elif (registration.stage == "postbirth" and
              registration.source.authority in ["hw_limited", "hw_full"] and
              set(hw_post_dob).issubset(data_fields)):
            print('4')
        # Public registration (currently only prebirth)
        elif (registration.stage == "prebirth" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_pre).issubset(data_fields)):
            print('5')
        elif (registration.stage == "loss" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_loss).issubset(data_fields)):
            print('6')
        else:
            print('invalid data set provided')
        return 'something'

    def run(self, registration_id, **kwargs):
        """ Sets the registration's validated field to True if
        validation is successful.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up the registration")
        registration = Registration.objects.get(id=registration_id)
        print(registration.validated)

        self.validate(registration)

        l.info("Setting the validated field to true")
        registration.validated = True
        registration.save()
        print(registration.validated)

        return "work in progress"

validate_registration = ValidateRegistration()
