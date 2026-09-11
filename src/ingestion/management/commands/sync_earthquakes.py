import logging
import os
import socket
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from ingestion.earthquake_importer import EarthquakeImporter
from ingestion.management.commands.ingest_usgs import Command as IngestUSGSCommand
from ingestion.usgs_client import USGSClient


### Default synchronization period.
### The importer allows updates during the first three months after an event date,
### so the default synchronization window covers that complete operational period.
DEFAULT_LOOKBACK_DAYS = 90

### Minimum magnitude used by the application.
### This keeps the synchronization dataset aligned with the public API population.
MIN_MAGNITUDE = 2.5

### Log file configuration.
LOG_DIRECTORY = Path(settings.BASE_DIR).parent / "logs"
LOG_FILE = LOG_DIRECTORY / "earthquake-sync.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5

### Lock file used to prevent overlapping synchronization processes.
LOCK_FILE = LOG_DIRECTORY / "earthquake-sync.lock"

LOGGER_NAME = "earthquake.sync"


def configure_logger():
    ### Configure both persistent file logging and console logging.
    ### A rotating file prevents an unattended scheduler from growing the log forever.
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    ### Avoid duplicate handlers if Django invokes the command more than once
    ### in the same Python process, for example from an automated test.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class SyncLock:
    ### Manage an exclusive lock file for the duration of one synchronization run.
    ### The file is created atomically so two processes cannot acquire it simultaneously.

    def __init__(self, path):
        self.path = Path(path)
        self.acquired = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            file_descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as error:
            raise CommandError(
                f"Another earthquake synchronization is already running. "
                f"Lock file: {self.path}"
            ) from error

        with os.fdopen(file_descriptor, "w", encoding="utf-8") as lock_handle:
            lock_handle.write(f"pid={os.getpid()}\n")
            lock_handle.write(f"host={socket.gethostname()}\n")
            lock_handle.write(
                f"started={datetime.now(timezone.utc).isoformat()}\n"
            )

        self.acquired = True

    def release(self):
        ### Remove the lock only when this process successfully acquired it.
        if not self.acquired:
            return

        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

        self.acquired = False


class Command(BaseCommand):
    help = "Synchronize recent earthquake events from USGS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=DEFAULT_LOOKBACK_DAYS,
            help=(
                "Number of days to synchronize backwards from the current time. "
                "Default: 90."
            ),
        )

        parser.add_argument(
            "--start-date",
            help=(
                "Explicit synchronization start date in YYYY-MM-DD format. "
                "Overrides --lookback-days."
            ),
        )

        parser.add_argument(
            "--end-date",
            help=(
                "Explicit synchronization end date in YYYY-MM-DD format. "
                "Defaults to the current time."
            ),
        )

    def handle(self, *args, **options):
        logger = configure_logger()
        lock = SyncLock(LOCK_FILE)
        started_at = time.monotonic()

        ### Validate the requested synchronization period inside the logging scope.
        ### Invalid scheduler arguments must be recorded in the persistent log.
        try:
            start, end = self.get_sync_period(options)
        except CommandError as error:
            logger.error("Invalid synchronization parameters: %s", error)
            raise

        logger.info("Starting earthquake synchronization.")
        logger.info(
            "Synchronization period: %s -> %s",
            start.isoformat(),
            end.isoformat(),
        )
        logger.info("Minimum magnitude: %.1f", MIN_MAGNITUDE)

        try:
            lock.acquire()
            logger.info("Synchronization lock acquired.")

            ### Reuse the existing USGS ingestion command instead of duplicating
            ### its pagination, window splitting, transformation, or import logic.
            ingestion_command = IngestUSGSCommand()
            client = USGSClient()
            importer = EarthquakeImporter()

            stats = ingestion_command.import_window(
                client,
                importer,
                start,
                end,
                MIN_MAGNITUDE,
            )

            duration = time.monotonic() - started_at

            logger.info("Synchronization completed successfully.")
            logger.info(
                "Statistics: created=%d updated=%d unchanged=%d skipped=%d "
                "requests=%d pages=%d split_windows=%d duration=%.2fs",
                stats["created"],
                stats["updated"],
                stats["unchanged"],
                stats["skipped"],
                stats["requests"],
                stats["pages"],
                stats["split_windows"],
                duration,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "Earthquake synchronization completed successfully."
                )
            )

            self.stdout.write(
                "Created: {created} | Updated: {updated} | "
                "Unchanged: {unchanged} | Skipped: {skipped} | "
                "Requests: {requests} | Pages: {pages} | "
                "Split windows: {split_windows}".format(**stats)
            )

            ### Django management commands should not return the statistics dictionary.
            ### The statistics have already been written to stdout and the persistent log.
            return None

        except CommandError as error:
            logger.error("Earthquake synchronization could not start: %s", error)
            raise

        except Exception:
            duration = time.monotonic() - started_at

            logger.exception(
                "Earthquake synchronization failed after %.2f seconds.",
                duration,
            )

            self.stderr.write(
                self.style.ERROR(
                    "Earthquake synchronization failed. "
                    f"See {LOG_FILE} for details."
                )
            )

            raise

        finally:
            if lock.acquired:
                lock.release()
                logger.info("Synchronization lock released.")

    def get_sync_period(self, options):
        ### Validate the synchronization date arguments before contacting USGS.
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        lookback_days = options["lookback_days"]

        if lookback_days < 1:
            raise CommandError("--lookback-days must be at least 1.")

        if start_date:
            start = self.parse_date(start_date, "--start-date")
        else:
            start = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        if end_date:
            end = self.parse_date(end_date, "--end-date")

            ### Explicit end dates represent the end of the requested calendar day.
            end = end.replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )
        else:
            end = datetime.now(timezone.utc)

        if start >= end:
            raise CommandError(
                "Synchronization start date must be earlier than the end date."
            )

        return start, end

    @staticmethod
    def parse_date(value, argument_name):
        ### Convert a calendar date into a timezone-aware UTC datetime.
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise CommandError(
                f"{argument_name} must use YYYY-MM-DD format."
            ) from error

        return parsed.replace(tzinfo=timezone.utc)