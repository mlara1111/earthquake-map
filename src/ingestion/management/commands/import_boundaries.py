import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection

from ingestion.geoboundaries_downloader import GeoBoundariesDownloader

class Command(BaseCommand):
    help = "Import administrative boundaries from geoBoundaries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--level",
            choices=["ADM0", "ADM1"],
            default="ADM0",
        )

        parser.add_argument(
            "--iso",
            help="ISO 3166-1 alpha-3 country code.",
        )

        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip boundaries already imported.",
        )

    def handle(self, *args, **options):
        level = options["level"]
        iso_filter = options["iso"]
        skip_existing = options["skip_existing"]

        downloader = GeoBoundariesDownloader(
            "/app/data/boundaries"
        )

        boundaries = downloader.get_metadata(level)

        ### Filter boundaries by ISO country code when requested.
        if iso_filter:
            boundaries = [
                boundary
                for boundary in boundaries
                if boundary["boundaryISO"] == iso_filter
            ]

            ### No boundary was found for the requested country.
            if not boundaries:
                raise ValueError(
                    f"Boundary not found: {level}/{iso_filter}"
                )

            ### geoBoundaries may contain multiple ADM1 datasets for the same ISO.
            ### Select the dataset with the highest number of administrative units.
            if level == "ADM1" and len(boundaries) > 1:
                boundaries.sort(
                    key=lambda boundary: int(
                        boundary.get("admUnitCount", 0)
                    ),
                    reverse=True,
                )

                boundaries = boundaries[:1]

        self.stdout.write(
            f"Found {len(boundaries)} {level} boundaries."
        )

        for number, boundary in enumerate(boundaries, start=1):
            iso = boundary["boundaryISO"]

            self.stdout.write(
                f"[{number}/{len(boundaries)}] Processing {iso}..."
            )

            if skip_existing and self.boundary_exists(level, iso):
                self.stdout.write(
                    f"  Skipping {iso}: already imported."
                )
                continue

            directory = downloader.download_boundary(boundary)

            shp_files = list(directory.glob("*.shp"))

            if not shp_files:
                raise RuntimeError(
                    f"No Shapefile found for {level}/{iso}"
                )

            shp_file = self.select_main_shapefile(
                shp_files,
                iso,
                level,
            )

            self.import_shapefile(
                shp_file,
                boundary,
                level,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{level} import completed."
            )
        )

    def boundary_exists(self, level, iso):
        with connection.cursor() as cursor:
            if level == "ADM0":
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM tbl_boundary_country
                        WHERE country_code = %s
                    );
                    """,
                    [iso],
                )
            else:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM tbl_boundary_region
                        WHERE country_code = %s
                    );
                    """,
                    [iso],
                )

            return cursor.fetchone()[0]

    @staticmethod
    def select_main_shapefile(shp_files, iso, level):
        expected_name = (
            f"geoBoundaries-{iso}-{level}.shp"
        )

        for shp_file in shp_files:
            if shp_file.name == expected_name:
                return shp_file

        return shp_files[0]

    def get_postgres_connection_string(self):
        return (
            f"PG:host={os.getenv('POSTGRES_HOST', 'postgres')} "
            f"port={os.getenv('POSTGRES_PORT', '5432')} "
            f"dbname={os.getenv('POSTGRES_DB')} "
            f"user={os.getenv('POSTGRES_USER')}"
        )

    def import_shapefile(self, shp_file, boundary, level):
        if level == "ADM0":
            staging_table = "staging_boundary_country"
            target_table = "tbl_boundary_country"
        else:
            staging_table = "staging_boundary_region"
            target_table = "tbl_boundary_region"

        with connection.cursor() as cursor:
            cursor.execute(
                f"DROP TABLE IF EXISTS {staging_table};"
            )

        connection.close()

        subprocess.run(
            [
                "ogr2ogr",
                "-f",
                "PostgreSQL",
                self.get_postgres_connection_string(),
                str(shp_file),
                "-nln",
                staging_table,
                "-overwrite",
                "-nlt",
                "PROMOTE_TO_MULTI",
                "-t_srs",
                "EPSG:4326",
            ],
            check=True,
            env={
                **os.environ,
                "PGPASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            },
        )

        if level == "ADM0":
            self.import_adm0(boundary, staging_table)
        else:
            self.import_adm1(boundary, staging_table)

    def import_adm0(self, boundary, staging_table):
        iso = boundary["boundaryISO"]

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO tbl_boundary_country (
                    source_boundary_id,
                    country,
                    country_code,
                    geometry,
                    boundary_year,
                    boundary_source,
                    boundary_license,
                    boundary_build_date
                )
                SELECT
                    shapeid,
                    shapename,
                    %s,
                    wkb_geometry,
                    %s,
                    %s,
                    %s,
                    %s
                FROM {staging_table}
                ON CONFLICT (country_code)
                DO UPDATE SET
                    source_boundary_id = EXCLUDED.source_boundary_id,
                    country = EXCLUDED.country,
                    geometry = EXCLUDED.geometry,
                    boundary_year = EXCLUDED.boundary_year,
                    boundary_source = EXCLUDED.boundary_source,
                    boundary_license = EXCLUDED.boundary_license,
                    boundary_build_date = EXCLUDED.boundary_build_date,
                    updated_date = CURRENT_TIMESTAMP;
                """,
                [
                    iso,
                    self.parse_year(
                        boundary["boundaryYearRepresented"]
                    ),
                    boundary["boundarySource"],
                    boundary["boundaryLicense"],
                    self.parse_build_date(
                        boundary["buildDate"]
                    ),
                ],
            )

            cursor.execute(
                """
                UPDATE tbl_boundary_country
                SET geometry_simplified =
                    ST_SimplifyPreserveTopology(
                        geometry,
                        0.01
                    )
                WHERE country_code = %s;
                """,
                [iso],
            )

    def import_adm1(self, boundary, staging_table):
        iso = boundary["boundaryISO"]

        directory = (
            Path("/app/data/boundaries")
            / "ADM1"
            / iso
        )

        simplified_file = (
            directory
            / f"geoBoundaries-{iso}-ADM1_simplified.geojson"
        )

        if not simplified_file.exists():
            raise RuntimeError(
                f"Simplified GeoJSON not found: {simplified_file}"
            )

        simplified_staging_table = (
            "staging_boundary_region_simplified"
        )

        # ---------------------------------------------------------
        # Import simplified geometry into a separate staging table
        # ---------------------------------------------------------

        with connection.cursor() as cursor:
            cursor.execute(
                f"DROP TABLE IF EXISTS "
                f"{simplified_staging_table};"
            )

        connection.close()

        subprocess.run(
            [
                "ogr2ogr",
                "-f",
                "PostgreSQL",
                self.get_postgres_connection_string(),
                str(simplified_file),
                "-nln",
                simplified_staging_table,
                "-overwrite",
                "-nlt",
                "PROMOTE_TO_MULTI",
                "-t_srs",
                "EPSG:4326",
            ],
            check=True,
            env={
                **os.environ,
                "PGPASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            }
        )

        # ---------------------------------------------------------
        # Insert original + official simplified geometry
        #
        # Both geoBoundaries files preserve feature order.
        # We therefore associate the geometries using ROW_NUMBER().
        # ---------------------------------------------------------

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO tbl_boundary_region (
                    source_boundary_id,
                    country_code,
                    region,
                    region_code,
                    geometry,
                    geometry_simplified,
                    boundary_year,
                    boundary_source,
                    boundary_license,
                    boundary_build_date
                )
                SELECT
                    original.shapeid,
                    %s,
                    original.shapename,
                    original.shapeiso,
                    original.wkb_geometry,
                    simplified.wkb_geometry,
                    %s,
                    %s,
                    %s,
                    %s
                FROM (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            ORDER BY ogc_fid
                        ) AS row_num
                    FROM {staging_table}
                ) original
                JOIN (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            ORDER BY ogc_fid
                        ) AS row_num
                    FROM {simplified_staging_table}
                ) simplified
                    ON original.row_num = simplified.row_num
                ON CONFLICT (source_boundary_id)
                DO UPDATE SET
                    country_code =
                        EXCLUDED.country_code,
                    region =
                        EXCLUDED.region,
                    region_code =
                        EXCLUDED.region_code,
                    geometry =
                        EXCLUDED.geometry,
                    geometry_simplified =
                        EXCLUDED.geometry_simplified,
                    boundary_year =
                        EXCLUDED.boundary_year,
                    boundary_source =
                        EXCLUDED.boundary_source,
                    boundary_license =
                        EXCLUDED.boundary_license,
                    boundary_build_date =
                        EXCLUDED.boundary_build_date,
                    updated_date =
                        CURRENT_TIMESTAMP;
                """,
                [
                    iso,
                    self.parse_year(
                        boundary["boundaryYearRepresented"]
                    ),
                    boundary["boundarySource"],
                    boundary["boundaryLicense"],
                    self.parse_build_date(
                        boundary["buildDate"]
                    ),
                ],
            )

            # -----------------------------------------------------
            # Cleanup simplified staging table
            # -----------------------------------------------------

            cursor.execute(
                f"DROP TABLE IF EXISTS "
                f"{simplified_staging_table};"
            )

    @staticmethod
    def parse_year(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_build_date(value):
        return datetime.strptime(
            value,
            "%b %d, %Y",
        ).date()