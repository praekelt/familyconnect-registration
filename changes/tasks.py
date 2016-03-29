from celery.task import Task

from familyconnect_registration import utils
from registrations.models import Registration, SubscriptionRequest
from .models import Change


class ImplementAction(Task):
    """ Task to apply a Change action.
    """
    name = "familyconnect_registration.changes.tasks.implement_action"

    def change_baby(self, change):
        # Get current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's identity
        mother = utils.get_identity(change.mother_id)

        # Get mother's registration
        registration = Registration.objects.get(mother_id=change.mother_id)

        short_name = utils.get_messageset_short_name(
            registration.data["msg_receiver"],
            'postbirth',
            registration.source.authority)

        msgset_id, msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(short_name, 0)

        # Make new subscription request object
        mother_sub = {
            "contact": registration.mother_id,
            "messageset": msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": mother["details"]["preferred_language"],
            "schedule": msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        return "Change baby completed"

    def change_loss(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's identity
        mother = utils.get_identity(change.mother_id)

        stage = 'miscarriage'
        weeks = 0
        voice_days = mother["details"]["preferred_msg_days"]
        voice_times = mother["details"]["preferred_msg_times"]

        mother_short_name = utils.get_messageset_short_name(
            stage, 'mother', mother["details"]["preferred_msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(mother_short_name, weeks)

        # Make new subscription request object
        mother_sub = {
            "contact": change.mother_id,
            "messageset": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": mother["details"]["preferred_language"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        # Get mother's registration
        registration = Registration.objects.get(mother_id=change.mother_id)
        if registration.data["msg_receiver"] != 'mother_only':
            # Get household's current subscriptions
            subscriptions = utils.get_subscriptions(
                mother["details"]["linked_to"])
            # Deactivate subscriptions
            for subscription in subscriptions:
                utils.deactivate_subscription(subscription)

        return "Change loss completed"

    def change_language(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Patch subscriptions languages
        for subscription in subscriptions:
            utils.patch_subscription(
                subscription, {"lang": change.data["new_language"]})

        if change.data["household_id"]:
            # Get household's current subscriptions
            subscriptions = utils.get_subscriptions(
                change.data["household_id"])
            # Patch subscriptions languages
            for subscription in subscriptions:
                utils.patch_subscription(
                    subscription, {"lang": change.data["new_language"]})

        return "Change language completed"

    def unsubscribe(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(
            change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)

        return "Unsubscribe completed"

    def run(self, change_id, **kwargs):
        """ Implements the appropriate action
        """
        change = Change.objects.get(id=change_id)

        result = {
            'change_baby': self.change_baby,
            'change_loss': self.change_loss,
            'change_language': self.change_language,
            'unsubscribe': self.unsubscribe,
        }.get(change.action, None)(change)
        return result

implement_action = ImplementAction()
