"""Root URLconf: includes trips.urls under api/ and nothing else."""
from django.urls import include, path

urlpatterns = [
    path("api/", include("trips.urls")),
]
