import datetime
import six  # for Python 2 and 3 string type compatibility

from celery.task import Task
from celery.utils.log import get_task_logger

from .models import Registration


logger = get_task_logger(__name__)


def get_today():
    return datetime.today()


def is_valid_date(date):
    try:
        datetime.datetime.strptime(date, "%Y%m%d")
        return True
    except:
        return False


def is_valid_uuid(id):
    return len(id) == 36 and id[14] == '4' and id[19] in ['a', 'b', '8', '9']


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


def calc_pregnancy_week_lmp(today, lmp):
    """ Calculate how far along the mother's prenancy is in weeks.
    """
    last_period_date = datetime.datetime.strptime(lmp, "%Y%m%d")
    time_diff = today - last_period_date
    preg_weeks = int(time_diff.days / 7)
    # You can't be less than two weeks pregnant
    if preg_weeks <= 1:
        preg_weeks = 2
    return preg_weeks


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
                # Check that if mama_dob is provided, the ID type is correct
                if (field == "mama_dob" and
                   registration_data["mama_id_type"] != "other"):
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
                # Check that if ID no is provided, the ID type is correct
                if not registration_data["mama_id_type"] == "ugandan_id":
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

        # Perhaps the below should rather be hardcoded to save a tiny bit of
        # processing time for each registration
        hw_pre_id = list(set(fields_general) | set(fields_prebirth) |
                         set(fields_hw_id))
        hw_pre_dob = list(set(fields_general) | set(fields_prebirth) |
                          set(fields_hw_dob))
        hw_post_id = list(set(fields_general) | set(fields_postbirth) |
                          set(fields_hw_id))
        hw_post_dob = list(set(fields_general) | set(fields_postbirth) |
                           set(fields_hw_dob))
        pbl_pre = list(set(fields_general) | set(fields_prebirth))
        pbl_loss = list(set(fields_general) | set(fields_loss))

        # HW registration, prebirth, id
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_id).issubset(data_fields)):  # ignore extra data
            if self.check_field_values(hw_pre_id, registration.data):
                registration.data["reg_type"] = "hw_pre_id"
                registration.data["preg_week"] = calc_pregnancy_week_lmp(
                    get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return "Success"
        # HW registration, prebirth, dob
        if (registration.stage == "prebirth" and
                registration.source.authority in ["hw_limited", "hw_full"] and
                set(hw_pre_dob).issubset(data_fields)):
            if self.check_field_values(hw_pre_dob, registration.data):
                registration.data["reg_type"] = "hw_pre_dob"
                registration.data["preg_week"] = calc_pregnancy_week_lmp(
                    get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return "Success"
        # HW registration, postbirth, id
        elif (registration.stage == "postbirth" and
              registration.source.authority in ["hw_limited", "hw_full"] and
              set(hw_post_id).issubset(data_fields)):
            if self.check_field_values(hw_post_id, registration.data):
                registration.data["reg_type"] = "hw_post_id"
                registration.data["baby_age"] = 1  # TODO calc age
                registration.validated = True
                registration.save()
                return "Success"
        # HW registration, postbirth, dob
        elif (registration.stage == "postbirth" and
              registration.source.authority in ["hw_limited", "hw_full"] and
              set(hw_post_dob).issubset(data_fields)):
            if self.check_field_values(hw_post_dob, registration.data):
                registration.data["reg_type"] = "hw_post_dob"
                registration.data["baby_age"] = 1  # TODO calc age
                registration.validated = True
                registration.save()
                return "Success"
        # Public registration (currently only prebirth)
        elif (registration.stage == "prebirth" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_pre).issubset(data_fields)):
            if self.check_field_values(pbl_pre, registration.data):
                registration.data["reg_type"] = "pbl_pre"
                registration.data["preg_week"] = calc_pregnancy_week_lmp(
                    get_today(), registration.data["last_period_date"])
                registration.validated = True
                registration.save()
                return "Success"
        # Loss registration
        elif (registration.stage == "loss" and
              registration.source.authority in ["patient", "advisor"] and
              set(pbl_loss).issubset(data_fields)):
            if self.check_field_values(pbl_loss, registration.data):
                registration.data["reg_type"] = "pbl_loss"
                registration.validated = True
                registration.save()
                return "Success"
        else:
            return "Failure"

    def run(self, registration_id, **kwargs):
        """ Sets the registration's validated field to True if
        validation is successful.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up the registration")
        registration = Registration.objects.get(id=registration_id)
        validation_result = self.validate(registration)

        return "Validation completed - %s" % validation_result

validate_registration = ValidateRegistration()
