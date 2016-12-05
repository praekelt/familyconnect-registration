import pika
from django.conf import settings
from functools import partial

from familyconnect_registration import utils

from .models import Registration


class MetricGenerator(object):
    def __init__(self):
        for language in settings.LANGUAGES:
            setattr(
                self, 'registrations_language_{}_sum'.format(language),
                partial(self.registrations_language_sum, language)
            )
            setattr(
                self, 'registrations_language_{}_total_last'.format(language),
                partial(self.registrations_language_total_last, language)
            )

    def generate_metric(self, name, start, end):
        """
        Generates a metric value for the given parameters.

        args:
            name: The name of the metric
            start: Datetime for where the metric window starts
            end: Datetime for where the metric window ends
        """
        metric_func = getattr(self, name.replace('.', '_'))
        return metric_func(start, end)

    def registrations_created_sum(self, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_created_total_last(self, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .count()

    def registrations_language_sum(self, language, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(data__language=language)\
            .count()

    def registrations_language_total_last(self, language, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(data__language=language)\
            .count()

    def registrations_source_hwc_sum(self, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(source__authority__in=['hw_limited', 'hw_full'])\
            .count()

    def registrations_source_hwc_total_last(self, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(source__authority__in=['hw_limited', 'hw_full'])\
            .count()

    def registrations_source_public_sum(self, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(source__authority__in=['patient', 'advisor'])\
            .count()

    def registrations_source_public_total_last(self, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(source__authority__in=['patient', 'advisor'])\
            .count()


def send_metric(amqp_channel, prefix, name, value, timestamp):
    timestamp = utils.timestamp_to_epoch(timestamp)

    if prefix:
        name = '{}.{}'.format(prefix, name)

    amqp_channel.basic_publish(
        'graphite', name, '{} {}'.format(float(value), int(timestamp)),
        pika.BasicProperties(content_type='text/plain', delivery_mode=2))
