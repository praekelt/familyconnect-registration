from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Record


class RecordPost(APIView):

    """ Webhook listener for identities needing a unique ID
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Accepts and creates a new unique ID record
        """
        if "identity" in request.data["data"]:
            Record.objects.create(**request.data["data"])
            # Return
            status = 201
            accepted = {"accepted": True}
            return Response(accepted, status=status)
        else:
            # Return
            status = 400
            accepted = {"identity": ['This field is required.']}
            return Response(accepted, status=status)
