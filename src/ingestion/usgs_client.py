import requests

class USGSClient:
    ### USGS FDSN Event Web Service endpoint.
    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    ### USGS limits a single query response to 20,000 events.
    ### The ingestion command handles larger result sets through pagination.
    MAX_RESULTS = 20000

    def get_events(
        self,
        starttime,
        endtime,
        minmagnitude=2.5,
        limit=20000,
        offset=1,
    ):
        ### Request earthquake events from USGS in GeoJSON format.
        ### Results are ordered chronologically so pagination remains deterministic.
        params = {
            "format": "geojson",
            "starttime": starttime,
            "endtime": endtime,
            "minmagnitude": minmagnitude,
            "limit": limit,
            "offset": offset,
            "orderby": "time-asc",
        }

        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=60,
        )

        response.raise_for_status()

        return response.json()
