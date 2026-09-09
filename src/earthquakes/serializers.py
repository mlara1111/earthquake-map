from rest_framework import serializers

from earthquakes.models import Earthquake

class EarthquakeSerializer(serializers.ModelSerializer):
    ### Expose only the fields required by the MVP API.
    ### This keeps the public API contract explicit instead of exposing
    ### every field currently available in the database model.
    class Meta:
        model = Earthquake
        fields = [
            "id",
            "event_date",
            "magnitude",
            "magnitude_type",
            "depth_km",
            "latitude",
            "longitude",
            "place",
            "country",
            "country_code",
            "region",
            "region_code",
            "event_type",
            "status",
            "tsunami",
            "usgs_url",
        ]