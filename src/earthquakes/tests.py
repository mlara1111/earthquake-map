from django.test import TestCase
from rest_framework.test import APIRequestFactory

from earthquakes.constants import MAX_RESULTS
from earthquakes.models import Earthquake, Source
from earthquakes.queries import Viewport, get_earthquakes_in_viewport
from earthquakes.views import EarthquakeListView

class EarthquakeViewportQueryTests(TestCase):
    ### Test the viewport query and API behavior.
    CALIFORNIA_VIEWPORT = Viewport(
        min_lat=32.5,
        max_lat=42.1,
        min_lon=-124.5,
        max_lon=-114.1,
    )

    def setUp(self):
        ### Use the existing USGS source seeded by the migration.
        self.source = Source.objects.get(code="USGS")
        self.factory = APIRequestFactory()

    def create_earthquake(
        self,
        source_event_id,
        latitude,
        longitude,
        magnitude,
        event_date,
    ):
        ### Create a minimal earthquake record for query testing.
        return Earthquake.objects.create(
            source=self.source,
            source_event_id=source_event_id,
            event_date=event_date,
            usgs_updated_date=event_date,
            magnitude=magnitude,
            magnitude_type="ml",
            event_type="earthquake",
            status="reviewed",
            depth_km=10,
            latitude=latitude,
            longitude=longitude,
            geometry=f"SRID=4326;POINT ({longitude} {latitude})",
            tsunami=False,
        )

    def test_returns_only_earthquakes_inside_viewport(self):
        ### Verify that earthquakes outside the viewport are excluded.
        inside = self.create_earthquake(
            source_event_id="inside",
            latitude=36.0,
            longitude=-120.0,
            magnitude=4.0,
            event_date="2026-01-01T00:00:00Z",
        )

        self.create_earthquake(
            source_event_id="outside",
            latitude=45.0,
            longitude=-120.0,
            magnitude=5.0,
            event_date="2026-01-02T00:00:00Z",
        )

        results = get_earthquakes_in_viewport(self.CALIFORNIA_VIEWPORT)

        self.assertEqual(list(results), [inside])

    def test_includes_earthquake_on_viewport_boundary(self):
        ### Verify that an earthquake exactly on the viewport boundary is included.
        boundary_earthquake = self.create_earthquake(
            source_event_id="boundary",
            latitude=32.5,
            longitude=-120.0,
            magnitude=4.0,
            event_date="2026-01-01T00:00:00Z",
        )

        results = get_earthquakes_in_viewport(self.CALIFORNIA_VIEWPORT)

        self.assertIn(boundary_earthquake, results)

    def test_limits_results_to_maximum(self):
        ### Verify that the viewport query never returns more than MAX_RESULTS.
        for index in range(MAX_RESULTS + 10):
            self.create_earthquake(
                source_event_id=f"limit-{index}",
                latitude=36.0,
                longitude=-120.0,
                magnitude=3.0,
                event_date=f"2026-01-{(index % 28) + 1:02d}T00:00:00Z",
            )

        results = get_earthquakes_in_viewport(self.CALIFORNIA_VIEWPORT)

        self.assertEqual(results.count(), MAX_RESULTS)

    def test_orders_by_magnitude_then_event_date(self):
        ### Verify strongest earthquakes appear first and equal magnitudes
        ### are ordered from newest to oldest.
        strongest = self.create_earthquake(
            source_event_id="strongest",
            latitude=36.0,
            longitude=-120.0,
            magnitude=5.0,
            event_date="2026-01-01T00:00:00Z",
        )

        newer_equal = self.create_earthquake(
            source_event_id="newer-equal",
            latitude=36.0,
            longitude=-120.0,
            magnitude=4.0,
            event_date="2026-03-01T00:00:00Z",
        )

        older_equal = self.create_earthquake(
            source_event_id="older-equal",
            latitude=36.0,
            longitude=-120.0,
            magnitude=4.0,
            event_date="2026-02-01T00:00:00Z",
        )

        results = list(
            get_earthquakes_in_viewport(self.CALIFORNIA_VIEWPORT)
        )

        self.assertEqual(
            results,
            [strongest, newer_equal, older_equal],
        )

    def test_api_returns_maximum_number_of_viewport_results(self):
        ### Verify that the API endpoint applies the viewport and maximum result limit.
        for index in range(MAX_RESULTS + 1):
            self.create_earthquake(
                source_event_id=f"api-limit-{index}",
                latitude=36.0,
                longitude=-120.0,
                magnitude=3.0,
                event_date=f"2026-01-{(index % 28) + 1:02d}T00:00:00Z",
            )

        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "32.5",
                "max_lat": "42.1",
                "min_lon": "-124.5",
                "max_lon": "-114.1",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), MAX_RESULTS)

    def test_api_rejects_missing_viewport_parameter(self):
        ### Verify that all four viewport coordinates are required.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "32.5",
                "max_lat": "42.1",
                "min_lon": "-124.5",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_api_rejects_non_numeric_coordinate(self):
        ### Verify that viewport coordinates must be numeric.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "invalid",
                "max_lat": "42.1",
                "min_lon": "-124.5",
                "max_lon": "-114.1",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_api_rejects_invalid_latitude(self):
        ### Verify that latitude values must be within the valid geographic range.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "-91",
                "max_lat": "42.1",
                "min_lon": "-124.5",
                "max_lon": "-114.1",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_api_rejects_invalid_longitude(self):
        ### Verify that longitude values must be within the valid geographic range.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "32.5",
                "max_lat": "42.1",
                "min_lon": "-181",
                "max_lon": "-114.1",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_api_rejects_reversed_latitude_range(self):
        ### Verify that minimum latitude must be smaller than maximum latitude.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "42.1",
                "max_lat": "32.5",
                "min_lon": "-124.5",
                "max_lon": "-114.1",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    def test_api_rejects_reversed_longitude_range(self):
        ### Verify that minimum longitude must be smaller than maximum longitude.
        request = self.factory.get(
            "/api/earthquakes/",
            {
                "min_lat": "32.5",
                "max_lat": "42.1",
                "min_lon": "-114.1",
                "max_lon": "-124.5",
            },
        )

        response = EarthquakeListView.as_view()(request)

        self.assertEqual(response.status_code, 400)