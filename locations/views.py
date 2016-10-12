from django.contrib.postgres.search import TrigramSimilarity
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from .models import Parish
from .serializers import ParishSerializer


class ParishSearch(ListModelMixin, GenericViewSet):
    """
    Viewset to search through the list of parishes.

    querystring parameters:
      name - The name of the Parish to search for
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = ParishSerializer

    def get_queryset(self):
        name = self.request.query_params.get('name', None)

        if name is None:
            return Parish.objects.none()

        qs = Parish.objects.all()
        qs = qs.annotate(similarity=TrigramSimilarity('name', name))
        qs = qs.filter(similarity__gt=0.3)
        qs = qs.order_by('-similarity')

        return qs
