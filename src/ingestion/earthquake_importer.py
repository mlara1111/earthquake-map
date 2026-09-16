
import logging

from dateutil.relativedelta import relativedelta

from earthquakes.models import Earthquake, Source
from ingestion.spatial_assigner import SpatialAssigner


LOGGER = logging.getLogger("earthquake.sync")


class EarthquakeImporter:
    ### Fields considered relevant for earthquake updates.
    RELEVANT_FIELDS = (
        "event_date",
        "magnitude",
        "magnitude_type",
        "depth_km",
        "latitude",
        "longitude",
        "geometry",
        "event_type",
        "status",
        "tsunami",
    )

    def __init__(self, source_code="USGS", update_reporter=None):
        ### Retrieve the source record created by the database seed migration.
        self.source = Source.objects.get(code=source_code)

        ### Assign administrative boundaries after creating or updating an event.
        self.spatial_assigner = SpatialAssigner()

        ### Use an optional callback for direct console reporting.
        self.update_reporter = update_reporter

    def import_event(self, data):
        ### Do not store or update events marked as deleted by USGS.
        if data["status"] == "deleted":
            LOGGER.info(
                "Skipped deleted earthquake: %s",
                data["source_event_id"],
            )
            return "skipped"

        try:
            earthquake = Earthquake.objects.get(
                source=self.source,
                source_event_id=data["source_event_id"],
            )
        except Earthquake.DoesNotExist:
            ### Create and spatially assign a new earthquake.
            earthquake = self._create_earthquake(data)

            LOGGER.info(
                "Created earthquake: %s",
                earthquake.source_event_id,
            )

            return "created"
        except Earthquake.MultipleObjectsReturned:
            ### Log data integrity issues without selecting a record arbitrarily.
            LOGGER.exception(
                "Multiple earthquakes found for source=%s, "
                "source_event_id=%s",
                self.source.code,
                data["source_event_id"],
            )
            raise

        ### An event can only be updated during the first three months
        ### after its event date, and only when the source version is newer.
        update_deadline = earthquake.event_date + relativedelta(months=3)

        if (
            data["usgs_updated_date"] > update_deadline
            or data["usgs_updated_date"] <= earthquake.usgs_updated_date
        ):
            return "unchanged"

        changes = self._get_changes(earthquake, data)

        ### Do not update or report events without relevant field changes.
        if not changes:
            return "unchanged"

        self._update_earthquake(earthquake, data)

        ### Recalculate administrative boundaries after the event is updated.
        self.spatial_assigner.assign_earthquake(earthquake.id)

        ### Report the changed fields after the update is completed.
        self._report_update(
            source_event_id=earthquake.source_event_id,
            changes=changes,
        )

        return "updated"

    def _create_earthquake(self, data):
        ### Add the source without modifying the original input dictionary.
        earthquake_data = {
            **data,
            "source": self.source,
        }

        earthquake = Earthquake.objects.create(**earthquake_data)

        ### Assign administrative boundaries using the event geometry.
        self.spatial_assigner.assign_earthquake(earthquake.id)

        return earthquake

    def _get_changes(self, earthquake, data):
        ### Collect old and new values for every relevant changed field.
        changes = {}

        for field in self.RELEVANT_FIELDS:
            old_value = getattr(earthquake, field)
            new_value = data[field]

            if old_value != new_value:
                changes[field] = (old_value, new_value)

        return changes

    def _update_earthquake(self, earthquake, data):
        ### Update the relevant fields with the latest source values.
        for field in self.RELEVANT_FIELDS:
            setattr(earthquake, field, data[field])

        ### Store the timestamp of the latest accepted source version.
        earthquake.usgs_updated_date = data["usgs_updated_date"]

        ### Persist only the fields modified by this importer.
        earthquake.save(
            update_fields=[
                *self.RELEVANT_FIELDS,
                "usgs_updated_date",
            ]
        )

    def _report_update(self, source_event_id, changes):
        ### Build a readable report for console and file logging.
        lines = [
            f"Updated earthquake: {source_event_id}",
            "Changed fields:",
        ]

        for field, (old_value, new_value) in changes.items():
            lines.append(
                f"  {field}: "
                f"{self._format_value(old_value)} -> "
                f"{self._format_value(new_value)}"
            )

        message = "\n".join(lines)

        ### Send the report to the configured callback when available.
        if self.update_reporter is not None:
            self.update_reporter(message)
            return

        ### The sync command uses the configured earthquake.sync logger.
        LOGGER.info(message)

    @staticmethod
    def _format_value(value):
        ### Display geometry using Well-Known Text (WKT) when supported.
        if hasattr(value, "wkt"):
            return value.wkt

        ### Represent null values explicitly in the report.
        if value is None:
            return "None"

        return str(value)