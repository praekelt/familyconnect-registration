from future.standard_library import install_aliases
install_aliases()  # noqa
from urllib.parse import urlparse

from celery.task import Task
from django.conf import settings
from seed_services_client import IdentityStoreApiClient

from .models import Parish


class SyncLocations(Task):
    """
    Has a look at all the identity store identities, and ensures that all of
    the locations assigned to identities appear in the list of locations.
    """
    name = 'locations.tasks.sync_locations'

    def get_identities(self, client):
        """
        Returns an iterator over all the identities in the identity store
        specified by 'client'.
        """
        identities = client.get_identities()
        while True:
            for identity in identities.get('results', []):
                yield identity
            # If there is a next page, extract the querystring and get it
            if identities.get('next') is not None:
                qs = urlparse(identities['next']).query
                identities = client.get_identities(params=qs)
            else:
                break

    def run(self, **kwargs):
        l = self.get_logger(**kwargs)
        l.info('Starting location import')
        imported_count = 0
        client = IdentityStoreApiClient(
            settings.IDENTITY_STORE_TOKEN, settings.IDENTITY_STORE_URL)
        for identity in self.get_identities(client):
            parish = identity.get('details', {}).get('parish')
            if parish is not None:
                _, created = Parish.objects.get_or_create(name=parish.title())
                if created:
                    imported_count += 1
        l.info('Imported {} locations'.format(imported_count))
        return imported_count

sync_locations = SyncLocations()
