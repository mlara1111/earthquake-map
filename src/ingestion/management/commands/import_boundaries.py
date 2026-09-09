import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection

from ingestion.geoboundaries_downloader import GeoBoundariesDownloader
from ingestion.text_normalizer import repair_mojibake


class Command(BaseCommand):
    help = "Import administrative boundaries from geoBoundaries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--level",
            choices=["ADM0", "ADM1"],
            default="ADM0",
            help="Administrative boundary level to import.",
        )

        parser.add_argument(
            "--country",
            help="ISO 3166-1 alpha-3 country code to import.",
        )

    def handle(self, *args, **options):
        level = options["level"]
        country = options["country"]

        downloader = GeoBoundariesDownloader()

        ### Download and store the metadata required to identify the
        ### boundary datasets available for the requested administrative level.
        metadata = downloader.get_metadata(level)
        downloader.save_metadata(level, metadata)

        ### Import either the requested country or all available countries.
        boundaries = metadata

        if country:
            boundaries = [
                boundary
                for boundary in metadata
                if boundary["boundaryISO"] == country
            ]

            if not boundaries:
                raise ValueError(
                    f"Boundary not found: {level}/{country}"
                )

        successful_boundaries = []
        failed_boundaries = []

        for boundary in boundaries:
            iso = boundary["boundaryISO"]

            self.stdout.write(
                f"Importing {level} boundary: {iso}"
            )

            try:
                directory = downloader.download_boundary(boundary)

                shp_file = (
                    directory
                    / f"geoBoundaries-{iso}-{level}.shp"
                )

                if not shp_file.exists():
                    raise FileNotFoundError(
                        f"Shapefile not found: {shp_file}"
                    )

                self.import_shapefile(
                    shp_file=shp_file,
                    boundary=boundary,
                    level=level,
                )

                successful_boundaries.append(iso)

            except Exception as exc:
                ### Keep processing the remaining boundaries when one dataset fails.
                ### The failure is recorded so the command can report an incomplete
                ### import and return a non-zero exit status at the end.
                failed_boundaries.append(
                    {
                        "iso": iso,
                        "error": str(exc),
                    }
                )

                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to import {level} boundary {iso}: {exc}"
                    )
                )

        ### Report the final import status after all requested boundaries were processed.
        self.stdout.write("")
        self.stdout.write(
            f"Successfully imported: {len(successful_boundaries)}"
        )
        self.stdout.write(
            f"Failed: {len(failed_boundaries)}"
        )

        if failed_boundaries:
            self.stdout.write("")
            self.stdout.write("Failed boundaries:")

            for failure in failed_boundaries:
                self.stdout.write(
                    f"- {failure['iso']}: {failure['error']}"
                )

            ### Signal an incomplete import to the operating system and CI/CD.
            raise RuntimeError(
                f"{len(failed_boundaries)} boundary import(s) failed."
            )

    def get_postgres_connection_string(self):
        ### Build the PostgreSQL connection string used by ogr2ogr.
        ### PostgreSQL connection parameters are provided through environment variables
        ### so the ingestion process uses the same configuration as the Django service.
        return (
            f"PG:host={os.environ['POSTGRES_HOST']} "
            f"port={os.environ['POSTGRES_PORT']} "
            f"dbname={os.environ['POSTGRES_DB']} "
            f"user={os.environ['POSTGRES_USER']}"
        )

    def normalize_staging_shapename(self, staging_table):
        ### Repair UTF-8 mojibake in human-readable boundary names before
        ### copying them from the staging table into the final tables.
        ### Boundary identifiers such as shapeISO and shapeID are not modified.
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT ogc_fid, shapename
                FROM {staging_table};
                """
            )

            rows = cursor.fetchall()

            for ogc_fid, shapename in rows:
                normalized = repair_mojibake(shapename)

                if normalized != shapename:
                    cursor.execute(
                        f"""
                        UPDATE {staging_table}
                        SET shapename = %s
                        WHERE ogc_fid = %s;
                        """,
                        [normalized, ogc_fid],
                    )

    def import_shapefile(self, shp_file, boundary, level):
        if level == "ADM0":
            staging_table = "staging_boundary_country"
            target_table = "tbl_boundary_country"
        else:
            staging_table = "staging_boundary_region"
            target_table = "tbl_boundary_region"

        ### Remove the previous staging table before importing the new
        ### shapefile. The staging table is temporary and recreated by ogr2ogr.
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {staging_table};")

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

        ### Normalize human-readable names immediately after ogr2ogr imports
        ### the source data. This fixes source-level mojibake before any
        ### earthquake records receive country or region names.
        self.normalize_staging_shapename(staging_table)

        if level == "ADM0":
            self.import_adm0(boundary, staging_table)
        else:
            self.import_adm1(boundary, staging_table)

    def import_adm0(self, boundary, staging_table):
        ### Insert the normalized country boundary into the definitive table.
        ### The country ISO code is taken from geoBoundaries metadata because
        ### it is the authoritative identifier for the imported country.
        boundary_year = self.extract_boundary_year(boundary)
        boundary_source = "geoBoundaries"
        boundary_license = boundary.get("licenseDetail")
        boundary_build_date = boundary.get("buildDate")

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
                    boundary_build_date = EXCLUDED.boundary_build_date;
                """,
                [
                    boundary["boundaryISO"],
                    boundary_year,
                    boundary_source,
                    boundary_license,
                    boundary_build_date,
                ],
            )

    def import_adm1(self, boundary, staging_table):
        ### Import the simplified geometry used for spatial operations and
        ### preserve the original geometry as the detailed boundary geometry.
        simplified_table = "staging_boundary_region_simplified"

        with connection.cursor() as cursor:
            cursor.execute(
                f"DROP TABLE IF EXISTS {simplified_table};"
            )

        simplified_file = (
            Path("data/boundaries")
            / "ADM1"
            / boundary["boundaryISO"]
            / (
                f"geoBoundaries-{boundary['boundaryISO']}"
                "-ADM1_simplified.geojson"
            )
        )

        if not simplified_file.exists():
            raise FileNotFoundError(
                f"Simplified boundary file not found: {simplified_file}"
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
                simplified_table,
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

        boundary_year = self.extract_boundary_year(boundary)
        boundary_source = "geoBoundaries"
        boundary_license = boundary.get("licenseDetail")
        boundary_build_date = boundary.get("buildDate")

        with connection.cursor() as cursor:
            ### The simplified and original datasets contain the same feature
            ### order. ROW_NUMBER provides a deterministic positional join.
            cursor.execute(
                f"""
                WITH original AS (
                    SELECT
                        shapeid,
                        shapename,
                        shapeiso,
                        wkb_geometry,
                        ROW_NUMBER() OVER (ORDER BY ogc_fid) AS row_number
                    FROM {staging_table}
                ),
                simplified AS (
                    SELECT
                        wkb_geometry,
                        ROW_NUMBER() OVER (ORDER BY ogc_fid) AS row_number
                    FROM {simplified_table}
                )
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
                FROM original
                JOIN simplified
                    ON original.row_number = simplified.row_number
                ON CONFLICT (source_boundary_id)
                DO UPDATE SET
                    country_code = EXCLUDED.country_code,
                    region = EXCLUDED.region,
                    region_code = EXCLUDED.region_code,
                    geometry = EXCLUDED.geometry,
                    geometry_simplified = EXCLUDED.geometry_simplified,
                    boundary_year = EXCLUDED.boundary_year,
                    boundary_source = EXCLUDED.boundary_source,
                    boundary_license = EXCLUDED.boundary_license,
                    boundary_build_date = EXCLUDED.boundary_build_date;
                """,
                [
                    boundary["boundaryISO"],
                    boundary_year,
                    boundary_source,
                    boundary_license,
                    boundary_build_date,
                ],
            )

            ### The simplified staging table is no longer needed after import.
            cursor.execute(
                f"DROP TABLE IF EXISTS {simplified_table};"
            )

    def extract_boundary_year(self, boundary):
        ### Extract the numeric boundary year from geoBoundaries metadata.
        ### Return None when the metadata does not provide a usable year.
        boundary_year = boundary.get("boundaryYear")

        if not boundary_year:
            return None

        try:
            return int(boundary_year)
        except (TypeError, ValueError):
            return None