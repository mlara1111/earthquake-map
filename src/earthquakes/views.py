from rest_framework import generics
from rest_framework.exceptions import ValidationError

from earthquakes.constants import MAX_RESULTS
from earthquakes.queries import Viewport, get_earthquakes_in_viewport
from earthquakes.serializers import EarthquakeSerializer


class EarthquakeListView(generics.ListAPIView):
    ### Expose earthquake records inside a client-supplied map viewport.
    ### The frontend will provide the viewport coordinates once the map is implemented.
    serializer_class = EarthquakeSerializer

    def get_queryset(self):
        ### Read the four geographic boundaries from the API query parameters.
        min_lat = self.request.query_params.get("min_lat")
        max_lat = self.request.query_params.get("max_lat")
        min_lon = self.request.query_params.get("min_lon")
        max_lon = self.request.query_params.get("max_lon")

        ### Require all four coordinates to define an unambiguous viewport.
        if None in (min_lat, max_lat, min_lon, max_lon):
            raise ValidationError(
                "min_lat, max_lat, min_lon and max_lon are required."
            )

        try:
            viewport = Viewport(
                min_lat=float(min_lat),
                max_lat=float(max_lat),
                min_lon=float(min_lon),
                max_lon=float(max_lon),
            )
        except ValueError:
            raise ValidationError(
                "Viewport coordinates must be valid numbers."
            )

        ### Validate the latitude and longitude ranges.
        if not -90 <= viewport.min_lat <= 90:
            raise ValidationError("min_lat must be between -90 and 90.")

        if not -90 <= viewport.max_lat <= 90:
            raise ValidationError("max_lat must be between -90 and 90.")

        if not -180 <= viewport.min_lon <= 180:
            raise ValidationError("min_lon must be between -180 and 180.")

        if not -180 <= viewport.max_lon <= 180:
            raise ValidationError("max_lon must be between -180 and 180.")

        ### Ensure the minimum coordinates are smaller than the maximum coordinates.
        if viewport.min_lat >= viewport.max_lat:
            raise ValidationError("min_lat must be smaller than max_lat.")

        if viewport.min_lon >= viewport.max_lon:
            raise ValidationError("min_lon must be smaller than max_lon.")

        ### Execute the reusable viewport query using the fixed MVP result limit.
        return get_earthquakes_in_viewport(
            viewport=viewport,
            max_results=MAX_RESULTS,
        )