from .models import Record
from rest_framework import mixins, generics
from rest_framework.permissions import IsAuthenticated
from .serializers import RecordSerializer


class RecordPost(mixins.CreateModelMixin, generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Record.objects.all()
    serializer_class = RecordSerializer

    # TODO make this work in test harness, works in production
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user,
    #                     updated_by=self.request.user)

    # def perform_update(self, serializer):
    #     serializer.save(updated_by=self.request.user)
