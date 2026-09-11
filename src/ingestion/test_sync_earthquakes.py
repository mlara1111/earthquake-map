from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from ingestion.management.commands.sync_earthquakes import (
    DEFAULT_LOOKBACK_DAYS,
    Command,
    SyncLock,
)


class SyncEarthquakesPeriodTests(SimpleTestCase):
    ### Verify synchronization period calculation without contacting USGS.

    def setUp(self):
        self.command = Command()

    def test_default_lookback_period(self):
        ### The default period must cover the configured lookback interval.
        before = datetime.now(timezone.utc)

        start, end = self.command.get_sync_period(
            {
                "lookback_days": DEFAULT_LOOKBACK_DAYS,
                "start_date": None,
                "end_date": None,
            }
        )

        after = datetime.now(timezone.utc)

        self.assertGreaterEqual(
            start,
            before - timedelta(days=DEFAULT_LOOKBACK_DAYS),
        )
        self.assertLessEqual(
            start,
            after - timedelta(days=DEFAULT_LOOKBACK_DAYS),
        )
        self.assertGreaterEqual(end, before)
        self.assertLessEqual(end, after)

    def test_explicit_start_and_end_dates(self):
        ### Explicit calendar dates must be converted into UTC datetimes.
        start, end = self.command.get_sync_period(
            {
                "lookback_days": DEFAULT_LOOKBACK_DAYS,
                "start_date": "2026-09-01",
                "end_date": "2026-09-10",
            }
        )

        self.assertEqual(
            start,
            datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(
            end,
            datetime(
                2026,
                9,
                10,
                23,
                59,
                59,
                999999,
                tzinfo=timezone.utc,
            ),
        )

    def test_invalid_lookback_days(self):
        ### Zero or negative lookback periods are invalid.
        with self.assertRaises(CommandError):
            self.command.get_sync_period(
                {
                    "lookback_days": 0,
                    "start_date": None,
                    "end_date": None,
                }
            )

    def test_invalid_date_format(self):
        ### Synchronization dates must use the documented ISO calendar format.
        with self.assertRaises(CommandError):
            self.command.get_sync_period(
                {
                    "lookback_days": DEFAULT_LOOKBACK_DAYS,
                    "start_date": "2026/09/01",
                    "end_date": None,
                }
            )

    def test_start_date_must_precede_end_date(self):
        ### An inverted synchronization window must be rejected.
        with self.assertRaises(CommandError):
            self.command.get_sync_period(
                {
                    "lookback_days": DEFAULT_LOOKBACK_DAYS,
                    "start_date": "2026-09-10",
                    "end_date": "2026-09-01",
                }
            )


class SyncLockTests(SimpleTestCase):
    ### Verify that concurrent synchronization processes cannot share a lock.

    def test_lock_is_exclusive(self):
        ### The second process must be unable to acquire an existing lock.
        lock_path = Path(self._testMethodName + ".lock")

        first_lock = SyncLock(lock_path)
        second_lock = SyncLock(lock_path)

        try:
            first_lock.acquire()

            with self.assertRaises(CommandError):
                second_lock.acquire()

        finally:
            first_lock.release()
            second_lock.release()

        self.assertFalse(lock_path.exists())


class SyncEarthquakesCommandTests(SimpleTestCase):
    ### Verify command orchestration without making real requests to USGS.

    @patch(
        "ingestion.management.commands.sync_earthquakes.EarthquakeImporter"
    )
    @patch(
        "ingestion.management.commands.sync_earthquakes.USGSClient"
    )
    @patch(
        "ingestion.management.commands.sync_earthquakes.IngestUSGSCommand"
    )
    def test_successful_synchronization(
        self,
        mocked_ingest_command,
        mocked_client,
        mocked_importer,
    ):
        ### Simulate the existing ingestion command returning structured statistics.
        mocked_ingest_command.return_value.import_window.return_value = {
            "created": 2,
            "updated": 1,
            "unchanged": 7,
            "skipped": 0,
            "requests": 1,
            "pages": 1,
            "split_windows": 0,
        }

        call_command(
            "sync_earthquakes",
            lookback_days=1,
        )

        mocked_ingest_command.return_value.import_window.assert_called_once()

        mocked_client.assert_called_once()
        mocked_importer.assert_called_once()