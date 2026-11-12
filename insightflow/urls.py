"""InsightFlow URL configuration."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("projects/", include("projects.urls")),
    path("", include("accounts.urls")),
]
