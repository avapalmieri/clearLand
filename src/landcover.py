"""
Land-cover reference data via Microsoft Planetary Computer's ESA
WorldCover collection (public, unauthenticated, 10m global land-cover
classification: https://esa-worldcover.org/).

Used to filter false positives out of NDVI-based change detection. A
simple two-date NDVI delta can't tell "someone illegally cleared this
land" apart from "this farm field was harvested, rotated to a different
crop, or left fallow between the two dates" -- both produce an identical
drop in vegetation index, but only one is actually a violation. Cropping
out pixels ESA WorldCover classifies as cropland removes that entire
class of false positive rather than guessing at it.
"""

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.vrt import WarpedVRT

try:
    from pystac_client import Client
    import planetary_computer as pc
    _PC_AVAILABLE = True
except ImportError:
    _PC_AVAILABLE = False

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "esa-worldcover"

# ESA WorldCover class codes (v100/v200 share the same legend):
# https://esa-worldcover.org/en/data-access -- "Cropland" = 40.
CROPLAND_CLASS = 40


def fetch_cropland_mask(bounds, out_width=512, out_height=512):
    """
    Return a boolean (out_height, out_width) array, True where ESA
    WorldCover classifies the pixel as cropland, reprojected onto the
    same EPSG:4326 grid used for the NDVI imagery so it lines up
    pixel-for-pixel.

    Returns None if the lookup fails for any reason (package missing,
    no tile covers this area, network error). Callers must treat None
    as "unknown" and skip filtering rather than assume everything is
    (or isn't) cropland -- this is an ancillary accuracy improvement,
    not something that should block an otherwise-successful analysis if
    this one auxiliary data source has a bad day.
    """
    if not _PC_AVAILABLE:
        print(
            "pystac-client / planetary-computer not installed -- "
            "skipping cropland false-positive filter."
        )
        return None

    try:
        catalog = Client.open(PC_STAC_URL)
        search = catalog.search(collections=[COLLECTION], bbox=list(bounds))
        items = list(search.items())
    except Exception as e:
        print(f"WorldCover STAC search failed: {e}")
        return None

    if not items:
        print("No ESA WorldCover tile found for this area -- skipping cropland filter.")
        return None

    # Prefer the most recent map version if more than one tile matches.
    items.sort(key=lambda it: it.properties.get('start_datetime', ''), reverse=True)
    item = pc.sign(items[0])

    try:
        href = item.assets['map'].href
    except KeyError:
        print("WorldCover item is missing the expected 'map' asset -- skipping cropland filter.")
        return None

    dst_transform = transform_from_bounds(*bounds, out_width, out_height)
    try:
        with rasterio.open(href) as src:
            with WarpedVRT(
                src,
                crs='EPSG:4326',
                transform=dst_transform,
                width=out_width,
                height=out_height,
                # Categorical class codes -- never interpolate between them.
                resampling=Resampling.nearest,
            ) as vrt:
                data = vrt.read(1)
    except Exception as e:
        print(f"Failed reading ESA WorldCover data: {e}")
        return None

    return data == CROPLAND_CLASS
