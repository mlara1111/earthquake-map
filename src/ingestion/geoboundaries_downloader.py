import json
import time
import zipfile
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://www.geoboundaries.org/api/current/gbOpen/ALL"


class GeoBoundariesDownloader:
    ### Download boundary datasets from geoBoundaries with retry handling
    ### for transient HTTP failures.

    TRANSIENT_STATUS_CODES = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    MAX_RETRIES = 4
    RETRY_BACKOFF_FACTOR = 2
    CONNECT_TIMEOUT = 30
    READ_TIMEOUT = 300

    def __init__(self, output_dir="data/boundaries"):
        self.output_dir = Path(output_dir)
        self.session = self._create_session()

    def _create_session(self):
        ### Create an HTTP session with automatic retries for transient failures.
        ###
        ### The retry policy applies to GET requests only because the downloader
        ### does not perform state-changing HTTP operations.

        retry = Retry(
            total=self.MAX_RETRIES,
            connect=self.MAX_RETRIES,
            read=self.MAX_RETRIES,
            status=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF_FACTOR,
            status_forcelist=sorted(self.TRANSIENT_STATUS_CODES),
            allowed_methods=["GET"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry)

        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _get(self, url, timeout=None):
        ### Execute a GET request using the shared retry-enabled session.
        ###
        ### Retryable HTTP failures are handled by urllib3 according to the
        ### configured retry policy. A final non-success response is raised
        ### normally so the caller can report the affected boundary.

        if timeout is None:
            timeout = (
                self.CONNECT_TIMEOUT,
                self.READ_TIMEOUT,
            )

        response = self.session.get(
            url,
            timeout=timeout,
        )
        response.raise_for_status()

        return response

    def get_metadata(self, adm_level):
        ### Retrieve the current geoBoundaries metadata for an administrative level.
        url = f"{BASE_URL}/{adm_level}/"
        response = self._get(url)

        return response.json()

    def save_metadata(self, adm_level, metadata):
        ### Persist the metadata used to identify available boundary datasets.
        directory = self.output_dir / adm_level
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "metadata.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return path

    def get_boundary(self, adm_level, iso):
        ### Find a boundary dataset by its ISO 3166-1 alpha-3 code.
        boundaries = self.get_metadata(adm_level)

        for boundary in boundaries:
            if boundary["boundaryISO"] == iso:
                return boundary

        raise ValueError(
            f"Boundary not found: {adm_level}/{iso}"
        )

    def download_boundary(self, boundary):
        ### Download and extract one geoBoundaries dataset.
        ###
        ### Existing files are preserved so interrupted imports can be resumed
        ### without downloading data that is already available locally.

        adm_level = boundary["boundaryType"]
        iso = boundary["boundaryISO"]

        directory = self.output_dir / adm_level / iso
        directory.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------
        # Original boundary: ZIP / Shapefile
        # ---------------------------------------------------------

        zip_path = directory / f"{iso}-{adm_level}.zip"

        if not zip_path.exists():
            response = self._get(
                boundary["staticDownloadLink"],
                timeout=(
                    self.CONNECT_TIMEOUT,
                    self.READ_TIMEOUT,
                ),
            )
            zip_path.write_bytes(response.content)

        ### Extract only if the main Shapefile does not already exist.
        expected_shp = (
            directory
            / f"geoBoundaries-{iso}-{adm_level}.shp"
        )

        if not expected_shp.exists():
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(directory)

        # ---------------------------------------------------------
        # Official simplified geometry
        # ---------------------------------------------------------

        simplified_url = boundary.get(
            "simplifiedGeometryGeoJSON"
        )

        if simplified_url:
            simplified_path = (
                directory
                / f"geoBoundaries-{iso}-{adm_level}_simplified.geojson"
            )

            if not simplified_path.exists():
                response = self._get(
                    simplified_url,
                    timeout=(
                        self.CONNECT_TIMEOUT,
                        self.READ_TIMEOUT,
                    ),
                )
                simplified_path.write_bytes(response.content)

        return directory