from datetime import datetime, timedelta, timezone

import requests
from django.core.management.base import BaseCommand

from ingestion.earthquake_importer import EarthquakeImporter
from ingestion.earthquake_transformer import EarthquakeTransformer
from ingestion.usgs_client import USGSClient

class Command(BaseCommand):
    help = "Import earthquake events from USGS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            default="2026-01-01",
            help="Start date in ISO 8601 format.",
        )
        parser.add_argument(
            "--end",
            help="End date in ISO 8601 format. Defaults to now.",
        )
        parser.add_argument(
            "--minmagnitude",
            type=float,
            default=2.5,
            help="Minimum earthquake magnitude.",
        )

    def handle(self, *args, **options):
        start = datetime.fromisoformat(options["start"]).replace(tzinfo=timezone.utc)
        end = (
            datetime.fromisoformat(options["end"]).replace(tzinfo=timezone.utc)
            if options["end"]
            else datetime.now(timezone.utc)
        )

        ### Create the API client and database importer once for the ingestion run.
        client = USGSClient()
        importer = EarthquakeImporter()

        self.import_window(
            client,
            importer,
            start,
            end,
            options["minmagnitude"],
        )

    def import_window(
        self,
        client,
        importer,
        start,
        end,
        minmagnitude,
    ):
        ### USGS returns HTTP 400 when the requested window exceeds its result limit.
        ### Split the time window recursively until each query can be processed.
        try:
            data = client.get_events(
                starttime=start.isoformat(),
                endtime=end.isoformat(),
                minmagnitude=minmagnitude,
            )

        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 400:
                self.stdout.write(
                    f"Window exceeds USGS limit: {start} → {end}. Splitting."
                )

                midpoint = start + (end - start) / 2

                self.import_window(
                    client,
                    importer,
                    start,
                    midpoint,
                    minmagnitude,
                )

                self.import_window(
                    client,
                    importer,
                    midpoint,
                    end,
                    minmagnitude,
                )

                return

            raise

        features = data.get("features", [])

        self.stdout.write(
            f"Importing {len(features)} events: {start} → {end}"
        )

        created = 0
        updated = 0
        unchanged = 0
        skipped = 0

        ### Transform and import each USGS event individually.
        for feature in features:
            event = EarthquakeTransformer.transform(feature)
            result = importer.import_event(event)

            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            elif result == "unchanged":
                unchanged += 1
            elif result == "skipped":
                skipped += 1

        self.stdout.write(
            f"Created: {created} | "
            f"Updated: {updated} | "
            f"Unchanged: {unchanged} | "
            f"Skipped: {skipped}"
        )

        ### If USGS returned the maximum page size, request the next page.
        if len(features) == client.MAX_RESULTS:
            ### Include results from all subsequent USGS pages in the final totals.
            offset_results = self.import_offset(
                client,
                importer,
                start,
                end,
                minmagnitude,
                20001,
            )

            created += offset_results["created"]
            updated += offset_results["updated"]
            unchanged += offset_results["unchanged"]
            skipped += offset_results["skipped"]

    def import_offset(
        self,
        client,
        importer,
        start,
        end,
        minmagnitude,
        offset,
    ):
        ### Continue pagination using the USGS offset parameter.
        data = client.get_events(
            starttime=start.isoformat(),
            endtime=end.isoformat(),
            minmagnitude=minmagnitude,
            offset=offset,
        )

        features = data.get("features", [])

        if not features:
            return {
                "created": 0,
                "updated": 0,
                "unchanged": 0,
                "skipped": 0,
            }

        self.stdout.write(
            f"Importing {len(features)} events from offset {offset}."
        )

        created = 0
        updated = 0
        unchanged = 0
        skipped = 0

        ### Process events from subsequent pages using the same transformation
        ### and import rules as the first page.
        for feature in features:
            event = EarthquakeTransformer.transform(feature)
            result = importer.import_event(event)

            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            elif result == "unchanged":
                unchanged += 1
            elif result == "skipped":
                skipped += 1

        ### USGS returned another full page, so continue with the next offset.
        if len(features) == client.MAX_RESULTS:
            next_page = self.import_offset(
                client,
                importer,
                start,
                end,
                minmagnitude,
                offset + client.MAX_RESULTS,
            )

            created += next_page["created"]
            updated += next_page["updated"]
            unchanged += next_page["unchanged"]
            skipped += next_page["skipped"]

        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "skipped": skipped,
        }
