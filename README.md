# Earthquake Map

An interactive web map for exploring earthquake events using geographic and seismic information.

## Current Features

The current MVP includes:

- Earthquake data from the USGS Earthquake API.
- PostgreSQL with PostGIS for geographic data.
- Country and first-level administrative region assignment.
- REST API for querying earthquakes within a map viewport.
- Interactive Leaflet map.
- Earthquake markers sized and colored by magnitude.
- Marker clustering for dense areas.
- Basic earthquake information through map popups.

## Technology Stack

- Python
- Django
- Django REST Framework
- GeoDjango
- PostgreSQL / PostGIS
- Leaflet
- Leaflet.markercluster
- Docker / Docker Compose

## Running the Project

Create a '.env' file with the required environment variables and start the application with:

```powershell
docker compose up --build
```

## The application will be available at:

http://localhost:8000/

## Testing

The project includes automated tests covering the main application components.

Run the test suite with:

```powershell
docker compose exec web python manage.py test
```

The current test suite contains 33 tests.

## Project Status

MVP - active development

The core data ingestion, geographic processing, REST API, and interactive map are implemented. Further functionality will be added incrementally.