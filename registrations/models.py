import uuid

from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.conf import settings
from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Source(models.Model):
    """ The source from which a registation originates.
        The User foreignkey is used to identify the source based on the
        user's api token.
    """
    name = models.CharField(max_length=100, null=False, blank=False)
    user = models.ForeignKey(User, related_name='sources', null=False)
    authority = models.CharField(max_length=30, null=False, blank=False,
                                 choices=settings.AUTHORITY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s" % self.name


class RegistrationQuerySet(models.QuerySet):
    def public_registrations(self):
        """
        Returns all registrations that were done on the public line.
        """
        return self.filter(
            stage='prebirth',
            source__authority__in=['patient', 'advisor'])

    def validated(self):
        """
        Returns only validated registrations.
        """
        return self.filter(validated=True)


@python_2_unicode_compatible
class Registration(models.Model):
    """ A registation submitted via Vumi or other sources.

    After a registation has been created, a task will fire that
    validates if the data provided is sufficient for the stage
    of pregnancy.

    Args:
        stage (str): The stage of pregnancy of the mother
        data (json): Registration info in json format
        validated (bool): True if the registation has been
            validated after creation
        source (object): Auto-completed field based on the Api key
    """

    STAGE_CHOICES = (
        ('prebirth', "Mother is pregnant"),
        ('postbirth', "Baby has been born"),
        ('loss', "Baby loss")
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.CharField(max_length=30, null=False, blank=False,
                             choices=STAGE_CHOICES)
    mother_id = models.CharField(max_length=36, null=False, blank=False)
    data = JSONField(null=True, blank=True)
    validated = models.BooleanField(default=False)
    source = models.ForeignKey(Source, related_name='registrations',
                               null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='registrations_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='registrations_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    objects = RegistrationQuerySet.as_manager()

    def __str__(self):
        return str(self.id)


@receiver(post_save, sender=Registration)
def registration_post_save(sender, instance, created, **kwargs):
    """ Post save hook to fire Registration validation task
    """
    if created:
        from .tasks import validate_registration
        validate_registration.apply_async(
            kwargs={"registration_id": str(instance.id)})


@receiver(post_save, sender=Registration)
def fire_created_metric(sender, instance, created, **kwargs):
    from .tasks import fire_metric
    if created:
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.created.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.created.total.last'
        total = get_or_incr_cache(
            total_key,
            Registration.objects.count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Registration)
def fire_language_metric(sender, instance, created, **kwargs):
    """
    Fires metrics for each language for each subscription, a sum metric for
    the registrations over time, and a last metric for the total count.
    """
    from .tasks import fire_metric, is_valid_lang
    if (created and instance.data and instance.data.get('language') and
            is_valid_lang(instance.data['language'])):
        lang = instance.data['language']
        fire_metric.apply_async(kwargs={
            'metric_name': "registrations.language.%s.sum" % lang,
            'metric_value': 1.0,
        })

        total_key = "registrations.language.%s.total.last" % lang
        total = get_or_incr_cache(
            total_key,
            Registration.objects.filter(data__language=lang).count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Registration)
def fire_source_metric(sender, instance, created, **kwargs):
    """
    Fires metrics for each source for each subscription, a sum metric for
    the registrations over time, and a last metric for the total count.
    """
    from .tasks import fire_metric
    if (created):
        source = instance.source.authority

        fire_metric.apply_async(kwargs={
            'metric_name': "registrations.source.%s.sum" % source,
            'metric_value': 1.0,
        })

        total_key = "registrations.source.%s.total.last" % source
        total = get_or_incr_cache(
            total_key,
            Registration.objects.filter(source__authority=source).count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


def get_or_incr_cache(key, func):
    """
    Used to either get a value from the cache, or if the value doesn't exist
    in the cache, run the function to get a value to use to populate the cache
    """
    value = cache.get(key)
    if value is None:
        value = func()
        cache.set(key, value)
    else:
        cache.incr(key)
        value += 1
    return value


@python_2_unicode_compatible
class SubscriptionRequest(models.Model):
    """ A data model that maps to the Stagebased Store
    Subscription model. Created after a successful Registration
    validation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.CharField(max_length=36, null=False, blank=False)
    messageset = models.IntegerField(null=False, blank=False)
    next_sequence_number = models.IntegerField(default=1, null=False,
                                               blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    schedule = models.IntegerField(default=1)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def serialize_hook(self, hook):
        # optional, there are serialization defaults
        # we recommend always sending the Hook
        # metadata along for the ride as well
        return {
            'hook': hook.dict(),
            'data': {
                'id': str(self.id),
                'identity': self.identity,
                'messageset': self.messageset,
                'next_sequence_number': self.next_sequence_number,
                'lang': self.lang,
                'schedule': self.schedule,
                'metadata': self.metadata,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat()
            }
        }

    def __str__(self):
        return str(self.id)
