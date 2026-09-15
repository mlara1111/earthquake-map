from decimal import Decimal

from rest_framework import serializers

from earthquakes.models import Earthquake


class EarthquakeSerializer(serializers.ModelSerializer):
    magnitude = serializers.SerializerMethodField()

    ### Expose only the fields required by the API.
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

    def get_magnitude(self, obj):
        ### Preserve null magnitudes as null in the API response.
        if obj.magnitude is None:
            return None

        ### The database keeps the original USGS precision.
        ### The API exposes magnitude rounded to one decimal place.
        return float(
            obj.magnitude.quantize(
                Decimal("0.1")
            )
        )