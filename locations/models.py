from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Parish(models.Model):
    """
    Stores information on the parish to search through later.
    """
    name = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.name
