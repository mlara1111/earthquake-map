/*
 * Earthquake visual configuration.
 *
 * This file contains only cartographic styling and visual helper functions.
 * Application behavior, API communication, and user interaction belong in map.js.
 */

/*
 * Define discrete magnitude classes for earthquake marker size.
 *
 * Larger magnitudes receive progressively larger markers.
 * The classes intentionally remain discrete so the visual scale is
 * predictable and easy to interpret.
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
    { max: Infinity, radius: 26 },
];


/*
 * Define the orange magnitude color scale.
 *
 * Lower magnitudes use lighter orange and higher magnitudes use
 * progressively darker orange.
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
    { max: Infinity, color: "#a63f00" },
];


/*
 * Default earthquake marker opacity.
 */
const DEFAULT_MARKER_OPACITY = 0.35;


/*
 * Active earthquake marker opacity.
 *
 * An active marker is shown when its popup is open or when it is selected
 * from the earthquake list.
 */
const ACTIVE_MARKER_OPACITY = 0.80;


/*
 * Default earthquake marker border width.
 */
const DEFAULT_MARKER_WEIGHT = 2;


/*
 * Active earthquake marker border width.
 */
const ACTIVE_MARKER_WEIGHT = 2.5;


/*
 * Minimum cluster radius.
 */
const CLUSTER_MIN_RADIUS = 11;


/*
 * Maximum distance in pixels within which markers can form a cluster.
 */
const CLUSTER_MAX_RADIUS = 60;


/*
 * Disable clustering from this zoom level onwards.
 *
 * At higher zoom levels individual earthquake markers are shown directly.
 */
const CLUSTER_DISABLE_ZOOM = 10;


/*
 * Default cluster opacity.
 */
const CLUSTER_DEFAULT_OPACITY = 0.75;


/*
 * Active cluster opacity.
 */
const CLUSTER_ACTIVE_OPACITY = 0.90;


/*
 * Determine the magnitude class for a numeric magnitude.
 */
function getMagnitudeClass(magnitude) {
    const numericMagnitude = Number(magnitude);

    /*
     * Missing or invalid magnitudes use the smallest visual class.
     */
    if (!Number.isFinite(numericMagnitude)) {
        return 0;
    }

    for (let index = 0; index < MAGNITUDE_RADIUS_CLASSES.length; index++) {
        if (numericMagnitude < MAGNITUDE_RADIUS_CLASSES[index].max) {
            return index;
        }
    }

    return MAGNITUDE_RADIUS_CLASSES.length - 1;
}


/*
 * Return the base marker radius for a magnitude.
 */
function getMagnitudeRadius(magnitude) {
    const magnitudeClass = getMagnitudeClass(magnitude);

    return MAGNITUDE_RADIUS_CLASSES[magnitudeClass].radius;
}


/*
 * Return the configured color for a magnitude.
 */
function getMagnitudeColor(magnitude) {
    const magnitudeClass = getMagnitudeClass(magnitude);

    return MAGNITUDE_COLOR_CLASSES[magnitudeClass].color;
}


/*
 * Calculate a responsive screen scale.
 *
 * The reference viewport corresponds approximately to a standard desktop
 * browser window. The result is deliberately bounded so markers do not
 * become excessively small or large.
 */
function getScreenScale() {
    const referenceWidth = 1366;
    const referenceHeight = 768;

    const widthScale = window.innerWidth / referenceWidth;
    const heightScale = window.innerHeight / referenceHeight;

    return Math.max(
        0.8,
        Math.min(
            1.2,
            Math.min(widthScale, heightScale)
        )
    );
}


/*
 * Return the final marker radius after applying the responsive scale.
 */
function getMarkerRadius(magnitude) {
    return getMagnitudeRadius(magnitude) * getScreenScale();
}


/*
 * Convert a hexadecimal color to an rgba() CSS value.
 */
function hexToRgba(hexColor, opacity) {
    const normalized = hexColor.replace("#", "");

    const red = parseInt(normalized.substring(0, 2), 16);
    const green = parseInt(normalized.substring(2, 4), 16);
    const blue = parseInt(normalized.substring(4, 6), 16);

    return `rgba(${red}, ${green}, ${blue}, ${opacity})`;
}


/*
 * Darken a hexadecimal color by the requested factor.
 */
function darkenHexColor(hexColor, factor) {
    const normalized = hexColor.replace("#", "");

    const red = parseInt(normalized.substring(0, 2), 16);
    const green = parseInt(normalized.substring(2, 4), 16);
    const blue = parseInt(normalized.substring(4, 6), 16);

    const darken = (value) => Math.round(value * (1 - factor));

    return `#${[red, green, blue]
        .map((value) => darken(value).toString(16).padStart(2, "0"))
        .join("")}`;
}