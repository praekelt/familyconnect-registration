try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.contrib.auth.models import User
from django.test import TestCase

from .metrics import MetricGenerator, send_metric
from .tests import AuthenticatedAPITestCase
from .models import Source, Registration
from familyconnect_registration import utils


class MetricsGeneratorTests(AuthenticatedAPITestCase):

    def setUp(self):
        super(MetricsGeneratorTests, self).setUp()

    def tearDown(self):
        super(MetricsGeneratorTests, self).tearDown()

    def test_generate_metric(self):
        """
        The generate_metric function should call the correct function with the
        correct start and end datetimes.
        """
        generator = MetricGenerator()
        generator.foo_bar = mock.MagicMock()
        start = datetime(2016, 10, 26)
        end = datetime(2016, 10, 26)
        generator.generate_metric('foo.bar', start, end)

        generator.foo_bar.assert_called_once_with(start, end)

    def create_registration_on(self, timestamp, source, **kwargs):
        r = Registration.objects.create(
            mother_id='motherid', source=source, data=kwargs)
        r.created_at = timestamp
        r.save()
        return r

    def test_registrations_created_sum(self):
        """
        Should return the amount of registrations in the given timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 15), source)  # On
        self.create_registration_on(datetime(2016, 10, 20), source)  # In
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_sum(start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_created_total_last(self):
        """
        Should return the total amount of registrations at the 'end' point in
        time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_total_last(
            start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_language_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific language
        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2015, 10, 15)
        end = datetime(2015, 10, 25)

        self.create_registration_on(
            datetime(2015, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2015, 10, 15), source, language='eng')  # On
        self.create_registration_on(
            datetime(2015, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2015, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2015, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_language_sum(
            'eng', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_language_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given language
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='cgg')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_language_total_last(
            'eng', start, end)
        self.assertEqual(reg_count, 3)

    def test_registrations_source_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific source
        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2015, 10, 15)
        end = datetime(2015, 10, 25)

        self.create_registration_on(
            datetime(2015, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2015, 10, 15), source, language='eng')  # On
        self.create_registration_on(
            datetime(2015, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2015, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2015, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_source_sum(
            'hw_full', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_source_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given source
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)
        wrong_source = Source.objects.create(
            name='TestSource 2', authority='patient', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), wrong_source, language='eng')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_source_total_last(
            'hw_full', start, end)
        self.assertEqual(reg_count, 3)

    def test_that_all_metrics_are_present(self):
        """
        We need to make sure that we have a function for each of the metrics.
        """
        user = User.objects.create(username='user1')
        Source.objects.create(
            name='TestSource', authority='hw_full', user=user)
        for metric in utils.get_available_metrics():
            self.assertTrue(callable(getattr(
                MetricGenerator(), metric.replace('.', '_'))))


class SendMetricTests(TestCase):
    def test_send_metric(self):
        """
        The send_metric function should publish the correct message to the
        correct exchange, using the provided channel.
        """
        channel = mock.MagicMock()
        send_metric(
            channel, '', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')

    def test_send_metric_prefix(self):
        """
        The send_metric function should add the correct prefix tot he metric
        name that it sends.
        """
        channel = mock.MagicMock()
        send_metric(
            channel, 'test.prefix', 'foo.bar', 17,
            datetime.utcfromtimestamp(1317))

        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'test.prefix.foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')
