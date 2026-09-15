Earthquake Map - First Pilot Project
=====================================

Project status
--------------
First pilot project - substantially complete and in the closing/documentation phase.

This project is a Django/PostgreSQL/PostGIS application that ingests earthquake
events from the USGS FDSN Event Web Service, enriches them with administrative
boundaries from geoBoundaries, and presents the resulting local dataset through
a viewport-oriented REST API and a Leaflet map frontend.

The project is intentionally documented as a first pilot rather than as a
production deployment.

System architecture
-------------------
The main application flow can be summarized as:

    +--------------------+
    |       User         |
    |  Leaflet frontend  |
    +---------+----------+
              |
              | HTTP / REST
              v
    +--------------------+
    |   Django / DRF     |
    |  Viewport API      |
    +---------+----------+
              |
              | PostGIS query
              v
    +--------------------+
    | PostgreSQL/PostGIS |
    | Earthquakes +      |
    | boundary tables    |
    +--------------------+

Data ingestion and synchronization are separate operational flows:

    +----------------+       +--------------------+
    | USGS FDSN API  | ----> | USGS ingestion     |
    +----------------+       | / synchronization  |
                             +----------+---------+
                                        |
                                        v
                             +--------------------+
                             | PostgreSQL/PostGIS |
                             +--------------------+


Current capabilities
--------------------
- USGS earthquake ingestion.
- Resumable ingestion with pagination and recursive time-window splitting.
- Three-month update eligibility for recent earthquake records.
- geoBoundaries ADM0 and ADM1 ingestion.
- Spatial country and ADM1 enrichment using PostGIS.
- Local PostgreSQL/PostGIS operational dataset.
- Viewport-oriented read-only REST API.
- Leaflet/OpenStreetMap interactive map.
- Marker clustering with magnitude-dependent visual styling.
- Earthquake list synchronized with map selection.
- Daily Windows synchronization through Task Scheduler.
- Rotating synchronization logs and atomic synchronization locking.
- Frontend diagnostic logging controlled by DEBUG_MODE.
- Django debug mode controlled by DJANGO_DEBUG.
- Automated Django test suite: 43 tests currently passing.

Technology stack
----------------
- Python 3.14
- Django 6.1
- Django REST Framework
- PostgreSQL + PostGIS
- GDAL / OGR
- Docker Compose
- Leaflet
- Leaflet.markercluster 1.5.3
- OpenStreetMap
- USGS FDSN Event Web Service
- geoBoundaries

Project structure
-----------------
src/
    Application source code, Django configuration, ingestion, API and frontend.

data/
    Local boundary/source datasets. Excluded from Git.

logs/
    Runtime synchronization logs and lock files. Excluded from Git.

scripts/
    Platform-specific operational wrappers.

doc/
    Project documentation. Excluded from Git.

compose.yaml
    Docker Compose development environment.

.env
    Local environment configuration and secrets. Excluded from Git.

Important: .env, local data, runtime logs, editor metadata, Python caches,
build artifacts and generated archives must not be committed.

Running the application
-----------------------
Start the services:

    docker compose up -d

Check service state:

    docker compose ps

Open the application:

    http://localhost:8000/

The web service is exposed on port 8000. PostgreSQL is exposed on port 5432
for the local development environment.

The source and data directories are mounted into the web container:

    ./src:/app/src
    ./data:/app/data
    ./logs:/app/logs

Health checks and validation
----------------------------
Run Django's system checks:

    docker compose exec web python manage.py check

Confirm that no unexpected migration is required:

    docker compose exec web python manage.py makemigrations --check --dry-run

Run the complete automated test suite:

    docker compose exec web python manage.py test

Current validation result:

    43 tests, all passing.


USGS ingestion flow
-------------------
A direct ingestion request follows this process:

    USGS FDSN Event Web Service
                 |
                 v
           USGSClient
                 |
                 v
        Request up to 20,000
                 |
          +------+------+
          |             |
       HTTP 200       HTTP 400
          |             |
          v             v
     Process page   Split time window
          |             |
          |        +----+----+
          |        |         |
          |     earlier     later
          |        |         |
          +--------+---------+
                   |
                   v
             Transform data
                   |
                   v
          Import / update DB

Offset pagination is used when a result set spans multiple pages.

USGS earthquake ingestion
-------------------------
The direct ingestion command is:

    docker compose exec web python manage.py ingest_usgs

Its defaults are distinct from the scheduled synchronization command.

Direct-ingestion defaults:
- Start: 2026-01-01
- End: current UTC time
- Minimum magnitude: 2.5
- USGS request/page size: 20,000
- Initial offset: 1
- HTTP timeout: 60 seconds

The direct-ingestion defaults are defined in:

    src/ingestion/management/commands/ingest_usgs.py
    src/ingestion/usgs_client.py

USGS HTTP 400 result-limit responses trigger recursive time-window splitting.
Large result sets are continued through offset pagination.


Scheduled synchronization flow
------------------------------
The normal Windows operational path is:

    Windows Task Scheduler
             |
             v
    sync_earthquakes.ps1
             |
             v
    docker compose exec
             |
             v
    Django sync_earthquakes
             |
             v
        USGS FDSN API
             |
             v
    Create / update / unchanged
             |
             v
      PostgreSQL/PostGIS
             |
             v
    Rotating sync log + exit code

An atomic lock prevents concurrent synchronization runs.

Scheduled synchronization
-------------------------
The operational synchronization entry point is:

    sync_earthquakes

The Windows wrapper is:

    .\scripts\sync_earthquakes.ps1

Default synchronization:

    .\scripts\sync_earthquakes.ps1 -LookbackDays 90

Other useful examples:

    .\scripts\sync_earthquakes.ps1 -LookbackDays 7

    .\scripts\sync_earthquakes.ps1 -StartDate 2026-01-01

    .\scripts\sync_earthquakes.ps1 -StartDate 2026-09-01 -EndDate 2026-09-10

Synchronization defaults:
- Lookback: 90 days
- Minimum magnitude: 2.5
- Progress interval: 500 events
- Log maximum size: 5 MB
- Rotated backups: 5

These values are defined primarily in:

    src/ingestion/management/commands/sync_earthquakes.py

The progress interval is defined in:

    src/ingestion/management/commands/ingest_usgs.py

The PowerShell wrapper defaults and validation range are defined in:

    scripts/sync_earthquakes.ps1

Synchronization logging and locking
-----------------------------------
Primary log:

    logs/earthquake-sync.log

Lock file:

    logs/earthquake-sync.lock

View the latest log entries:

    Get-Content .\logs\earthquake-sync.log -Tail 30

Follow the log while a synchronization is running:

    Get-Content .\logs\earthquake-sync.log -Wait

Check whether the lock exists:

    Test-Path .\logs\earthquake-sync.lock

Synchronization statistics include:
- created
- updated
- unchanged
- skipped
- requests
- pages
- split_windows
- duration

The synchronization lock is created atomically and prevents concurrent runs.
Successful completion returns exit code 0; failures return a non-zero exit code.

Windows automation
------------------
Windows Task Scheduler is configured for:

- Task: Earthquake Map - USGS Synchronization
- Frequency: Daily
- Time: 10:00 local Windows time
- Start date: 12 September 2026
- Logon mode: Run only when user is logged on
- Overlap policy: Do not start a new instance
- Synchronization window: 90 days

Docker Desktop is configured to start when the user signs in.

The task was manually launched and completed successfully. Completion was
confirmed through the persistent synchronization log and absence of the lock
file.

REST API
--------
Endpoint:

    /api/earthquakes/

Required viewport parameters:

    min_lat
    max_lat
    min_lon
    max_lon

The API:
- uses PostGIS spatial filtering;
- applies a minimum magnitude of 2.5;
- returns a maximum of 1000 results;
- orders by magnitude descending and event date descending;
- is read-only;
- currently defers pagination.

The API result limit is defined in:

    src/earthquakes/constants.py


Frontend request flow
---------------------
Map interaction and API refresh follow this process:

    User moves / zooms map
              |
              v
        Leaflet moveend
              |
              v
       Read map viewport
              |
              v
      GET /api/earthquakes/
              |
              v
     Django + PostGIS filter
              |
              v
       JSON earthquake data
              |
        +-----+------+
        |            |
        v            v
     Markers      Earthquake
     / clusters      list
        |            |
        +-----+------+
              |
              v
       Synchronized view

Frontend
--------
The frontend is implemented with Leaflet and OpenStreetMap.

Main behavior:
- Initial viewport: Europe.
- Viewport changes refresh the API data.
- Earthquakes are displayed as individual markers and clusters.
- The left-side list supports newest, oldest, highest magnitude and lowest
  magnitude sorting.
- List and map selection are synchronized.
- A viewport earthquake count is displayed.
- A globe control provides continent navigation.
- A magnitude legend is displayed near the map scale.

Frontend files:
- map.html => page structure and template markup.
- map.css => layout and presentation.
- earthquake-style.js => magnitude/cartographic visual configuration.
- map.js => Leaflet behavior, API interaction, list interaction, viewport
  handling and frontend diagnostics.

Marker clustering
------------------
Leaflet.markercluster version 1.5.3 is used.

Current clustering configuration:
- Clustering disabled at zoom 10.
- Minimum cluster radius: 11 px.
- Default cluster opacity: 0.75.
- Active cluster opacity: 0.90.
- Maximum cluster radius: 60 px.
- Spiderfy disabled.

Clusters display their earthquake count and derive their visual size and color
from the strongest earthquake in the cluster. Magnitude text is not displayed
inside clusters.

Frontend debugging
------------------
Frontend diagnostic logging is retained for troubleshooting but is disabled
by default.

Implementation:

    src/map/static/map/js/map.js

Normal setting:

    const DEBUG_MODE = false;

To temporarily enable diagnostics:

    const DEBUG_MODE = true;

Reload http://localhost:8000/ and inspect the browser developer console.

The diagnostics cover the main map flow, including viewport calculation,
API request/response handling, normalization, marker updates, list rendering
and viewport count updates.

After troubleshooting, restore:

    const DEBUG_MODE = false;

This mode was manually verified with both enabled and disabled states on
15 September 2026.

Django debug configuration
--------------------------
Django debug mode is controlled through the environment variable:

    DJANGO_DEBUG

The local pilot .env currently enables it:

    DJANGO_DEBUG=True

The application settings default to False when DJANGO_DEBUG is not defined.

Implementation:

    src/config/settings.py

This setting is separate from the frontend DEBUG_MODE flag.


Geographic enrichment flow
--------------------------
Boundary preparation and earthquake enrichment use the following flow:

    geoBoundaries
         |
         +------------------+
         |                  |
         v                  v
      ADM0 data          ADM1 data
         |                  |
         v                  v
    Country table       Region table
         \                  /
          \                /
           +------v-------+
                  |
             PostGIS ST_Covers
                  |
                  v
        Earthquake geographic
             assignment

The stable ADM1 source identity is source_boundary_id.
Region codes may remain NULL when the source does not provide them consistently.

Boundary data
-------------
Boundary source data is stored locally under:

    data/boundaries/ADM0/
    data/boundaries/ADM1/

The boundary datasets are excluded from Git.

Current validated boundary state:
- 230 ADM0 country records.
- 3,235 ADM1 region records.
- 198 distinct ADM1 country codes.
- 0 duplicate ADM0 country codes.
- 0 duplicate ADM1 source_boundary_id values.
- Region codes may legitimately be NULL.
- Spatial assignment uses PostGIS ST_Covers.

The boundary tables are:

    tbl_boundary_country
    tbl_boundary_region

The project uses source_boundary_id as the stable ADM1 source identity.

Configuration and defaults
--------------------------
Key behavior-affecting values and their source files:

- Application minimum magnitude: 2.5
  Source: src/earthquakes/constants.py

- API maximum results: 1000
  Source: src/earthquakes/constants.py

- USGS maximum result page: 20,000
  Source: src/ingestion/usgs_client.py

- USGS request limit: 20,000
  Source: src/ingestion/usgs_client.py

- USGS initial offset: 1
  Source: src/ingestion/usgs_client.py

- USGS request timeout: 60 seconds
  Source: src/ingestion/usgs_client.py

- Direct ingestion start: 2026-01-01
  Source: src/ingestion/management/commands/ingest_usgs.py

- Direct ingestion end: current UTC time
  Source: src/ingestion/management/commands/ingest_usgs.py

- Synchronization lookback: 90 days
  Source: src/ingestion/management/commands/sync_earthquakes.py

- Synchronization progress interval: 500
  Source: src/ingestion/management/commands/ingest_usgs.py

- Synchronization log maximum size: 5 MB
  Source: src/ingestion/management/commands/sync_earthquakes.py

- Synchronization log backups: 5
  Source: src/ingestion/management/commands/sync_earthquakes.py

- PowerShell LookbackDays default: 90
  Source: scripts/sync_earthquakes.ps1

- PowerShell LookbackDays range: 1–3650
  Source: scripts/sync_earthquakes.ps1

- Frontend DEBUG_MODE: false
  Source: src/map/static/map/js/map.js

Testing
-------
The current automated suite contains 43 tests and all tests pass.

Validated areas include:
- USGS ingestion.
- Pagination and offset handling.
- Synchronization period calculation.
- Explicit date-range handling.
- Input validation.
- Synchronization locking.
- Management-command orchestration.
- Real synchronization runs.
- Windows Task Scheduler execution.

The frontend diagnostic mode was also manually verified in both enabled and
disabled states.

Important commands
------------------
Git:

    git status
    git log --oneline -10
    git fetch origin
    git status
    git add .
    git commit -m "Descriptive commit message"
    git push origin main

Docker:

    docker compose up -d
    docker compose ps
    docker compose up -d --force-recreate web
    docker compose down
    docker compose logs web --tail 30
    docker compose logs -f web

Django:

    docker compose exec web python manage.py check
    docker compose exec web python manage.py makemigrations --check --dry-run
    docker compose exec web python manage.py test

Operational synchronization:

    .\scripts\sync_earthquakes.ps1 -LookbackDays 90

Clean source archive on Windows
--------------------------------
For a Windows-compatible ZIP, use PowerShell with a small, selective staging
directory. Do not copy the complete repository into staging because local
data/ may contain several gigabytes of boundary/source data.

The source archive should contain the project source and release-level files:

    .gitignore
    LICENSE
    README.md
    compose.yaml
    Dockerfile
    requirements.txt
    scripts/
    src/

The archive should exclude:
- data/
- src/data/
- .git/
- .env
- .env.*
- __pycache__/
- *.pyc
- .pytest_cache/
- .venv/
- venv/
- *.zip
- *.log
- .vscode/
- doc/
- logs/
- *.egg-info/
- editor temporary files such as ~$*.docx

Create a small temporary staging directory:

```powershell
$Staging = Join-Path $env:TEMP "earthquake-map-source"

if (Test-Path $Staging) {
    Remove-Item $Staging -Recurse -Force
}

New-Item -ItemType Directory -Path $Staging | Out-Null
```

Copy only the required root files:

```powershell
$RootFiles = @(
    ".gitignore",
    "LICENSE",
    "README.md",
    "compose.yaml",
    "Dockerfile",
    "requirements.txt"
)

foreach ($File in $RootFiles) {
    if (Test-Path $File) {
        Copy-Item $File -Destination $Staging
    }
}
```

Copy the operational scripts:

```powershell
robocopy .\scripts "$Staging\scripts" /E `
    /XD __pycache__ .pytest_cache `
    /XF *.pyc *.pyo *.pyd *.log *.zip
```

Copy the application source while explicitly excluding local data and artifacts:

```powershell
robocopy .\src "$Staging\src" /E `
    /XD data __pycache__ .pytest_cache `
    /XF *.pyc *.pyo *.pyd *.log *.zip
```

Create the ZIP:

```powershell
$Zip = Join-Path (Get-Location) "earthquake-map-source.zip"

if (Test-Path $Zip) {
    Remove-Item $Zip -Force
}

Compress-Archive `
    -Path "$Staging\*" `
    -DestinationPath $Zip `
    -CompressionLevel Optimal
```

Verify the archive contents before distribution:

```powershell
tar -tf $Zip
```

The resulting archive is a distribution artifact and must not be committed to
the Git repository.

Project license
---------------
Project-authored source code is intended to be released under the GNU General
Public License version 3 (GPL v3).

The root repository should contain:

    LICENSE

The project GPL v3 license applies to project-authored source code. It does not
automatically relicense third-party datasets, libraries, map tiles or external
services.

Third-party data and services
-----------------------------
USGS
    Earthquake event data and FDSN Event Web Service. Use remains subject to
    applicable USGS data/service terms.

geoBoundaries
    ADM0 and ADM1 administrative boundary datasets. The applicable license and
    attribution requirements of the specific source version must be respected.

OpenStreetMap
    Base map data/tiles. Applicable OpenStreetMap and tile-provider terms
    remain in force.

Leaflet
    Third-party mapping library. Its own license applies.

Leaflet.markercluster
    Third-party clustering library. Its own license applies.

Django, Django REST Framework, PostgreSQL/PostGIS and GDAL/OGR
    Third-party software. Their respective licenses apply independently of
    the project GPL v3 license.

Group / Team
------------
The Earthquake Map First Pilot was developed through a collaborative
human–AI development model, with responsibilities divided between project
leadership and technical implementation.

Project lead / product role - Human:
- Responsible for project direction, requirements, priorities and scope.
- Defines acceptance criteria and makes final technical and product decisions.
- Reviews and validates implementation results.
- Retains responsibility for the final project outcome.

Architecture, implementation and technical support - AI:
- Supports system architecture and technical design.
- Supports implementation, debugging, testing and technical analysis.
- Supports documentation and identification of implementation risks and
  potential improvements.

Collaborative development:
- Design choices, implementation changes, validation, troubleshooting and
  documentation were developed iteratively through interaction between the
  project lead and the AI assistant.
- The AI assistant provides technical proposals and implementation support.
- The project lead reviews the results, performs validation and retains final
  decision-making responsibility.

Future development
------------------
The first pilot is substantially complete. Remaining work is mainly related
to portability, source-data lifecycle, maintainability and potential future
scaling.

Deferred or future items:
- Validate Linux cron scheduling when Linux deployment is introduced.
- Validate future geoBoundaries refreshes before accepting new source versions.
- Revisit boundary-table schema ownership if operational requirements change.
- Revisit API pagination if the query model or result population requires it.
- Consider production-grade orchestration and monitoring separately from the
  current local Docker/Windows deployment model.
- Consider a more formal release/package process if the project moves beyond
  the first pilot.

Repository hygiene
-------------------
The following are intentionally excluded from version control:
- Local boundary/source data.
- Runtime synchronization logs.
- Environment files containing secrets.
- Documentation working files.
- Editor metadata.
- Python caches and build artifacts.
- Generated source archives.

Documentation
-------------
Primary technical documentation:

    Earthquake Map - First Pilot Project
    Architecture & Technical Documentation
    Version 16
    Documentation checkpoint: 15 September 2026

The detailed documentation covers architecture, data model, ingestion,
synchronization, API, frontend behavior, debugging, automation, validation,
architectural decisions, licensing and future work.

The documentation includes process diagrams for the main architecture,
ingestion, synchronization, geographic enrichment and frontend request flows,
because these processes are easier to understand visually than through prose alone.