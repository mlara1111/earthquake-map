/*
    Main earthquake map application.

    This file contains:

    - Leaflet map initialization
    - Base map configuration
    - Custom zoom and globe controls
    - Continent navigation
    - Geographic scale
    - Earthquake API communication
    - Earthquake clustering
    - Earthquake popups
    - Earthquake list rendering
    - List/map synchronization
    - Viewport earthquake count

    Earthquake visual configuration belongs in earthquake-style.js.
*/


const API_URL = "/api/earthquakes/";


/*
    Initial map viewport.

    Europe is used as the default starting area for the MVP.
*/

const INITIAL_MAP_CENTER = [50.0, 10.0];
const INITIAL_MAP_ZOOM = 4;


/*
    Continent viewport definitions.

    Each entry contains a map center and zoom level suitable for
    displaying the corresponding continent with visible country
    boundaries.
*/

const CONTINENT_VIEWS = {
    Europe: {
        center: [54.0, 15.0],
        zoom: 4,
    },

    "North America": {
        center: [40.0, -100.0],
        zoom: 3,
    },

    "South America": {
        center: [-15.0, -60.0],
        zoom: 3,
    },

    Asia: {
        center: [35.0, 100.0],
        zoom: 3,
    },

    Africa: {
        center: [5.0, 20.0],
        zoom: 3,
    },

    Oceania: {
        center: [-25.0, 135.0],
        zoom: 4,
    },

    Antarctica: {
        center: [-75.0, 0.0],
        zoom: 3,
    },
};


/*
    Current earthquake records returned for the map viewport.
*/

let currentEarthquakes = [];


/*
    Current list sorting mode.
*/

let currentSort = "newest";


/*
    ID of the currently selected earthquake.
*/

let selectedEarthquakeId = null;


/*
 * Earthquake waiting to be opened after a viewport change.
 *
 * When selecting an earthquake requires a zoom operation, the old
 * MarkerCluster layer must not be reused after the viewport reload.
 * The ID is therefore kept until the new viewport dataset creates
 * the corresponding marker again.
 */

let pendingSelectedEarthquakeId = null;


/*
    Map marker lookup.

    The string representation of the earthquake ID is used consistently
    so that API values and DOM dataset values can be compared safely.
*/

const earthquakeMarkerById = new Map();


/*
    Track the latest API request.

    This prevents an older viewport request from overwriting the result
    of a newer viewport request.
*/

let latestRequestId = 0;


/*
    Initialize the Leaflet map.

    The standard Leaflet zoom control is disabled because the MVP uses
    its own integrated navigation control.
*/

const map = L.map("map", {
    zoomControl: false,
}).setView(
    INITIAL_MAP_CENTER,
    INITIAL_MAP_ZOOM
);


/*
    OpenStreetMap base layer.
*/

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
    }
).addTo(map);


/*
    Add the geographic scale.

    The CSS positions this control to the right of the earthquake panel
    so that the scale remains visible on the map itself.
*/

L.control.scale({
    position: "bottomleft",
    imperial: false,
}).addTo(map);


/*
    Earthquake count element.

    This remains independent from Leaflet's controls so that it can
    stay fixed in the upper-right corner.
*/

const earthquakeCount = document.getElementById(
    "earthquake-count"
);


/*
    Earthquake list element.
*/

const earthquakeList = document.getElementById(
    "earthquake-list"
);


/*
    Sorting selector.
*/

const earthquakeSort = document.getElementById(
    "earthquake-sort"
);


/*
    Create the custom map navigation control.

    The control contains:

    - vertical + / - zoom buttons
    - globe button
    - vertical continent menu

    The control itself is positioned on the LEFT side of the map.
    CSS moves it just to the right of the earthquake panel.
*/

function createMapNavigationControl() {
    const control = L.control({
        position: "topleft",
    });


    control.onAdd = function () {
        const container = L.DomUtil.create(
            "div",
            "map-navigation-control"
        );


        /*
            Prevent clicks and scrolling inside the control from
            propagating to the map.
        */

        L.DomEvent.disableClickPropagation(
            container
        );

        L.DomEvent.disableScrollPropagation(
            container
        );


        /*
            Create the vertical zoom group.
        */

        const zoomButtons =
            document.createElement("div");

        zoomButtons.className =
            "map-zoom-buttons";


        const zoomInButton =
            document.createElement("button");

        zoomInButton.type = "button";
        zoomInButton.className =
            "map-zoom-button";

        zoomInButton.setAttribute(
            "aria-label",
            "Zoom in"
        );

        zoomInButton.setAttribute(
            "title",
            "Zoom in"
        );

        zoomInButton.textContent = "+";


        const zoomOutButton =
            document.createElement("button");

        zoomOutButton.type = "button";
        zoomOutButton.className =
            "map-zoom-button";

        zoomOutButton.setAttribute(
            "aria-label",
            "Zoom out"
        );

        zoomOutButton.setAttribute(
            "title",
            "Zoom out"
        );

        zoomOutButton.textContent = "−";


        zoomButtons.appendChild(
            zoomInButton
        );

        zoomButtons.appendChild(
            zoomOutButton
        );


        /*
            Create the globe wrapper.

            The wrapper is positioned relative to the globe button
            so that the continent menu can open directly underneath it.
        */

        const globeWrapper =
            document.createElement("div");

        globeWrapper.className =
            "globe-wrapper";


        /*
            Create the globe button.

            An inline SVG is used instead of an emoji so that the icon
            renders consistently across browsers and operating systems.
        */

        const globeButton =
            document.createElement("button");

        globeButton.type = "button";
        globeButton.className =
            "globe-button";

        globeButton.setAttribute(
            "aria-label",
            "Select continent"
        );

        globeButton.setAttribute(
            "title",
            "Select continent"
        );


        globeButton.innerHTML = `
            <svg
                viewBox="0 0 24 24"
                width="20"
                height="20"
                aria-hidden="true"
                focusable="false"
            >
                <circle
                    cx="12"
                    cy="12"
                    r="9"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                />

                <ellipse
                    cx="12"
                    cy="12"
                    rx="4"
                    ry="9"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                />

                <path
                    d="M3 12h18"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                />

                <path
                    d="M5 7.5h14M5 16.5h14"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.1"
                />
            </svg>
        `;


        /*
            Create the vertical continent menu.
        */

        const continentMenu =
            document.createElement("div");

        continentMenu.className =
            "continent-menu";


        /*
            Add one compact button for each continent.
        */

        Object.keys(
            CONTINENT_VIEWS
        ).forEach(
            (continentName) => {
                const button =
                    document.createElement("button");

                button.type = "button";

                button.className =
                    "continent-menu-button";

                button.textContent =
                    continentName;


                /*
                    Navigate to the selected continent.

                    The resulting map movement triggers moveend,
                    which reloads the earthquake viewport automatically.
                */
                button.addEventListener(
                    "click",
                    () => {
                        const view =
                            CONTINENT_VIEWS[
                                continentName
                            ];

                        console.log(
                            "[DEBUG] Continent selected:", // debug log to trace continent selection
                            continentName
                        );

                        console.log(
                            "[DEBUG] Target view:", // debug log to trace target view
                            view
                        );

                        continentMenu.classList.remove(
                            "open"
                        );

                        map.setView(
                            view.center,
                            view.zoom,
                            {
                                animate: true,
                            }
                        );

                        console.log(
                            "[DEBUG] setView() called" // debug log to trace setView() calls
                        );
                    }
                );


                continentMenu.appendChild(
                    button
                );
            }
        );


        /*
            Toggle the continent menu.
        */

        globeButton.addEventListener(
            "click",
            () => {
                continentMenu.classList.toggle(
                    "open"
                );
            }
        );


        /*
            Zoom in.
        */

        zoomInButton.addEventListener(
            "click",
            () => {
                map.zoomIn();
            }
        );


        /*
            Zoom out.
        */

        zoomOutButton.addEventListener(
            "click",
            () => {
                map.zoomOut();
            }
        );


        globeWrapper.appendChild(
            globeButton
        );

        globeWrapper.appendChild(
            continentMenu
        );


        container.appendChild(
            zoomButtons
        );

        container.appendChild(
            globeWrapper
        );


        return container;
    };


    control.addTo(map);

    return control;
}


/*
    Initialize the custom navigation controls.
*/

createMapNavigationControl();


/*
    Create the horizontal magnitude legend.

    The legend deliberately uses the same magnitude color progression
    as the earthquake markers.
*/

function createMagnitudeLegend() {
    const legend = L.control({
        position: "bottomright",
    });


    legend.onAdd = function () {
        const container =
            L.DomUtil.create(
                "div",
                "magnitude-legend"
            );


        L.DomEvent.disableClickPropagation(
            container
        );

        L.DomEvent.disableScrollPropagation(
            container
        );


        const title =
            document.createElement("div");

        title.className =
            "magnitude-legend-title";

        title.textContent =
            "Magnitude";

        container.appendChild(
            title
        );


        const gradient =
            document.createElement("div");

        gradient.className =
            "magnitude-legend-gradient";

        container.appendChild(
            gradient
        );


        const labels =
            document.createElement("div");

        labels.className =
            "magnitude-legend-labels";


        const magnitudeLabels = [
            "< 4.0",
            "5.0",
            "6.0",
            "7.0",
            "≥ 7.5",
        ];


        magnitudeLabels.forEach(
            (label) => {
                const span =
                    document.createElement("span");

                span.textContent =
                    label;

                labels.appendChild(
                    span
                );
            }
        );


        container.appendChild(
            labels
        );


        return container;
    };


    legend.addTo(map);

    return legend;
}


createMagnitudeLegend();


/*
    Create the earthquake marker cluster group.

    Cluster size and color are determined by the strongest earthquake
    represented by the cluster.
*/

const earthquakeMarkers =
    L.markerClusterGroup({
        maxClusterRadius:
            CLUSTER_MAX_RADIUS,

        disableClusteringAtZoom:
            CLUSTER_DISABLE_ZOOM,

        /*
            The MVP uses zoom-to-split rather than spiderfy.
        */

        spiderfyOnMaxZoom: false,

        showCoverageOnHover: false,

        zoomToBoundsOnClick: true,

        animate: true,

        iconCreateFunction:
            createClusterIcon,
    });


map.addLayer(
    earthquakeMarkers
);


/*
    Return the strongest earthquake magnitude represented by a cluster.
*/

function getClusterMaximumMagnitude(
    cluster
) {
    const childMarkers =
        cluster.getAllChildMarkers();


    if (
        childMarkers.length === 0
    ) {
        return null;
    }


    const magnitudes =
        childMarkers
            .map(
                (marker) =>
                    Number(
                        marker.earthquakeMagnitude
                    )
            )
            .filter(
                (magnitude) =>
                    Number.isFinite(
                        magnitude
                    )
            );


    if (
        magnitudes.length === 0
    ) {
        return null;
    }


    return Math.max(
        ...magnitudes
    );
}


/*
    Create the visual representation of an earthquake cluster.

    The number represents the number of earthquakes.

    Size and color represent the strongest earthquake in the cluster.
*/

function createClusterIcon(
    cluster
) {
    const childCount =
        cluster.getChildCount();


    const maximumMagnitude =
        getClusterMaximumMagnitude(
            cluster
        );


    const magnitudeColor =
        getMagnitudeColor(
            maximumMagnitude
        );


    const radius =
        Math.max(
            CLUSTER_MIN_RADIUS,
            getMarkerRadius(
                maximumMagnitude
            )
        );


    const diameter =
        radius * 2;


    return L.divIcon({
        html: `
            <div
                class="earthquake-cluster"
                style="
                    width: ${diameter}px;
                    height: ${diameter}px;
                    background-color: ${hexToRgba(
                        magnitudeColor,
                        CLUSTER_DEFAULT_OPACITY
                    )};
                    border-color: ${magnitudeColor};
                "
            >
                <span>${childCount}</span>
            </div>
        `,

        className:
            "earthquake-cluster-wrapper",

        iconSize: [
            diameter,
            diameter,
        ],

        iconAnchor: [
            radius,
            radius,
        ],
    });
}


/*
    Create an individual earthquake marker.
*/

function createEarthquakeMarker(
    earthquake
) {
    const magnitude =
        Number(
            earthquake.magnitude
        );


    const markerColor =
        getMagnitudeColor(
            magnitude
        );


    const radius =
        getMarkerRadius(
            magnitude
        );


    const marker = L.marker(
        [
            Number(
                earthquake.latitude
            ),
            Number(
                earthquake.longitude
            ),
        ],
        {
            icon: L.divIcon({
                className:
                    "earthquake-marker-wrapper",

                html: `
                    <div
                        class="earthquake-marker"
                        style="
                            width: ${radius * 2}px;
                            height: ${radius * 2}px;
                            background-color: ${hexToRgba(
                                markerColor,
                                DEFAULT_MARKER_OPACITY
                            )};
                            border-color: ${darkenHexColor(
                                markerColor,
                                0.20
                            )};
                            border-width: ${DEFAULT_MARKER_WEIGHT}px;
                        "
                    ></div>
                `,

                iconSize: [
                    radius * 2,
                    radius * 2,
                ],

                iconAnchor: [
                    radius,
                    radius,
                ],
            }),
        }
    );


    /*
        Store the earthquake ID on the marker.
    */

    marker.earthquakeId =
        earthquake.id;


    /*
        Store the magnitude on the marker.

        Cluster creation uses this value to determine the strongest
        earthquake represented by the cluster.
    */

    marker.earthquakeMagnitude =
        magnitude;


    /*
        Build the earthquake popup.
    */

    const popupContent = `
        <div class="earthquake-popup">
            <strong>
                Magnitude ${formatMagnitude(
                    magnitude
                )}
            </strong>
            <br>
            <strong>Date:</strong>
            ${escapeHtml(
                formatEarthquakeDate(
                    earthquake.event_date
                )
            )}
            <br>
            <strong>Depth:</strong>
            ${escapeHtml(
                formatEarthquakeDepth(
                    earthquake.depth_km
                )
            )}
            <br>
            <strong>Location:</strong>
            ${escapeHtml(
                earthquake.place
            )}
            <br>
            <strong>Country:</strong>
            ${escapeHtml(
                earthquake.country
            )}
            <br>
            <strong>Region:</strong>
            ${escapeHtml(
                earthquake.region
            )}
            ${
                earthquake.usgs_url
                    ? `
                        <br><br>
                        <a
                            href="${escapeHtml(
                                earthquake.usgs_url
                            )}"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            View on USGS
                        </a>
                    `
                    : ""
            }
        </div>
    `;


    marker.bindPopup(
        popupContent,
        {
            autoPan: false,
        }
    );


    /*
        Highlight the marker when its popup opens.
    */

    marker.on(
        "popupopen",
        () => {
            selectedEarthquakeId =
                earthquake.id;


            updateMarkerActiveState(
                marker,
                true
            );


            renderEarthquakeList();


            scrollSelectedEarthquakeIntoView();
        }
    );


    /*
        Restore the normal marker appearance when the popup closes.
    */

    marker.on(
        "popupclose",
        () => {
            updateMarkerActiveState(
                marker,
                false
            );
        }
    );


    /*
        Highlight the marker while hovering over it.
    */

    marker.on(
        "mouseover",
        () => {
            if (
                !marker.isPopupOpen()
            ) {
                updateMarkerActiveState(
                    marker,
                    true
                );
            }
        }
    );


    marker.on(
        "mouseout",
        () => {
            if (
                !marker.isPopupOpen()
            ) {
                updateMarkerActiveState(
                    marker,
                    false
                );
            }
        }
    );


    /*
        Selecting a marker also selects the corresponding list row.
    */

    marker.on(
        "click",
        () => {
            selectedEarthquakeId =
                earthquake.id;


            renderEarthquakeList();


            scrollSelectedEarthquakeIntoView();
        }
    );


    return marker;
}


/*
    Update the active visual state of an individual marker.
*/

function updateMarkerActiveState(
    marker,
    active
) {
    const element =
        marker.getElement();


    if (!element) {
        return;
    }


    const markerElement =
        element.querySelector(
            ".earthquake-marker"
        );


    if (!markerElement) {
        return;
    }


    const magnitude =
        Number(
            marker.earthquakeMagnitude
        );


    const markerColor =
        getMagnitudeColor(
            magnitude
        );


    if (active) {
        markerElement.style.backgroundColor =
            hexToRgba(
                markerColor,
                ACTIVE_MARKER_OPACITY
            );


        markerElement.style.borderColor =
            "#000000";


        markerElement.style.borderWidth =
            `${ACTIVE_MARKER_WEIGHT}px`;


        return;
    }


    markerElement.style.backgroundColor =
        hexToRgba(
            markerColor,
            DEFAULT_MARKER_OPACITY
        );


    markerElement.style.borderColor =
        darkenHexColor(
            markerColor,
            0.20
        );


    markerElement.style.borderWidth =
        `${DEFAULT_MARKER_WEIGHT}px`;
}


/*
    Format magnitude for the user interface.

    The database/API retains its precision while the UI consistently
    displays one decimal place.
*/

function formatMagnitude(value) {
    const magnitude =
        Number(value);


    if (
        !Number.isFinite(
            magnitude
        )
    ) {
        return "N/A";
    }


    return magnitude.toFixed(1);
}


/*
    Format earthquake event date in UTC.
*/

function formatEarthquakeDate(
    value
) {
    if (!value) {
        return "Unknown";
    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(value);
    }


    const day =
        String(
            date.getUTCDate()
        ).padStart(
            2,
            "0"
        );


    const month =
        String(
            date.getUTCMonth() + 1
        ).padStart(
            2,
            "0"
        );


    const year =
        date.getUTCFullYear();


    const hours =
        String(
            date.getUTCHours()
        ).padStart(
            2,
            "0"
        );


    const minutes =
        String(
            date.getUTCMinutes()
        ).padStart(
            2,
            "0"
        );


    const seconds =
        String(
            date.getUTCSeconds()
        ).padStart(
            2,
            "0"
        );


    return (
        `${day}.${month}.${year} ` +
        `${hours}:${minutes}:${seconds}`
    );
}


/*
    Format earthquake depth.

    Whole kilometers are used in the list to keep the three-column
    layout compact.
*/

function formatEarthquakeDepth(
    value
) {
    const depth =
        Number(value);


    if (
        !Number.isFinite(
            depth
        )
    ) {
        return "";
    }


    return `${Math.trunc(depth)} km`;
}


/*
    Escape API values before inserting them into HTML.
*/

function escapeHtml(value) {
    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


/*
    Build the API URL from the current map viewport.
*/

function buildEarthquakeApiUrl() {
    const bounds =
        map.getBounds();


    const minLat =
        Math.max(
            -90,
            bounds.getSouth()
        );


    const maxLat =
        Math.min(
            90,
            bounds.getNorth()
        );


    let minLon =
        bounds.getWest();


    let maxLon =
        bounds.getEast();


    /*
        If the viewport covers the complete world width, use the
        complete valid longitude range.
    */

    if (
        maxLon - minLon >= 360
    ) {
        minLon = -180;
        maxLon = 180;
    } else {
        minLon =
            Math.max(
                -180,
                minLon
            );

        maxLon =
            Math.min(
                180,
                maxLon
            );
    }


    const params =
        new URLSearchParams({
            min_lat: minLat,
            max_lat: maxLat,
            min_lon: minLon,
            max_lon: maxLon,
        });


    return (
        `${API_URL}?${params.toString()}`
    );
}


/*
    Normalize the API response.

    This supports both a plain array and a DRF response containing
    a "results" property.
*/

function normalizeEarthquakeResponse(
    data
) {
    if (
        Array.isArray(data)
    ) {
        return data;
    }


    if (
        data &&
        Array.isArray(
            data.results
        )
    ) {
        return data.results;
    }


    throw new Error(
        "Unexpected earthquake API response."
    );
}


/*
    Return earthquakes in the currently selected sort order.
*/

function getSortedEarthquakes() {
    const earthquakes =
        [
            ...currentEarthquakes
        ];


    switch (
        currentSort
    ) {
        case "oldest":
            earthquakes.sort(
                (a, b) =>
                    new Date(
                        a.event_date
                    ) -
                    new Date(
                        b.event_date
                    )
            );
            break;


        case "magnitude-desc":
            earthquakes.sort(
                (a, b) =>
                    Number(
                        b.magnitude
                    ) -
                    Number(
                        a.magnitude
                    )
            );
            break;


        case "magnitude-asc":
            earthquakes.sort(
                (a, b) =>
                    Number(
                        a.magnitude
                    ) -
                    Number(
                        b.magnitude
                    )
            );
            break;


        case "newest":
        default:
            earthquakes.sort(
                (a, b) =>
                    new Date(
                        b.event_date
                    ) -
                    new Date(
                        a.event_date
                    )
            );
            break;
    }


    return earthquakes;
}


/*
    Render the earthquake list.
*/

function renderEarthquakeList() {
    if (
        currentEarthquakes.length === 0
    ) {
        earthquakeList.innerHTML = `
            <div class="earthquake-list-status">
                No earthquakes in the current viewport.
            </div>
        `;

        return;
    }


    const earthquakes =
        getSortedEarthquakes();


    earthquakeList.innerHTML = "";


    earthquakes.forEach(
        (earthquake) => {
            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "earthquake-list-item";


            if (
                String(
                    earthquake.id
                ) ===
                String(
                    selectedEarthquakeId
                )
            ) {
                item.classList.add(
                    "selected"
                );
            }


            item.dataset.earthquakeId =
                earthquake.id;


            item.innerHTML = `
                <div class="earthquake-list-magnitude">
                    ${escapeHtml(
                        formatMagnitude(
                            earthquake.magnitude
                        )
                    )}
                </div>

                <div class="earthquake-list-main">
                    <div class="earthquake-list-date">
                        ${escapeHtml(
                            formatEarthquakeDate(
                                earthquake.event_date
                            )
                        )}
                    </div>

                    <div
                        class="earthquake-list-place"
                        title="${escapeHtml(
                            earthquake.place
                        )}"
                    >
                        ${escapeHtml(
                            earthquake.place
                        )}
                    </div>
                </div>

                <div class="earthquake-list-depth">
                    ${escapeHtml(
                        formatEarthquakeDepth(
                            earthquake.depth_km
                        )
                    )}
                </div>
            `;


            item.addEventListener(
                "click",
                () => {
                    selectEarthquake(
                        earthquake.id
                    );
                }
            );


            earthquakeList.appendChild(
                item
            );
        }
    );
}


/*
 * Select an earthquake from the list.
 *
 * The current viewport is the single source of truth.
 *
 * If the earthquake is already represented by an individual marker,
 * its popup can be opened directly.
 *
 * If the earthquake is hidden inside a cluster, the map is moved and
 * zoomed to the earthquake location. That viewport change triggers
 * moveend -> loadEarthquakes(), which replaces the complete dataset.
 * The popup is then opened on the newly created marker.
 */

function selectEarthquake(
    earthquakeId
) {
    const marker =
        earthquakeMarkerById.get(
            String(
                earthquakeId
            )
        );


    if (!marker) {
        return;
    }


    selectedEarthquakeId =
        earthquakeId;


    renderEarthquakeList();


    /*
     * If the marker already has a DOM element, it is currently displayed
     * as an individual marker rather than being hidden inside a cluster.
     *
     * No viewport change is necessary in this case.
     */

    if (marker.getElement()) {
        marker.openPopup();

        updateMarkerActiveState(
            marker,
            true
        );

        scrollSelectedEarthquakeIntoView();

        return;
    }


    /*
     * The earthquake is currently represented inside a cluster.
     *
     * Do not use MarkerCluster's zoomToShowLayer() here because it starts
     * an internal animation that can overlap with loadEarthquakes(),
     * which replaces the cluster layers after moveend.
     */

    pendingSelectedEarthquakeId =
        earthquakeId;


    /*
     * Zoom directly to the level where individual earthquake markers
     * are displayed. The map movement triggers moveend, which reloads
     * the complete dataset for the new viewport.
     */

    const targetZoom =
        Math.max(
            map.getZoom(),
            CLUSTER_DISABLE_ZOOM
        );


    map.setView(
        marker.getLatLng(),
        targetZoom,
        {
            animate: true,
        }
    );
}


/*
    Scroll the selected earthquake row into view.
*/

function scrollSelectedEarthquakeIntoView() {
    if (
        selectedEarthquakeId === null
    ) {
        return;
    }


    const selectedItem =
        earthquakeList.querySelector(
            `[data-earthquake-id="${CSS.escape(
                String(
                    selectedEarthquakeId
                )
            )}"]`
        );


    if (!selectedItem) {
        return;
    }


    selectedItem.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
    });
}

/*
 * Load earthquakes for the current map viewport.
 *
 * The viewport is the single source of truth for the earthquake data
 * displayed by the application.
 *
 * Every successful viewport request updates these three representations
 * from the same dataset:
 *
 * 1. Map markers and clusters
 * 2. Earthquake list
 * 3. Viewport earthquake counter
 *
 * This keeps the map, list, and counter synchronized after every
 * pan, zoom, or continent navigation.
 */

let latestViewportRequestId = 0;


async function loadEarthquakes() {

    console.log("[DEBUG] loadEarthquakes() called"); // debug log to trace function calls

    const requestId =
        ++latestViewportRequestId;


    /*
     * Show the loading state while the new viewport is being requested.
     */

    earthquakeCount.textContent =
        "Loading earthquakes...";


    try {
        const bounds =
            map.getBounds();

        console.log("[DEBUG] Current viewport:", {
            min_lat: bounds.getSouth(),
            max_lat: bounds.getNorth(),
            min_lon: bounds.getWest(),
            max_lon: bounds.getEast(),
        }); // debug log to trace viewport bounds


        const minLat =
            Math.max(
                -90,
                bounds.getSouth()
            );


        const maxLat =
            Math.min(
                90,
                bounds.getNorth()
            );


        let minLon =
            bounds.getWest();


        let maxLon =
            bounds.getEast();


        /*
         * If the viewport covers a complete world width, request the
         * complete valid longitude range.
         */

        if (
            maxLon - minLon >= 360
        ) {
            minLon = -180;
            maxLon = 180;
        } else {
            minLon =
                Math.max(
                    -180,
                    minLon
                );

            maxLon =
                Math.min(
                    180,
                    maxLon
                );
        }


        const params =
            new URLSearchParams({
                min_lat: minLat,
                max_lat: maxLat,
                min_lon: minLon,
                max_lon: maxLon,
            });


        /*
         * Request exactly the data belonging to the current viewport.
         */

        const url =
            `${API_URL}?${params.toString()}`;

        console.log("[DEBUG] API URL:", url); // debug log to trace the constructed API URL

        console.log("[DEBUG] Starting API fetch"); // debug log to trace the start of the API fetch

        const response = await fetch(url);

        console.log(
            "[DEBUG] API response received:", // debug log to trace the API response
            response.status,
            response.ok
        );


        if (!response.ok) {
            throw new Error(
                `Earthquake API returned HTTP ${response.status}.`
            );
        }


        const responseData = await response.json();

        console.log("[DEBUG] API JSON received"); // debug log to trace the successful receipt of JSON data
        console.log(
            "[DEBUG] API response dataset:", // debug log to trace the dataset received from the API
            Array.isArray(responseData)
                ? responseData.length
                : responseData.results?.length
        );


        /*
         * Support both a plain array and a DRF response containing
         * a "results" array.
         */

        const earthquakes =
            Array.isArray(responseData)
                ? responseData
                : responseData.results;

        console.log(
            "[DEBUG] Earthquakes normalized:", // debug log to trace the normalized earthquake dataset
            earthquakes.length
        );

        if (
            !Array.isArray(earthquakes)
        ) {
            throw new Error(
                "Unexpected earthquake API response."
            );
        }


        /*
         * A newer viewport request may already have completed while
         * this request was waiting for the API.
         *
         * Never allow an older request to overwrite the newer viewport.
         */

        if (
            requestId !==
            latestViewportRequestId
        ) {
            return;
        }


        /*
         * The previous selection belongs to the previous viewport.
         *
         * Keep it only when the selected earthquake is still part of
         * the newly returned viewport dataset.
         */

        const selectedStillVisible =
            selectedEarthquakeId !== null &&
            earthquakes.some(
                (earthquake) =>
                    String(
                        earthquake.id
                    ) ===
                    String(
                        selectedEarthquakeId
                    )
            );


        if (
            !selectedStillVisible
        ) {
            selectedEarthquakeId =
                null;
        }


        /*
         * Replace the complete in-memory viewport dataset.
         *
         * This dataset is now the source used by the earthquake list.
         */

        currentEarthquakes =
            earthquakes;

        console.log(
            "[DEBUG] currentEarthquakes updated:", // debug log to trace the update of the in-memory viewport dataset
            currentEarthquakes.length
        );


        /*
         * Remove the previous marker lookup.
         */

        earthquakeMarkerById.clear();


        /*
         * Remove every marker belonging to the previous viewport.
         */

        earthquakeMarkers.clearLayers();


        /*
         * Create markers exclusively from the new viewport dataset.
         */

        const markers =
            earthquakes.map(
                (earthquake) => {
                    const marker =
                        createEarthquakeMarker(
                            earthquake
                        );


                    earthquakeMarkerById.set(
                        String(
                            earthquake.id
                        ),
                        marker
                    );


                    return marker;
                }
            );


        /*
         * Add only the new viewport markers to the map.
         */

        earthquakeMarkers.addLayers(
            markers
        );

        /*
        * Complete a pending list selection using the marker created from
        * the newly loaded viewport dataset.
        *
        * The marker lookup now contains only markers belonging to the
        * current viewport.
        */

        if (
            pendingSelectedEarthquakeId !== null
        ) {
            const pendingMarker =
                earthquakeMarkerById.get(
                    String(
                        pendingSelectedEarthquakeId
                    )
                );


            if (pendingMarker) {
                selectedEarthquakeId =
                    pendingSelectedEarthquakeId;

                pendingSelectedEarthquakeId =
                    null;

                pendingMarker.openPopup();

                updateMarkerActiveState(
                    pendingMarker,
                    true
                );
            } else {
                pendingSelectedEarthquakeId =
                    null;

                selectedEarthquakeId =
                    null;
            }
        }

        console.log(
            "[DEBUG] Map markers updated:", // debug log to trace the update of map markers
            markers.length
        );

        /*
         * Render the list from exactly the same dataset used above
         * to create the map markers.
         */

        renderEarthquakeList();

        console.log(
            "[DEBUG] Earthquake list rendered:", // debug log to trace the rendering of the earthquake list
            currentEarthquakes.length
        );

        /*
         * Update the counter from exactly the same dataset.
         */

        earthquakeCount.textContent =
            `${earthquakes.length} earthquakes in current viewport`;

        console.log(
            "[DEBUG] Earthquake count updated:", // debug log to trace the update of the earthquake count
            earthquakeCount.textContent
        );


    } catch (error) {
        /*
         * Ignore errors from obsolete viewport requests.
         */

        if (
            requestId !==
            latestViewportRequestId
        ) {
            return;
        }


        console.error(
            "Failed to load earthquake data:",
            error
        );


        /*
         * The failed request must not leave the previous viewport
         * displayed as if it were still current.
         */

        currentEarthquakes = [];


        selectedEarthquakeId =
            null;


        earthquakeMarkerById.clear();


        earthquakeMarkers.clearLayers();


        /*
         * Keep the list and counter synchronized with the empty
         * current dataset when the request fails.
         */

        renderEarthquakeList();


        earthquakeCount.textContent =
            "Unable to load earthquakes.";
    }
}


/*
 * Reload the complete viewport dataset whenever the user finishes
 * moving or zooming the map.
 *
 * Leaflet's moveend event covers:
 *
 * - mouse/touch panning
 * - zoom buttons
 * - mouse-wheel zoom
 * - programmatic setView()
 * - continent navigation
 */
map.on(
    "moveend",
    function () {
        const bounds = map.getBounds();

        console.log(
            "[DEBUG] map moveend fired" // debug log to trace moveend events
        );

        console.log(
            "[DEBUG] Viewport after moveend:", // debug log to trace viewport bounds after moveend
            {
                min_lat: bounds.getSouth(),
                max_lat: bounds.getNorth(),
                min_lon: bounds.getWest(),
                max_lon: bounds.getEast(),
            }
        );

        loadEarthquakes();
    }
);


/*
 * Recalculate the Leaflet map dimensions after a browser resize.
 *
 * The viewport is then reloaded so that map and list remain synchronized.
 */

window.addEventListener(
    "resize",
    () => {
        map.invalidateSize();

        loadEarthquakes();
    }
);


/*
 * Change the list ordering without requesting the API again.
 *
 * Sorting changes presentation only; it does not change the viewport
 * dataset represented by the map.
 */

earthquakeSort.addEventListener(
    "change",
    () => {
        currentSort =
            earthquakeSort.value;

        renderEarthquakeList();
    }
);


/*
 * Load the initial viewport.
 *
 * The initial map position is Europe.
 */

loadEarthquakes();