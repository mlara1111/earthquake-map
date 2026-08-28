import json
import zipfile
from pathlib import Path

import requests

BASE_URL = "https://www.geoboundaries.org/api/current/gbOpen/ALL"

class GeoBoundariesDownloader:
    def __init__(self, output_dir="data/boundaries"):
        self.output_dir = Path(output_dir)

    def get_metadata(self, adm_level):
        url = f"{BASE_URL}/{adm_level}/"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.json()

    def save_metadata(self, adm_level, metadata):
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
        boundaries = self.get_metadata(adm_level)

        for boundary in boundaries:
            if boundary["boundaryISO"] == iso:
                return boundary

        raise ValueError(
            f"Boundary not found: {adm_level}/{iso}"
        )

    def download_boundary(self, boundary):
        adm_level = boundary["boundaryType"]
        iso = boundary["boundaryISO"]

        directory = self.output_dir / adm_level / iso
        directory.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------
        # Original boundary: ZIP / Shapefile
        # ---------------------------------------------------------

        zip_path = directory / f"{iso}-{adm_level}.zip"

        if not zip_path.exists():
            response = requests.get(
                boundary["staticDownloadLink"],
                timeout=300,
            )
            response.raise_for_status()

            zip_path.write_bytes(response.content)

        # Extract only if the main Shapefile does not already exist.
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
                response = requests.get(
                    simplified_url,
                    timeout=300,
                )
                response.raise_for_status()

                simplified_path.write_bytes(response.content)

        return directory