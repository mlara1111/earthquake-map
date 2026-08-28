from django.db import models

###
from django.contrib.gis.db.models import PointField

# Create your models here.

### Table: tbl_source.
class Source(models.Model):
    ### Unique identifier assigned by us to each data source.
    code = models.CharField(max_length=20, unique=True)

    ### Full name of the data source.
    name = models.CharField(max_length=150)

    ### Reference website for the data source.
    url = models.URLField(max_length=500)

    ### Date and time when the source was added to our system.
    created_date = models.DateTimeField(auto_now_add=True)

    ### Date and time when the source record was last updated.
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_source"
        ordering = ["id"]

    def __str__(self):
        return self.code


### Table: tbl_earthquake.
class Earthquake(models.Model):
    ### Data source that provided the earthquake event.
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="earthquakes",
    )

    ### Unique event identifier assigned by the source.
    source_event_id = models.CharField(max_length=50)

    ### Event date and time in UTC.
    event_date = models.DateTimeField()

    ### Date and time when the source last updated the event.
    usgs_updated_date = models.DateTimeField()

    ### Earthquake magnitude.
    magnitude = models.DecimalField(max_digits=4, decimal_places=2)

    ### Magnitude scale used by the source, e.g. ml, mb, mw.
    magnitude_type = models.CharField(max_length=20, null=True, blank=True)

    ### Event classification, e.g. earthquake or explosion.
    event_type = models.CharField(max_length=50)

    ### Review status assigned by the source.
    status = models.CharField(max_length=20)

    ### Depth of the event in kilometers.
    depth_km = models.DecimalField(max_digits=8, decimal_places=3)

    ### Latitude in decimal degrees.
    latitude = models.DecimalField(max_digits=9, decimal_places=6)

    ### Longitude in decimal degrees.
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    ### Geographic point used by PostGIS for spatial operations.
    geometry = PointField(srid=4326)

    ### Human-readable location provided by the source.
    place = models.CharField(max_length=255, null=True, blank=True)

    ### Country calculated during data ingestion.
    country = models.CharField(max_length=100, null=True, blank=True)

    ### ISO country code calculated during data ingestion.
    country_code = models.CharField(max_length=10, null=True, blank=True)

    ### First-level administrative region calculated during data ingestion.
    region = models.CharField(max_length=150, null=True, blank=True)

    ### ISO or source-provided code of the first-level administrative region.
    ### The value may be NULL because geoBoundaries does not provide a region code
    ### consistently for all ADM1 datasets.
    region_code = models.CharField(max_length=20, null=True, blank=True)

    ### URL of the earthquake event at the source.
    usgs_url = models.URLField(max_length=500, null=True, blank=True)

    ### Indicates whether the event triggered a tsunami flag.
    tsunami = models.BooleanField(default=False)

    ### Number of user reports associated with the event.
    felt_reports = models.IntegerField(null=True, blank=True)

    ### Community Determined Intensity.
    cdi = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    ### Modified Mercalli Intensity.
    mmi = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    ### USGS significance score.
    significance = models.IntegerField(null=True, blank=True)

    ### Date and time when the event entered our database.
    created_date = models.DateTimeField(auto_now_add=True)

    ### Date and time when our record was last updated.
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_earthquake"
        ordering = ["-event_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_event_id"],
                name="uq_earthquake_source_event",
            ),
        ]
        indexes = [
            models.Index(fields=["event_date"]),
            models.Index(fields=["magnitude"]),
            models.Index(fields=["status"]),
            models.Index(fields=["source", "source_event_id"]),
        ]

    def __str__(self):
        return f"{self.source_event_id} - M{self.magnitude}"