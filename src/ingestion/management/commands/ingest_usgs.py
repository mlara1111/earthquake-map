
from datetime import datetime, timezone
import logging

import requests
from django.core.management.base import BaseCommand

from ingestion.earthquake_importer import EarthquakeImporter
from ingestion.earthquake_transformer import EarthquakeTransformer
from ingestion.usgs_client import USGSClient


### Number of events processed between progress messages.
### This keeps long-running synchronizations observable without flooding the log.
PROGRESS_INTERVAL = 500


### Use the shared synchronization logger for ingestion and synchronization logs.
LOGGER = logging.getLogger("earthquake.sync")


def empty_stats():
    ### Create a zeroed statistics dictionary for one ingestion operation.
    return {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "requests": 0,
        "pages": 0,
        "split_windows": 0,
    }


def add_stats(target, source):
    ### Accumulate structured ingestion statistics into a single result.
    for key in target:
        target[key] += source[key]


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
        start = datetime.fromisoformat(
            options["start"],
        ).replace(tzinfo=timezone.utc)

        end = (
            datetime.fromisoformat(
                options["end"],
            ).replace(tzinfo=timezone.utc)
            if options["end"]
            else datetime.now(timezone.utc)
        )

        ### Create the API client and database importer once for the ingestion run.
        client = USGSClient()

        ### Send detailed update reports directly to the console and logger.
        importer = EarthquakeImporter(
            update_reporter=self._report,
        )

        ### Execute the ingestion without returning statistics to Django.
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
        ### Track the complete result of this window, including split windows.
        stats = empty_stats()

        ### USGS returns HTTP 400 when the requested window exceeds its limit.
        ### Split the time window recursively until each query can be processed.
        try:
            data = client.get_events(
                starttime=start.isoformat(),
                endtime=end.isoformat(),
                minmagnitude=minmagnitude,
            )
            stats["requests"] += 1

        except requests.HTTPError as error:
            if (
                error.response is not None
                and error.response.status_code == 400
            ):
                self._report(
                    f"Window exceeds USGS limit: {start} → {end}. "
                    "Splitting."
                )

                midpoint = start + (end - start) / 2
                stats["split_windows"] += 1

                add_stats(
                    stats,
                    self.import_window(
                        client,
                        importer,
                        start,
                        midpoint,
                        minmagnitude,
                    ),
                )

                add_stats(
                    stats,
                    self.import_window(
                        client,
                        importer,
                        midpoint,
                        end,
                        minmagnitude,
                    ),
                )

                return stats

            ### Propagate unexpected HTTP errors to the caller.
            raise

        stats["pages"] += 1
        features = data.get("features", [])

        self._report(
            f"Importing {len(features)} events: {start} → {end}",
        )

        page_stats = self.import_features(importer, features)
        add_stats(stats, page_stats)

        self._report(
            f"Created: {page_stats['created']} | "
            f"Updated: {page_stats['updated']} | "
            f"Unchanged: {page_stats['unchanged']} | "
            f"Skipped: {page_stats['skipped']}",
        )

        ### If USGS returned the maximum page size, request the next page.
        if len(features) == client.MAX_RESULTS:
            ### Include subsequent USGS pages in the final totals.
            offset_results = self.import_offset(
                client,
                importer,
                start,
                end,
                minmagnitude,
                client.MAX_RESULTS + 1,
            )
            add_stats(stats, offset_results)

        return stats

    def import_features(self, importer, features):
        ### Transform and import each USGS event individually.
        ### Progress is reported periodically to keep long-running
        ### synchronizations observable.
        stats = empty_stats()
        total_events = len(features)

        for index, feature in enumerate(features, start=1):
            event = EarthquakeTransformer.transform(feature)
            result = importer.import_event(event)

            if result == "created":
                stats["created"] += 1
            elif result == "updated":
                stats["updated"] += 1
            elif result == "unchanged":
                stats["unchanged"] += 1
            elif result == "skipped":
                stats["skipped"] += 1

            ### Report progress every 500 events and at the end of each page.
            if index % PROGRESS_INTERVAL == 0 or index == total_events:
                self._report(
                    f"Import progress: {index} / {total_events}",
                    flush=True,
                )

        return stats

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
        stats = empty_stats()

        data = client.get_events(
            starttime=start.isoformat(),
            endtime=end.isoformat(),
            minmagnitude=minmagnitude,
            offset=offset,
        )

        stats["requests"] += 1
        stats["pages"] += 1

        features = data.get("features", [])

        if not features:
            return stats

        self._report(
            f"Importing {len(features)} events from offset {offset}.",
        )

        page_stats = self.import_features(importer, features)
        add_stats(stats, page_stats)

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
            add_stats(stats, next_page)

        return stats


    def _report(self, message, flush=False):
        ### Write operational messages to both the console and logger.
        self.stdout.write(message)

        if flush:
            self.stdout.flush()

        LOGGER.info(message)