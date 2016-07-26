import django_filters
from django.contrib.auth.models import User, Group
from rest_hooks.models import Hook
from rest_framework import viewsets, mixins, generics, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import Source, Registration
from .serializers import (UserSerializer, GroupSerializer,
                          SourceSerializer, RegistrationSerializer,
                          HookSerializer)


class HookViewSet(viewsets.ModelViewSet):
    """
    Retrieve, create, update or destroy webhooks.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Hook.objects.all()
    serializer_class = HookSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserViewSet(viewsets.ReadOnlyModelViewSet):

    """
    API endpoint that allows users to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = User.objects.all()
    serializer_class = UserSerializer


class GroupViewSet(viewsets.ReadOnlyModelViewSet):

    """
    API endpoint that allows groups to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class SourceViewSet(viewsets.ModelViewSet):

    """
    API endpoint that allows sources to be viewed or edited.
    """
    permission_classes = (IsAdminUser,)
    queryset = Source.objects.all()
    serializer_class = SourceSerializer


class RegistrationPost(mixins.CreateModelMixin, generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer

    def post(self, request, *args, **kwargs):
        # load the users sources - posting users should only have one source
        source = Source.objects.get(user=self.request.user)
        request.data["source"] = source.id
        return self.create(request, *args, **kwargs)

    # TODO make this work in test harness, works in production
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user,
    #                     updated_by=self.request.user)

    # def perform_update(self, serializer):
    #     serializer.save(updated_by=self.request.user)


class RegistrationFilter(filters.FilterSet):
    """Filter for registrations created, using ISO 8601 formatted dates"""
    created_before = django_filters.IsoDateTimeFilter(name="created_at",
                                                      lookup_type="lte")
    created_after = django_filters.IsoDateTimeFilter(name="created_at",
                                                     lookup_type="gte")

    class Meta:
        model = Registration
        ('stage', 'mother_id', 'validated', 'source', 'created_at')
        fields = ['stage', 'mother_id', 'validated', 'source',
                  'created_before', 'created_after']


class RegistrationGetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Registrations to be viewed.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    filter_class = RegistrationFilter
