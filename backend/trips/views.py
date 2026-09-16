"""Thin API views: validate, call a service, serialize. No business logic."""
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})
