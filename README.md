# Earthquake Map

An interactive web application for exploring earthquake events using geographic and seismic information.

## Project Status

**Pilot project — first project cycle nearing completion**

The first project cycle is now substantially complete. The application provides an end-to-end pipeline for retrieving earthquake data from the USGS, storing and processing it with PostgreSQL/PostGIS, exposing it through a REST API, and visualizing it through an interactive web map.

The current focus is on final validation, documentation, repository cleanup, and closing the first pilot project cycle.

## Current Capabilities

- Earthquake data ingestion from the USGS Earthquake API.
- Incremental synchronization of recently updated earthquake events.
- PostgreSQL with PostGIS for spatial data storage and querying.
- Geographic assignment of earthquakes to countries and first-level administrative regions.
- geoBoundaries ADM0 and ADM1 boundary data support.
- REST API for retrieving earthquakes within a map viewport.
- API-side minimum magnitude filtering and result limiting.
- Interactive Leaflet map.
- Earthquake markers sized and colored according to magnitude.
- Marker clustering for dense areas.
- Interactive earthquake list synchronized with the map.
- Magnitude-based sorting of earthquake results.
- Viewport-based loading of earthquake data.
- Continent navigation controls.
- Magnitude legend and earthquake information display.
- Persistent synchronization logs with log rotation.
- Atomic synchronization locking to prevent overlapping ingestion runs.
- Windows Task Scheduler integration for daily synchronization.
- Linux scheduling support through the provided synchronization script.

## Data and Processing

Earthquake events are retrieved from the USGS Earthquake Hazards Program FDSN Event Web Service.

The ingestion pipeline:

1. Requests earthquake events from USGS.
2. Splits large time windows when the USGS response limit is exceeded.
3. Handles USGS pagination for large result sets.
4. Transforms USGS GeoJSON features into the application's internal representation.
5. Creates new earthquake records or updates recently updated existing records.
6. Assigns countries and first-level administrative regions using PostGIS spatial operations.
7. Stores the resulting data in PostgreSQL/PostGIS.

The application currently uses a minimum magnitude of **2.5** for the populated earthquake dataset.

The USGS API retains the original magnitude precision in the database. The application formats magnitudes to one decimal place for presentation.

## Technology Stack

- Python 3.14
- Django 6.1
- Django REST Framework
- GeoDjango
- PostgreSQL
- PostGIS
- Leaflet
- Leaflet.markercluster
- Docker
- Docker Compose
- PowerShell
- Windows Task Scheduler

## Project Structure

The main application code is located under `src/`.

Key areas include:

- `src/earthquakes/` — earthquake domain model, API, queries, serializers, views, and shared constants.
- `src/ingestion/` — USGS ingestion, transformation, boundary processing, and management commands.
- `src/map/` — interactive map views, templates, CSS, and JavaScript.
- `scripts/` — synchronization wrappers for scheduled or manual execution.
- `compose.yaml` — Docker Compose application and database configuration.

Boundary datasets are intentionally kept outside the Git repository under:

- `data/boundaries/ADM0/`
- `data/boundaries/ADM1/`

The `data/` directory is excluded from Git because the boundary datasets are local project assets.

## Running the Application

Create a local `.env` file containing the required database and application environment variables.

Build and start the application with:

```powershell
docker compose up --build
```

The application will then be available at:

http://localhost:8000/

## Earthquake Data Ingestion

The initial or manual ingestion can be executed through the Django management command.

Example:

```powershell
docker compose exec web python manage.py ingest_usgs --start 2026-01-01
```

The ingestion command supports:

- `--start` — start date/time in ISO 8601 format.
- `--end` — end date/time; defaults to the current UTC time.
- `--minmagnitude` — minimum earthquake magnitude; defaults to `2.5`.

For large USGS result sets, the ingestion process automatically splits the requested period and continues through additional result pages when required.

## Scheduled Earthquake Synchronization

The project includes a dedicated synchronization command designed for recurring execution.

The default synchronization period is the **previous 90 days through the current time**. This period aligns with the application's three-month update window for recently occurred events.

On Windows, the synchronization wrapper is:

```powershell
.\scripts\sync_earthquakes.ps1
```

Examples:

```powershell
.\scripts\sync_earthquakes.ps1 -LookbackDays 90
.\scripts\sync_earthquakes.ps1 -LookbackDays 7
.\scripts\sync_earthquakes.ps1 -StartDate 2026-09-01
.\scripts\sync_earthquakes.ps1 -StartDate 2026-09-01 -EndDate 2026-09-10
```

The minimum magnitude remains `2.5`.

The synchronization process:

- prevents concurrent synchronization runs through an atomic lock;
- records structured execution statistics;
- writes persistent logs;
- rotates logs when they reach the configured size;
- returns a non-zero exit code when synchronization fails.

## Logging and Observability

Synchronization logs are stored locally in:

```text
logs/earthquake-sync.log
```

The log records include information such as:

- synchronization period;
- requests and pages processed;
- created events;
- updated events;
- unchanged events;
- skipped events;
- split USGS windows;
- execution duration;
- errors and tracebacks when a synchronization fails.

The lock file is:

```text
logs/earthquake-sync.lock
```

The lock is removed after a successful or failed run when the process exits normally.

## Windows Automation

The project is configured for daily synchronization through Windows Task Scheduler.

The scheduled workflow is:

```text
Windows Task Scheduler
        |
        v
scripts/sync_earthquakes.ps1
        |
        v
Docker Compose
        |
        v
Django sync_earthquakes
        |
        v
USGS ingestion pipeline
        |
        v
PostgreSQL / PostGIS
```

The current Windows configuration uses a daily scheduled execution. Docker Desktop is configured to start when the user signs in, and the task is configured to run only when the user is logged on.

## REST API

The application exposes a REST endpoint for retrieving earthquakes intersecting a geographic viewport.

The endpoint accepts the viewport boundaries as geographic coordinates and returns earthquake information suitable for rendering on the map.

The API currently:

- validates viewport parameters;
- applies the minimum magnitude filter;
- performs a spatial query against the earthquake geometry;
- orders results by magnitude and event date;
- limits the response to **1000 earthquakes**;
- returns earthquake magnitudes formatted to one decimal place.

The API is intentionally viewport-based rather than paginated for the current project scope.

## Map Interface

The frontend is built with Leaflet.

The map provides:

- earthquake markers;
- magnitude-dependent marker size and color;
- marker clustering;
- click-to-select interaction;
- synchronized map/list selection;
- viewport-driven data loading;
- earthquake sorting;
- continent navigation;
- zoom controls;
- magnitude legend;
- earthquake count for the current viewport.

Clusters display the number of earthquakes they contain. Cluster size and visual intensity are based on the strongest earthquake represented by the cluster.

## Boundary Data

Administrative boundaries are based on geoBoundaries datasets.

The project uses:

- ADM0 for countries.
- ADM1 for first-level administrative regions.

The boundary datasets are downloaded and imported locally. They are not included in the Git repository.

Spatial assignment uses PostGIS `ST_Covers`, allowing earthquake points located on administrative boundary edges to be handled consistently.

## Testing

The project includes automated tests covering the main application components.

Run the test suite with:

```powershell
docker compose exec web python manage.py test
```

The current documented validation checkpoint contains **33 tests**.

Additional project validation includes:

- Django migration checks.
- Database integrity checks.
- Boundary duplicate checks.
- Earthquake geometry validation.
- Ingestion and synchronization runs against the USGS API.
- Manual validation of the interactive map and API.

## Configuration and Defaults

Important application defaults and limits are centralized where appropriate.

Current key values include:

- Minimum earthquake magnitude: `2.5`
- API maximum viewport results: `1000`
- USGS single-request result limit: `20000`
- Scheduled synchronization lookback: `90 days`
- Existing-event update window: `3 months`
- Synchronization log maximum size: `5 MB`
- Synchronization log backup count: `5`

These values should be reviewed before changing ingestion, API, or scheduling behavior.

## Operational Notes

The daily synchronization does not update administrative boundary datasets. Boundary data is treated as relatively static project reference data and is managed separately from recurring earthquake synchronization.

Earthquakes located offshore may not receive a country or first-level administrative region when their coordinates do not fall within the available administrative polygons. This is expected behavior and does not indicate a failure of the API or ingestion process.

The project deliberately keeps raw/local boundary datasets and environment-specific configuration outside version control.

## Pilot Project Closure

The first project cycle has reached the stage where the main functional pipeline is implemented and validated:

```text
USGS
  |
  v
Ingestion
  |
  v
Transformation
  |
  v
PostgreSQL / PostGIS
  |
  +--> Administrative assignment
  |
  v
REST API
  |
  v
Leaflet Map
```

The remaining work is primarily project closure and refinement rather than implementation of the core pipeline. This includes final repository review, README and technical documentation maintenance, final validation, and identification of potential improvements for a future project cycle.

## Future Development

Potential future work may include:

- additional earthquake metadata and filtering;
- richer map interaction;
- performance optimization for larger datasets;
- improved API capabilities;
- expanded automated test coverage;
- more advanced deployment and operational infrastructure;
- additional geographic or seismic data sources.

These items are outside the scope of the current first project cycle.

## License

No project license has been defined yet.
