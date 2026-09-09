/*
    Earthquake visual configuration.

    This file defines the cartographic representation of earthquake
    magnitude, including marker size, marker color, transparency,
    cluster appearance, and responsive scaling.

    Leaflet map behaviour belongs in map.js. Keeping visual configuration
    here allows the magnitude representation to be changed independently
    from map interaction and API logic.
*/

/*
    Define discrete visual size classes for earthquake magnitudes.

    The classes intentionally use fixed sizes instead of a continuous
    mathematical formula. This makes magnitude differences visually
    predictable and easier to interpret on the map.
*/
const MAGNITUDE_RADIUS_CLASSES = [
    { max: 4.0, radius: 4 },
    { max: 4.5, radius: 6 },
    { max: 5.0, radius: 8 },
    { max: 5.5, radius: 10 },
    { max: 6.0, radius: 12 },
    { max: 6.5, radius: 15 },
    { max: 7.0, radius: 18 },
    { max: 7.5, radius: 21 },
    { max: Infinity, radius: 26 }
];

/*
    Define the orange color scale used to represent earthquake magnitude.

    Lighter orange represents lower magnitudes and progressively darker
    orange represents higher magnitudes.
*/
const MAGNITUDE_COLOR_CLASSES = [
    { max: 4.0, color: "#ffd9a8" },
    { max: 4.5, color: "#ffc27a" },
    { max: 5.0, color: "#ffad4f" },
    { max: 5.5, color: "#ff9826" },
    { max: 6.0, color: "#ff850f" },
    { max: 6.5, color: "#f47700" },
    { max: 7.0, color: "#df6500" },
    { max: 7.5, color: "#c45100" },
    { max: Infinity, color: "#a63f00" }
];

/*
    Define the normal and active visual states.

    Transparency is applied only to the fill. The border remains opaque
    so the magnitude color stays clearly visible against any map background.
*/
const DEFAULT_MARKER_OPACITY = 0.35;
const ACTIVE_MARKER_OPACITY = 0.80;

const DEFAULT_MARKER_WEIGHT = 2;
const ACTIVE_MARKER_WEIGHT = 2.5;

/*
    Define the visual parameters for earthquake clusters.

    The cluster uses the magnitude and size of the strongest earthquake
    contained in the cluster.
*/
const CLUSTER_MIN_RADIUS = 11;
const CLUSTER_DEFAULT_OPACITY = 0.75;
const CLUSTER_ACTIVE_OPACITY = 0.90;
const CLUSTER_COUNT_FONT_SIZE = 11;

/*
    Define the zoom-dependent clustering behaviour.

    A smaller cluster radius creates more, smaller clusters.
    Clustering is disabled from this zoom level downward so the individual
    earthquakes become visible at sufficiently close zoom levels.
*/
const CLUSTER_MAX_RADIUS = 60;
const CLUSTER_DISABLE_ZOOM = 10;

/*
    Determine the magnitude class for a numeric earthquake magnitude.

    This class is shared by the size and color calculations so both
    visual encodings always use the same magnitude boundaries.
*/
function getMagnitudeClass(magnitude) {
    const numericMagnitude = Number(magnitude);

    /*
        Missing or invalid magnitudes are assigned to the smallest
        visual class.
    */
    if (!Number.isFinite(numericMagnitude)) {
        return 0;
    }

    for (
        let index = 0;
        index < MAGNITUDE_RADIUS_CLASSES.length;
        index++
    ) {
        if (
            numericMagnitude
            < MAGNITUDE_RADIUS_CLASSES[index].max
        ) {
            return index;
        }
    }

    /*
        The final class uses Infinity as its upper bound.
    */
    return MAGNITUDE_RADIUS_CLASSES.length - 1;
}

/*
    Determine the base marker radius from earthquake magnitude.
*/
function getMagnitudeRadius(magnitude) {
    const magnitudeClass = getMagnitudeClass(magnitude);

    return MAGNITUDE_RADIUS_CLASSES[magnitudeClass].radius;
}

/*
    Determine the marker color from earthquake magnitude.

    Higher magnitudes use progressively darker orange.
*/
function getMagnitudeColor(magnitude) {
    const magnitudeClass = getMagnitudeClass(magnitude);

    return MAGNITUDE_COLOR_CLASSES[magnitudeClass].color;
}

/*
    Convert a hexadecimal color to an RGBA CSS value.

    This allows transparency to be applied to the fill without making
    the marker border transparent.
*/
function hexToRgba(hexColor, opacity) {
    const hex = hexColor.replace("#", "");

    const red = parseInt(
        hex.substring(0, 2),
        16
    );

    const green = parseInt(
        hex.substring(2, 4),
        16
    );

    const blue = parseInt(
        hex.substring(4, 6),
        16
    );

    return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}

/*
    Darken a hexadecimal color by the requested percentage.

    This is used for marker borders so the magnitude color remains
    recognizable while providing stronger contrast against the map.

    The original magnitude color is kept for the fill. Only the border
    receives the darker variant.
*/
function darkenHexColor(hexColor, percentage) {
    const hex = hexColor.replace("#", "");

    const red = parseInt(
        hex.substring(0, 2),
        16
    );

    const green = parseInt(
        hex.substring(2, 4),
        16
    );

    const blue = parseInt(
        hex.substring(4, 6),
        16
    );

    const factor = 1 - percentage;

    const darkenedRed = Math.round(
        red * factor
    );

    const darkenedGreen = Math.round(
        green * factor
    );

    const darkenedBlue = Math.round(
        blue * factor
    );

    return "#"
        + darkenedRed.toString(16).padStart(2, "0")
        + darkenedGreen.toString(16).padStart(2, "0")
        + darkenedBlue.toString(16).padStart(2, "0");
}

/*
    Calculate the fill color for an earthquake marker.

    The underlying color remains the magnitude-dependent orange,
    while only its alpha channel changes between visual states.
*/
function getMagnitudeFillColor(
    magnitude,
    opacity
) {
    return hexToRgba(
        getMagnitudeColor(magnitude),
        opacity
    );
}

/*
    Calculate a responsive scale based on the available browser viewport.

    CSS pixels are used because Leaflet marker sizes are expressed
    in CSS pixels as well.
*/
function getScreenScale() {
    const referenceWidth = 1366;
    const referenceHeight = 768;

    const widthScale =
        window.innerWidth / referenceWidth;

    const heightScale =
        window.innerHeight / referenceHeight;

    /*
        Use the smaller dimension scale so markers remain proportional
        when the browser window has an unusual aspect ratio.
    */
    return Math.max(
        0.8,
        Math.min(
            1.2,
            Math.min(
                widthScale,
                heightScale
            )
        )
    );
}

/*
    Calculate the final marker radius by combining the magnitude class
    with the responsive screen scale.
*/
function getMarkerRadius(magnitude) {
    return getMagnitudeRadius(magnitude)
        * getScreenScale();
}