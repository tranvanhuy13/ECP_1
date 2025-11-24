from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import NotificationPreference
from .serializers import NotificationPreferenceSerializer


class NotificationPreferenceView(APIView):

    def get(self, request):
        """
        Get notification preferences for the logged-in user.
        Create defaults automatically if not exist.
        """
        prefs, created = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, many=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        """
        Update preferences (full update).
        """
        prefs, created = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)