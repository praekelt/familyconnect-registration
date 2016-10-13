from rest_framework.serializers import ModelSerializer

from .models import Parish


class ParishSerializer(ModelSerializer):
    class Meta:
        model = Parish
        fields = ('name',)
