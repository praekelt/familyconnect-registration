from celery.task import Task
from celery.utils.log import get_task_logger

from .models import Registration


logger = get_task_logger(__name__)


class ValidateRegistration(Task):
    """ Task to validate a registration model entry's registration
    data.
    """
    name = "familyconnect_registration.registrations.tasks.\
    validate_registration"

    def validate_prebirth(registration_data):
        """ Validates that all the required info is provided for a
        prebirth registration.
        """
        required_fields = ["last_period_date"]

    def run(self, registration_id, **kwargs):
        """ Sets the registration's validated field to True if
        validation is successful.
        """
        l = self.get_logger(**kwargs)
        l.info("Looking up the registration")
        registration = Registration.objects.get(id=registration_id)
        print(registration.validated)

        l.info("Setting the validated field to true")
        registration.validated = True
        registration.save()
        print(registration.validated)

        return "work in progress"

validate_registration = ValidateRegistration()
