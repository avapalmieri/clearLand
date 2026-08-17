"""
Spatial analysis utilities for ClearLand.
NDVI calculation and change detection.
"""

import numpy as np
import rasterio
from shapely.geometry import shape
from rasterio.features import shapes
from scipy import ndimage


def ndvi_from_paths(red_path, nir_path):
    """Calculate NDVI from red and NIR band files."""
    with rasterio.open(red_path) as red_src:
        red = red_src.read(1).astype(np.float32)
        profile = red_src.profile

    with rasterio.open(nir_path) as nir_src:
        nir = nir_src.read(1).astype(np.float32)

    # Avoid division by zero
    denominator = nir + red
    denominator[denominator == 0] = 0.0001

    ndvi = (nir - red) / denominator
    ndvi = np.clip(ndvi, -1.0, 1.0)

    return ndvi, profile


def ndvi_delta(ndvi_before, ndvi_after):
    """Calculate NDVI change between two time periods."""
    return ndvi_after - ndvi_before


def mask_to_polygons(mask, transform, min_pixels=50):
    """
    Convert a binary mask to polygons, keeping only connected components
    with at least `min_pixels` raster pixels.

    NOTE: min_pixels is evaluated by counting connected pixels directly
    (via scipy.ndimage.label), not by comparing polygon area in the
    raster's native units. The previous implementation filtered by
    `polygon.area > min_pixels * pixel_width**2` on geometries in
    EPSG:4326 (degrees) -- pixel width in degrees varies by location and
    isn't a real area unit, so that threshold was inconsistent across
    latitudes and meaningless as a physical size cutoff. Counting pixels
    directly is resolution/latitude independent and matches what
    `min_pixels` actually means.
    """
    mask = mask.astype(np.uint8)

    labeled, num_features = ndimage.label(mask)
    if num_features == 0:
        return []

    counts = np.bincount(labeled.ravel())
    keep_labels = [lbl for lbl in range(1, num_features + 1) if counts[lbl] >= min_pixels]
    if not keep_labels:
        return []

    filtered = np.isin(labeled, keep_labels).astype(np.uint8)

    polygons = []
    for geom, value in shapes(filtered, transform=transform):
        if value == 1:
            polygons.append(shape(geom))

    return polygons


def filter_cropland_blobs(mask, cropland_mask, min_pixels=50, cropland_fraction_threshold=0.5):
    """
    Given a raw NDVI-loss mask and a same-shape boolean cropland mask
    (see src/landcover.py), drop entire connected blobs that are
    majority-cropland by pixel count.

    This operates blob-by-blob rather than pixel-by-pixel: a blob that's
    mostly real land clearing but clips the edge of a field keeps its
    full natural shape, instead of getting notched/fragmented by
    removing individual cropland pixels from inside it. A blob is only
    dropped if the *majority* of its pixels fall on cropland -- the
    threshold that "this is farmland, not a violation" is a real
    judgment call, and this defaults to a plain majority rather than
    something more aggressive.

    A blob under min_pixels is dropped silently, same as always -- too
    small to be meaningful regardless of land cover, and NOT counted as
    "excluded for being agricultural" since that wasn't why it was
    dropped.

    If cropland_mask is None (the WorldCover lookup failed or the
    optional dependency isn't installed), no filtering happens --
    everything above min_pixels passes through unchanged.

    Returns (kept_mask, excluded_agricultural_count).
    """
    mask_u8 = mask.astype(np.uint8)
    labeled, num_features = ndimage.label(mask_u8)
    if num_features == 0:
        return np.zeros_like(mask, dtype=bool), 0

    kept = np.zeros_like(mask, dtype=bool)
    excluded_agricultural = 0

    for lbl in range(1, num_features + 1):
        blob = labeled == lbl
        count = int(blob.sum())
        if count < min_pixels:
            continue

        if cropland_mask is not None:
            cropland_fraction = float(cropland_mask[blob].mean())
            if cropland_fraction > cropland_fraction_threshold:
                excluded_agricultural += 1
                continue

        kept |= blob

    return kept, excluded_agricultural


def polygon_area_hectares(gdf):
    """
    Compute polygon areas in hectares by reprojecting to an appropriate
    local UTM CRS first. Areas computed directly on EPSG:4326 (lat/lon)
    geometries are in degrees^2, which is not a real-world area unit and
    is not comparable across latitudes -- this fixes that.
    """
    if len(gdf) == 0:
        return gdf.geometry.area  # empty series, nothing to reproject

    utm_crs = gdf.estimate_utm_crs()
    return gdf.to_crs(utm_crs).geometry.area / 10000.0
