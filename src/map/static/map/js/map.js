/*
    Main earthquake map application.

    This file contains Leaflet initialization, API communication,
    marker creation, clustering, popups, map interaction, and the
    magnitude legend.

    Earthquake visual configuration belongs in earthquake-style.js.
*/

/*
    Initialize the map centered approximately on California.

    The map viewport determines which earthquakes are requested
    from the backend.
*/
const map = L.map("map").setView([37.5, -119.5], 6);

/*
    Use OpenStreetMap tiles as the base map for the MVP.

    The referrer policy allows the browser to send the page origin
    when requesting cross-origin map tiles.
*/
L.tileLayer(
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
        referrerPolicy: "strict-origin-when-cross-origin"
    }
).addTo(map);

/*
    Keep the status display separate from the map itself.
*/
const earthquakeCount =
    document.getElementById("earthquake-count");

/*
    Build the API URL from the current Leaflet map viewport.

    When the map is zoomed out far enough, Leaflet can expose a
    viewport wider than the complete world. In that situation,
    longitude values can fall outside the API's valid [-180, 180]
    range. The correct representation for that situation is the
    complete world longitude range.
*/
function buildEarthquakeApiUrl() {
    const bounds = map.getBounds();

    const minLat = Math.max(
        -90,
        bounds.getSouth()
    );

    const maxLat = Math.min(
        90,
        bounds.getNorth()
    );

    let minLon = bounds.getWest();
    let maxLon = bounds.getEast();

    /*
        If the viewport covers at least one complete world width,
        request the complete longitude range instead of sending
        Leaflet's wrapped longitude values to the API.
    */
    if (maxLon - minLon >= 360) {
        minLon = -180;
        maxLon = 180;
    } else {
        /*
            Keep longitude values within the API's supported range.

            This handles the normal far-zoomed-out case without
            changing the API contract.
        */
        minLon = Math.max(
            -180,
            minLon
        );

        maxLon = Math.min(
            180,
            maxLon
        );
    }

    const params = new URLSearchParams({
        min_lat: minLat,
        max_lat: maxLat,
        min_lon: minLon,
        max_lon: maxLon
    });

    return `/api/earthquakes/?${params.toString()}`;
}

/*
    Create the magnitude legend using the same color classes
    used by the earthquake markers.

    The legend deliberately does not represent marker size.
    Color intensity is the primary magnitude encoding.
*/
function createMagnitudeLegend() {
    const legend = L.control({
        position: "bottomleft"
    });

    legend.onAdd = function () {
        const container = L.DomUtil.create(
            "div",
            "magnitude-legend"
        );

        /*
            Prevent clicks and map interactions inside the legend
            from propagating to the underlying Leaflet map.
        */
        L.DomEvent.disableClickPropagation(
            container
        );

        L.DomEvent.disableScrollPropagation(
            container
        );

        const title = document.createElement("div");

        title.className =
            "magnitude-legend-title";

        title.textContent =
            "Magnitude";

        container.appendChild(title);

        const gradient =
            document.createElement("div");

        gradient.className =
            "magnitude-legend-gradient";

        container.appendChild(gradient);

        const labels =
            document.createElement("div");

        labels.className =
            "magnitude-legend-labels";

        const magnitudeLabels = [
            "< 4.0",
            "5.0",
            "6.0",
            "7.0",
            "≥ 7.5"
        ];

        magnitudeLabels.forEach((label) => {
            const span =
                document.createElement("span");

            span.textContent = label;

            labels.appendChild(span);
        });

        container.appendChild(labels);

        return container;
    };

    legend.addTo(map);

    return legend;
}

/*
    Create the magnitude legend after the map has been initialized.
*/
const magnitudeLegend =
    createMagnitudeLegend();

/*
    Determine the strongest earthquake contained in a cluster.

    Leaflet.markercluster provides getAllChildMarkers(), which returns
    the earthquake markers represented by the cluster.

    Each earthquake marker stores its numeric magnitude in the
    earthquakeMagnitude property.
*/
function getClusterMaximumMagnitude(cluster) {
    const childMarkers =
        cluster.getAllChildMarkers();

    let maximumMagnitude = null;

    childMarkers.forEach((marker) => {
        const magnitude = Number(
            marker.earthquakeMagnitude
        );

        if (!Number.isFinite(magnitude)) {
            return;
        }

        if (
            maximumMagnitude === null
            || magnitude > maximumMagnitude
        ) {
            maximumMagnitude = magnitude;
        }
    });

    /*
        A valid earthquake cluster should always contain at least
        one valid magnitude. This fallback is defensive only.
    */
    return maximumMagnitude === null
        ? 0
        : maximumMagnitude;
}

/*
    Create the custom icon used for a cluster.

    The strongest earthquake inside the cluster determines:

    - the cluster color;
    - the cluster radius.

    The cluster count is the only text displayed inside the cluster.
*/
function createClusterIcon(cluster) {
    const maximumMagnitude =
        getClusterMaximumMagnitude(cluster);

    /*
        Use exactly the same magnitude color function as individual
        earthquakes. Therefore the cluster and an individual
        earthquake with the same magnitude class have the same color.
    */
    const clusterColor =
        getMagnitudeColor(maximumMagnitude);

    /*
        Use exactly the same magnitude radius function as individual
        earthquakes.

        A minimum radius guarantees that the count remains readable
        for low-magnitude clusters.
    */
    const clusterRadius = Math.max(
        getMarkerRadius(maximumMagnitude),
        CLUSTER_MIN_RADIUS
    );

    const clusterDiameter =
        clusterRadius * 2;

    const childCount =
        cluster.getChildCount();

    /*
        Apply transparency only to the fill.

        The border remains fully opaque so the magnitude-dependent
        color remains clearly identifiable over both land and water.
    */
    const clusterFillColor =
        hexToRgba(
            clusterColor,
            CLUSTER_DEFAULT_OPACITY
        );

    const html = `
        <div
            class="earthquake-cluster"
            style="
                width: ${clusterDiameter}px;
                height: ${clusterDiameter}px;
                background-color: ${clusterFillColor};
                border-color: ${clusterColor};
                border-width: ${DEFAULT_MARKER_WEIGHT}px;
                font-size: ${CLUSTER_COUNT_FONT_SIZE}px;
            "
        >
            <span class="earthquake-cluster-count">
                ${childCount}
            </span>
        </div>
    `;

    return L.divIcon({
        html: html,
        className: "",
        iconSize: [
            clusterDiameter,
            clusterDiameter
        ],
        iconAnchor: [
            clusterRadius,
            clusterRadius
        ]
    });
}

/*
    Create the marker cluster group.

    The default spiderfy behaviour is disabled because the MVP uses
    traditional clustering: clicking a cluster zooms into it and
    the cluster progressively divides as the map zoom increases.
*/
const earthquakeLayer =
    L.markerClusterGroup({
        maxClusterRadius:
            CLUSTER_MAX_RADIUS,

        disableClusteringAtZoom:
            CLUSTER_DISABLE_ZOOM,

        spiderfyOnMaxZoom: false,

        showCoverageOnHover: false,

        zoomToBoundsOnClick: true,

        animate: true,

        iconCreateFunction:
            createClusterIcon
    }).addTo(map);

/*
    Apply the active visual state to an individual earthquake marker.

    The border becomes black and the fill becomes more opaque.
*/
function activateEarthquakeMarker(marker) {
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

    markerElement.style.borderColor =
        "#000000";

    markerElement.style.borderWidth =
        `${ACTIVE_MARKER_WEIGHT}px`;

    markerElement.style.backgroundColor =
        getMagnitudeFillColor(
            marker.earthquakeMagnitude,
            ACTIVE_MARKER_OPACITY
        );
}

/*
    Restore the normal visual state of an individual earthquake marker.

    The border uses the exact magnitude color and the fill uses the
    same magnitude color with the default transparency.
*/
function resetEarthquakeMarker(
    marker,
    markerColor
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

    markerElement.style.borderColor =
        markerColor;

    markerElement.style.borderWidth =
        `${DEFAULT_MARKER_WEIGHT}px`;

    markerElement.style.backgroundColor =
        hexToRgba(
            markerColor,
            DEFAULT_MARKER_OPACITY
        );
}

/*
    Apply the active visual state to a cluster.

    Cluster hover follows the same visual language as individual
    earthquake hover: black border and increased fill opacity.
*/
earthquakeLayer.on(
    "clustermouseover",
    function (event) {
        const clusterElement =
            event.layer.getElement();

        if (!clusterElement) {
            return;
        }

        const clusterMarker =
            clusterElement.querySelector(
                ".earthquake-cluster"
            );

        if (!clusterMarker) {
            return;
        }

        const maximumMagnitude =
            getClusterMaximumMagnitude(
                event.layer
            );

        const clusterColor =
            getMagnitudeColor(
                maximumMagnitude
            );

        clusterMarker.style.borderColor =
            "#000000";

        clusterMarker.style.borderWidth =
            `${ACTIVE_MARKER_WEIGHT}px`;

        clusterMarker.style.backgroundColor =
            hexToRgba(
                clusterColor,
                CLUSTER_ACTIVE_OPACITY
            );
    }
);

/*
    Restore the normal cluster appearance when the cursor leaves it.
*/
earthquakeLayer.on(
    "clustermouseout",
    function (event) {
        const clusterElement =
            event.layer.getElement();

        if (!clusterElement) {
            return;
        }

        const clusterMarker =
            clusterElement.querySelector(
                ".earthquake-cluster"
            );

        if (!clusterMarker) {
            return;
        }

        const maximumMagnitude =
            getClusterMaximumMagnitude(
                event.layer
            );

        const clusterColor =
            getMagnitudeColor(
                maximumMagnitude
            );

        clusterMarker.style.borderColor =
            clusterColor;

        clusterMarker.style.borderWidth =
            `${DEFAULT_MARKER_WEIGHT}px`;

        clusterMarker.style.backgroundColor =
            hexToRgba(
                clusterColor,
                CLUSTER_DEFAULT_OPACITY
            );
    }
);

/*
    Escape values received from the API before inserting them
    into popup HTML.
*/
function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

/*
    Format the earthquake event timestamp as:
    dd.mm.YYYY hh:mm:ss

    The USGS timestamp is returned as UTC, indicated by the trailing
    "Z". UTC components are therefore used explicitly so the displayed
    event time does not depend on the browser's local timezone.
*/
function formatEarthquakeDate(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    const day = String(
        date.getUTCDate()
    ).padStart(2, "0");

    const month = String(
        date.getUTCMonth() + 1
    ).padStart(2, "0");

    const year =
        date.getUTCFullYear();

    const hours = String(
        date.getUTCHours()
    ).padStart(2, "0");

    const minutes = String(
        date.getUTCMinutes()
    ).padStart(2, "0");

    const seconds = String(
        date.getUTCSeconds()
    ).padStart(2, "0");

    return `${day}.${month}.${year} `
        + `${hours}:${minutes}:${seconds}`;
}

/*
    Format earthquake depth as a whole number of kilometers.

    Math.trunc() deliberately removes the decimal portion instead
    of rounding the value.
*/
function formatEarthquakeDepth(value) {
    const depth = Number(value);

    if (!Number.isFinite(depth)) {
        return "";
    }

    return `${Math.trunc(depth)} km`;
}

/*
    Create an individual earthquake marker.

    The marker uses the magnitude configuration from earthquake-style.js.
*/
function createEarthquakeMarker(earthquake) {
    const radius =
        getMarkerRadius(
            earthquake.magnitude
        );

    const markerColor =
        getMagnitudeColor(
            earthquake.magnitude
        );

    /*
        Use a darker version of the magnitude color for the normal marker
        border so small earthquakes remain visible against detailed maps.
    */
    const markerBorderColor =
        darkenHexColor(
            markerColor,
            0.25
        );

    const markerFillColor =
        getMagnitudeFillColor(
            earthquake.magnitude,
            DEFAULT_MARKER_OPACITY
        );

    const diameter =
        radius * 2;

    /*
        Render the individual earthquake as a Leaflet Marker
        containing a circular HTML element.

        This preserves the established visual appearance while
        allowing Leaflet.markercluster to manage the marker.
    */
    const marker =
        L.marker(
            [
                earthquake.latitude,
                earthquake.longitude
            ],
            {
                icon: L.divIcon({
                    html: `
                        <div
                            class="earthquake-marker"
                            style="
                                width: ${diameter}px;
                                height: ${diameter}px;
                                background-color: ${markerFillColor};
                                border-color: ${markerBorderColor};
                                border-width: ${DEFAULT_MARKER_WEIGHT}px;
                            "
                        ></div>
                    `,
                    className: "",
                    iconSize: [
                        diameter,
                        diameter
                    ],
                    iconAnchor: [
                        radius,
                        radius
                    ]
                })
            }
        );

    /*
        Store the magnitude directly on the marker so the cluster icon
        can determine the strongest earthquake without changing the API.
    */
    marker.earthquakeMagnitude =
        Number(earthquake.magnitude);

    /*
        Build the popup content once so hover and click interactions
        use exactly the same information.
    */
    const popupContent = `
        <strong>Magnitude:</strong>
        ${escapeHtml(
            earthquake.magnitude
        )}
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
    `;

    marker.bindPopup(
        popupContent
    );

    /*
        Track whether this marker's popup has been explicitly
        selected with a click.

        Hover creates a temporary visual highlight, while click
        converts the popup and visual highlight into a persistent
        selection.
    */
    let popupPinned = false;

    /*
        Highlight the earthquake when the cursor enters the marker.
    */
    marker.on(
        "mouseover",
        function () {
            activateEarthquakeMarker(
                this
            );

            this.openPopup();
        }
    );

    /*
        Restore the normal marker appearance when the cursor leaves
        the earthquake.

        A popup selected with click remains open and the marker
        remains highlighted.
    */
    marker.on(
        "mouseout",
        function () {
            if (!popupPinned) {
                resetEarthquakeMarker(
                    this,
                    markerColor
                );

                this.closePopup();
            }
        }
    );

    /*
        A click explicitly selects the earthquake.

        The black border and higher fill opacity therefore remain
        active after the cursor leaves the marker.
    */
    marker.on(
        "click",
        function () {
            popupPinned = true;

            activateEarthquakeMarker(
                this
            );

            this.openPopup();
        }
    );

    /*
        Reset the selection state and restore the normal marker
        appearance when the user closes the popup with Leaflet's
        close button.
    */
    marker.on(
        "popupclose",
        function () {
            popupPinned = false;

            resetEarthquakeMarker(
                this,
                markerColor
            );
        }
    );

    return marker;
}

/*
    Load earthquakes from the backend for the current map viewport.

    The backend is responsible for spatial filtering, ordering,
    and enforcing the maximum MVP result limit.
*/
async function loadEarthquakes() {
    earthquakeCount.textContent =
        "Loading earthquakes...";

    try {
        const response =
            await fetch(
                buildEarthquakeApiUrl()
            );

        /*
            Treat HTTP errors as failed API requests rather than
            attempting to process an unexpected response.
        */
        if (!response.ok) {
            throw new Error(
                `Earthquake API returned HTTP `
                + `${response.status}.`
            );
        }

        const earthquakes =
            await response.json();

        /*
            Replace the previous markers with the records returned
            for the new map viewport.
        */
        earthquakeLayer.clearLayers();

        earthquakes.forEach(
            (earthquake) => {
                const marker =
                    createEarthquakeMarker(
                        earthquake
                    );

                /*
                    Add the earthquake to the clustering layer.

                    The clusterer decides whether the marker should be
                    displayed individually or as part of a cluster.
                */
                earthquakeLayer.addLayer(
                    marker
                );
            }
        );

        earthquakeCount.textContent =
            `${earthquakes.length} earthquakes`;
    } catch (error) {
        /*
            Keep the map usable even if the earthquake API request
            fails. The browser console contains the technical error.
        */
        console.error(
            "Failed to load earthquakes:",
            error
        );

        earthquakeCount.textContent =
            "Unable to load earthquakes.";
    }
}

/*
    Reload earthquake data whenever the user finishes moving
    or zooming the map.
*/
map.on(
    "moveend",
    loadEarthquakes
);

/*
    Recalculate marker sizes when the browser viewport changes.

    Reloading the current viewport applies the new responsive scale.
*/
window.addEventListener(
    "resize",
    loadEarthquakes
);

/*
    Load the initial earthquake data for the initial map viewport.
*/
loadEarthquakes();