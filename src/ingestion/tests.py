from datetime import datetime, timezone
from unittest.mock import Mock

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection
from django.test import TestCase

from earthquakes.models import Earthquake, Source
from ingestion.spatial_assigner import SpatialAssigner

class SpatialAssignerTests(TestCase):
    ### Test spatial assignment using controlled PostGIS geometries.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ### Create the boundary tables required by SpatialAssigner in the test database.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE tbl_boundary_country (
                    id BIGSERIAL PRIMARY KEY,
                    source_boundary_id VARCHAR(50) NOT NULL,
                    country VARCHAR(150) NOT NULL,
                    country_code VARCHAR(10) NOT NULL,
                    geometry geometry(MultiPolygon,4326) NOT NULL,
                    UNIQUE (country_code)
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX idx_test_boundary_country_geometry
                ON tbl_boundary_country
                USING GIST (geometry);
                """
            )

            cursor.execute(
                """
                CREATE TABLE tbl_boundary_region (
                    id BIGSERIAL PRIMARY KEY,
                    source_boundary_id VARCHAR(50) NOT NULL,
                    country_code VARCHAR(10) NOT NULL,
                    region VARCHAR(150) NOT NULL,
                    region_code VARCHAR(20),
                    geometry geometry(MultiPolygon,4326) NOT NULL,
                    UNIQUE (source_boundary_id)
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX idx_test_boundary_region_geometry
                ON tbl_boundary_region
                USING GIST (geometry);
                """
            )

        ### Create a simple country polygon covering the test points.
        country_geometry = MultiPolygon(
            Polygon(
                (
                    (-10, 40),
                    (10, 40),
                    (10, 50),
                    (-10, 50),
                    (-10, 40),
                )
            )
        )

        ### Create an ADM1 polygon covering only part of the country.
        region_geometry = MultiPolygon(
            Polygon(
                (
                    (-10, 40),
                    (0, 40),
                    (0, 50),
                    (-10, 50),
                    (-10, 40),
                )
            )
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tbl_boundary_country (
                    source_boundary_id,
                    country,
                    country_code,
                    geometry
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    ST_GeomFromText(%s, 4326)
                );
                """,
                [
                    "TEST-COUNTRY-001",
                    "Test Country",
                    "TST",
                    country_geometry.wkt,
                ],
            )

            cursor.execute(
                """
                INSERT INTO tbl_boundary_region (
                    source_boundary_id,
                    country_code,
                    region,
                    region_code,
                    geometry
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    ST_GeomFromText(%s, 4326)
                );
                """,
                [
                    "TEST-REGION-001",
                    "TST",
                    "Test Region",
                    "TST-01",
                    region_geometry.wkt,
                ],
            )

    @classmethod
    def tearDownClass(cls):
        ### Remove the boundary tables created specifically for the test database.
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS tbl_boundary_region;")
            cursor.execute("DROP TABLE IF EXISTS tbl_boundary_country;")

        super().tearDownClass()

    def create_earthquake(self, longitude, latitude):
        ### Create a minimal earthquake event for spatial testing.
        source, _ = Source.objects.get_or_create(
            code="TEST",
            defaults={
                "name": "Test Source",
                "url": "https://example.com/",
            },
        )

        return Earthquake.objects.create(
            source=source,
            source_event_id=f"test-{longitude}-{latitude}",
            event_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usgs_updated_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            magnitude=3.0,
            magnitude_type="ml",
            event_type="earthquake",
            status="reviewed",
            depth_km=10.0,
            latitude=latitude,
            longitude=longitude,
            geometry=Point(longitude, latitude, srid=4326),
            tsunami=False,
        )

    def test_assigns_country_and_region(self):
        ### A point inside both ADM0 and ADM1 receives all spatial attributes.
        earthquake = self.create_earthquake(-5, 45)

        assigned = SpatialAssigner().assign_earthquake(earthquake.id)

        self.assertTrue(assigned)

        earthquake.refresh_from_db()

        self.assertEqual(earthquake.country, "Test Country")
        self.assertEqual(earthquake.country_code, "TST")
        self.assertEqual(earthquake.region, "Test Region")
        self.assertEqual(earthquake.region_code, "TST-01")

    def test_assigns_country_without_region(self):
        ### A point inside ADM0 but outside ADM1 receives only country data.
        earthquake = self.create_earthquake(5, 45)

        assigned = SpatialAssigner().assign_earthquake(earthquake.id)

        self.assertTrue(assigned)

        earthquake.refresh_from_db()

        self.assertEqual(earthquake.country, "Test Country")
        self.assertEqual(earthquake.country_code, "TST")
        self.assertIsNone(earthquake.region)
        self.assertIsNone(earthquake.region_code)

    def test_point_outside_adm0_remains_unassigned(self):
        ### A point outside ADM0 remains without spatial attributes.
        earthquake = self.create_earthquake(20, 45)

        assigned = SpatialAssigner().assign_earthquake(earthquake.id)

        self.assertFalse(assigned)

        earthquake.refresh_from_db()

        self.assertIsNone(earthquake.country)
        self.assertIsNone(earthquake.country_code)
        self.assertIsNone(earthquake.region)
        self.assertIsNone(earthquake.region_code)

    def test_reassignment_clears_previous_region(self):
        ### Reassignment must remove stale ADM1 values when the new point
        ### is outside the previous region.
        earthquake = self.create_earthquake(-5, 45)

        assigner = SpatialAssigner()

        self.assertTrue(assigner.assign_earthquake(earthquake.id))

        earthquake.refresh_from_db()

        self.assertEqual(earthquake.region, "Test Region")
        self.assertEqual(earthquake.region_code, "TST-01")

        ### Move the event outside ADM1 but keep it inside ADM0.
        earthquake.geometry = Point(5, 45, srid=4326)
        earthquake.latitude = 45
        earthquake.longitude = 5
        earthquake.save()

        self.assertTrue(assigner.assign_earthquake(earthquake.id))

        earthquake.refresh_from_db()

        self.assertEqual(earthquake.country_code, "TST")
        self.assertIsNone(earthquake.region)
        self.assertIsNone(earthquake.region_code)


class EarthquakeImporterTests(SpatialAssignerTests):
    ### Test the integration between earthquake persistence and spatial assignment.

    def test_new_event_is_spatially_assigned(self):
        ### A newly imported event must receive its administrative attributes.
        from ingestion.earthquake_importer import EarthquakeImporter

        source, _ = Source.objects.get_or_create(
            code="USGS",
            defaults={
                "name": "United States Geological Survey",
                "url": "https://earthquake.usgs.gov/",
            },
        )

        importer = EarthquakeImporter()

        data = {
            "source_event_id": "integration-test-001",
            "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "usgs_updated_date": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            "magnitude": 3.5,
            "magnitude_type": "ml",
            "event_type": "earthquake",
            "status": "reviewed",
            "depth_km": 10.0,
            "latitude": 45.0,
            "longitude": -5.0,
            "geometry": Point(-5, 45, srid=4326),
            "place": "Test location",
            "tsunami": False,
        }

        result = importer.import_event(data)

        self.assertEqual(result, "created")

        earthquake = Earthquake.objects.get(
            source=source,
            source_event_id="integration-test-001",
        )

        self.assertEqual(earthquake.country, "Test Country")
        self.assertEqual(earthquake.country_code, "TST")
        self.assertEqual(earthquake.region, "Test Region")
        self.assertEqual(earthquake.region_code, "TST-01")

    def test_updated_event_is_reassigned(self):
        ### Updating an event must recalculate its administrative attributes
        ### when its geometry changes.
        from ingestion.earthquake_importer import EarthquakeImporter

        source, _ = Source.objects.get_or_create(
            code="USGS",
            defaults={
                "name": "United States Geological Survey",
                "url": "https://earthquake.usgs.gov/",
            },
        )

        earthquake = Earthquake.objects.create(
            source=source,
            source_event_id="integration-test-002",
            event_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usgs_updated_date=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            magnitude=3.0,
            magnitude_type="ml",
            event_type="earthquake",
            status="reviewed",
            depth_km=10.0,
            latitude=45.0,
            longitude=-5.0,
            geometry=Point(-5, 45, srid=4326),
            country="Test Country",
            country_code="TST",
            region="Test Region",
            region_code="TST-01",
            tsunami=False,
        )

        data = {
            "source_event_id": "integration-test-002",
            "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "usgs_updated_date": datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            "magnitude": 3.1,
            "magnitude_type": "ml",
            "event_type": "earthquake",
            "status": "reviewed",
            "depth_km": 10.0,
            "latitude": 45.0,
            "longitude": 5.0,
            "geometry": Point(5, 45, srid=4326),
            "place": "Updated test location",
            "tsunami": False,
        }

        importer = EarthquakeImporter()

        result = importer.import_event(data)

        self.assertEqual(result, "updated")

        earthquake.refresh_from_db()

        self.assertEqual(earthquake.country, "Test Country")
        self.assertEqual(earthquake.country_code, "TST")
        self.assertIsNone(earthquake.region)
        self.assertIsNone(earthquake.region_code)

class USGSPaginationTests(TestCase):
    ### Test USGS pagination and result counter aggregation.

    def test_import_offset_accumulates_results_from_all_pages(self):
        ### Simulate multiple USGS pages and verify that import results
        ### are accumulated across all pages.
        from unittest.mock import patch

        from ingestion.management.commands.ingest_usgs import Command

        command = Command()

        client = Mock()
        importer = Mock()

        client.MAX_RESULTS = 2

        client.get_events.side_effect = [
            {
                "features": [
                    {"id": "event-3"},
                    {"id": "event-4"},
                ]
            },
            {
                "features": [
                    {"id": "event-5"},
                ]
            },
        ]

        importer.import_event.side_effect = [
            "created",
            "updated",
            "skipped",
        ]

        ### Mock the transformer because this test is specifically about
        ### pagination and counter aggregation, not transformation.
        with patch(
            "ingestion.management.commands.ingest_usgs.EarthquakeTransformer.transform",
            side_effect=[
                {"source_event_id": "event-3"},
                {"source_event_id": "event-4"},
                {"source_event_id": "event-5"},
            ],
        ):
            result = command.import_offset(
                client,
                importer,
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                2.5,
                0,
            )

        self.assertEqual(
            result,
            {
                "created": 1,
                "updated": 1,
                "unchanged": 0,
                "skipped": 1,
            },
        )

        self.assertEqual(client.get_events.call_count, 2)
        self.assertEqual(importer.import_event.call_count, 3)