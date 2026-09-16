"""Root URLconf: includes trips.urls under api/, with JSON 404 and 500 pages for the API."""
from django.urls import include, path

urlpatterns = [
    path("api/", include("trips.urls")),
]

handler404 = "trips.exceptions.json_not_found"
handler500 = "trips.exceptions.json_server_error"
