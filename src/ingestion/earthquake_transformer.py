from datetime import datetime, timezone
from django.contrib.gis.geos import Point

class EarthquakeTransformer:
    @staticmethod
    def transform(feature):
        ### Extract the fields used by the MVP from the USGS GeoJSON feature.
        properties = feature["properties"]
        coordinates = feature["geometry"]["coordinates"]

        ### USGS GeoJSON coordinates are ordered as longitude, latitude, depth.
        longitude = coordinates[0]
        latitude = coordinates[1]
        depth_km = coordinates[2]

        ### Some optional USGS properties may legitimately be null.
        ### The Earthquake model therefore allows NULL for the corresponding fields.
        return {
            "source_event_id": feature["id"],
            "event_date": datetime.fromtimestamp(
                properties["time"] / 1000,
                tz=timezone.utc,
            ),
            "usgs_updated_date": datetime.fromtimestamp(
                properties["updated"] / 1000,
                tz=timezone.utc,
            ),
            "magnitude": properties["mag"],
            "magnitude_type": properties["magType"],
            "event_type": properties["type"],
            "status": properties["status"],
            "depth_km": depth_km,
            "latitude": latitude,
            "longitude": longitude,
            "geometry": Point(longitude, latitude, srid=4326),
            "place": properties["place"],
            "usgs_url": properties["url"],
            "tsunami": bool(properties["tsunami"]),
            "felt_reports": properties["felt"],
            "cdi": properties["cdi"],
            "mmi": properties["mmi"],
            "significance": properties["sig"],
        }
