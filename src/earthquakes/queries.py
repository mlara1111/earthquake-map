from dataclasses import dataclass

from django.contrib.gis.geos import Polygon
from django.db.models import F

from earthquakes.constants import MAX_RESULTS
from earthquakes.models import Earthquake


@dataclass(frozen=True)
class Viewport:
    ### Geographic boundaries of a rectangular map viewport.
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


def get_earthquakes_in_viewport(viewport, max_results=MAX_RESULTS):
    ### Build a rectangular viewport from geographic coordinates.
    ### The frontend will provide these coordinates once the map is implemented.
    bounding_box = Polygon.from_bbox(
        (
            viewport.min_lon,
            viewport.min_lat,
            viewport.max_lon,
            viewport.max_lat,
        )
    )

    ### ST_Intersects is appropriate for point geometries and a map viewport.
    ### It includes points located exactly on the viewport boundary.
    ### GeoDjango handles the geometry parameter adaptation for PostgreSQL/PostGIS.
    return Earthquake.objects.filter(
        geometry__intersects=bounding_box
    ).order_by(
        F("magnitude").desc(nulls_last=True),
        "-event_date",
    )[:max_results]