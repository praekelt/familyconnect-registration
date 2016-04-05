from .models import Record
from rest_framework import serializers


class RecordSerializer(serializers.ModelSerializer):

    class Meta:
        model = Record
        read_only_fields = ('id')
        fields = ('id', 'identity', 'created_at', 'created_by')
