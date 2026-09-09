"""
URL configuration for the config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""

from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path

from earthquakes.views import EarthquakeListView
from map.views import map_view


urlpatterns = [
    path("admin/", admin.site.urls),

    ### Expose the read-only earthquake collection through the API.
    ### The frontend supplies the viewport coordinates through query parameters.
    path("api/earthquakes/", EarthquakeListView.as_view(), name="earthquake-list"),

    ### Render the main earthquake map page.
    ### Earthquake data is loaded asynchronously by the frontend.
    path("", map_view, name="map"),
]


### Serve static assets explicitly during local development.
### This makes the development static-file route explicit instead of relying
### on runserver's automatic static-file handling.
urlpatterns += staticfiles_urlpatterns()