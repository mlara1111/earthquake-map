from dateutil.relativedelta import relativedelta
from earthquakes.models import Earthquake, Source
from ingestion.spatial_assigner import SpatialAssigner

class EarthquakeImporter:
    def __init__(self, source_code="USGS"):
        ### Use the source record created by the database seed migration.
        self.source = Source.objects.get(code=source_code)

        ### Spatial assignment is performed after creating or updating an event.
        self.spatial_assigner = SpatialAssigner()

    def import_event(self, data):
        ### Events marked as deleted by USGS are not stored or updated.
        if data["status"] == "deleted":
            return "skipped"

        try:
            earthquake = Earthquake.objects.get(
                source=self.source,
                source_event_id=data["source_event_id"],
            )
        except Earthquake.DoesNotExist:
            ### New events are inserted using the source/event ID pair as identity.
            data["source"] = self.source
            earthquake = Earthquake.objects.create(**data)

            ### Assign administrative boundaries using the event geometry.
            self.spatial_assigner.assign_earthquake(earthquake.id)

            return "created"

        ### MVP policy: an event can only be updated during the first three months
        ### after its event date. This window can be changed in a future version.
        update_deadline = earthquake.event_date + relativedelta(months=3)

        if data["usgs_updated_date"] > update_deadline:
            return "unchanged"

        ### Ignore source data that is not newer than the version already stored.
        if data["usgs_updated_date"] <= earthquake.usgs_updated_date:
            return "unchanged"

        ### Only these fields are considered relevant for updates in the MVP.
        ### Additional USGS fields are stored in the model but are intentionally
        ### excluded from update comparison until a future MVP iteration.
        relevant_fields = [
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
        ]

        changed = any(
            getattr(earthquake, field) != data[field]
            for field in relevant_fields
        )

        if not changed:
            return "unchanged"

        ### Update only the fields explicitly defined as relevant to the MVP.
        for field in relevant_fields:
            setattr(earthquake, field, data[field])

        ### Keep the source update timestamp even when the event data changes.
        earthquake.usgs_updated_date = data["usgs_updated_date"]
        earthquake.save()

        ### Recalculate administrative boundaries after the event is updated.
        ### This is required because geometry is one of the relevant MVP fields.
        self.spatial_assigner.assign_earthquake(earthquake.id)

        return "updated"
