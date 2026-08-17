"""
Real Landsat Collection 2 Level-2 NDVI fetch via Microsoft Planetary
Computer's public STAC API (https://planetarycomputer.microsoft.com/).

No account or API key is required to search the catalog and read the
Cloud-Optimized GeoTIFF (COG) assets used here -- this is a public,
unauthenticated STAC endpoint. This replaces the previous
`fetch_landsat_via_usgs` / `generate_historical_ndvi` stand-ins, which
never fetched real pixels and always fell back to synthetic noise.

If pystac-client / planetary-computer aren't installed, or no usable
scene is found, functions here return None. Callers must treat None as
"no real data available" and must NOT fabricate a substitute -- that
was the root cause of inaccurate detections in the previous version.
"""

from datetime import datetime, timedelta

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
COLLECTION = "landsat-c2-l2"

# Landsat Collection 2 Level-2 surface reflectance scale/offset
# (see USGS Landsat Collection 2 Level-2 Science Product Guide)
SR_SCALE = 0.0000275
SR_OFFSET = -0.2

# QA_PIXEL bit flags (Collection 2), used to mask cloud/shadow pixels
# out of the NDVI result rather than let them read as fake vegetation
# loss.
DILATED_CLOUD_BIT = 1 << 1
CLOUD_BIT = 1 << 3
CLOUD_SHADOW_BIT = 1 << 4


def fetch_landsat_ndvi(bounds, date_str, out_width=512, out_height=512, max_cloud_cover=20,
                        search_window_days=30, max_cloud_masked_fraction=0.5):
    """
    Search for a Landsat scene near date_str, read red/NIR/QA_PIXEL
    clipped and reprojected onto a common EPSG:4326 grid matching
    `bounds`/`out_width`/`out_height`, and compute cloud-masked NDVI.

    Returns an (out_height, out_width) float32 NDVI array with
    cloud/shadow pixels set to NaN, or None if no usable real scene was
    found.
    """
    if not _PC_AVAILABLE:
        print(
            "pystac-client / planetary-computer not installed "
            "(pip install pystac-client planetary-computer) -- "
            "cannot fetch real Landsat data."
        )
        return None

    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    start = (target_date - timedelta(days=search_window_days)).strftime('%Y-%m-%d')
    end = (target_date + timedelta(days=search_window_days)).strftime('%Y-%m-%d')

    try:
        catalog = Client.open(PC_STAC_URL)
        search = catalog.search(
            collections=[COLLECTION],
            bbox=list(bounds),
            datetime=f"{start}/{end}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        )
        items = list(search.items())
    except Exception as e:
        print(f"Planetary Computer STAC search failed: {e}")
        return None

    if not items:
        print(f"No Landsat scene found within {search_window_days}d of {date_str} "
              f"with <{max_cloud_cover}% cloud cover.")
        return None

    def _days_away(item):
        item_date = datetime.strptime(item.properties['datetime'][:10], '%Y-%m-%d')
        return abs((item_date - target_date).days)

    items.sort(key=lambda it: (_days_away(it), it.properties.get('eo:cloud_cover', 100)))
    item = pc.sign(items[0])

    try:
        red = _read_band_clip(item.assets['red'].href, bounds, out_width, out_height)
        nir = _read_band_clip(item.assets['nir08'].href, bounds, out_width, out_height)
        qa = _read_band_clip(
            item.assets['qa_pixel'].href, bounds, out_width, out_height, resampling=Resampling.nearest
        )
    except KeyError as e:
        print(f"Landsat item {item.id} is missing expected asset {e}; skipping.")
        return None
    except Exception as e:
        print(f"Failed reading Landsat bands from {item.id}: {e}")
        return None

    red_sr = red.astype(np.float32) * SR_SCALE + SR_OFFSET
    nir_sr = nir.astype(np.float32) * SR_SCALE + SR_OFFSET

    denom = nir_sr + red_sr
    denom[denom == 0] = 1e-4
    ndvi = (nir_sr - red_sr) / denom
    ndvi = np.clip(ndvi, -1.0, 1.0)

    qa_int = qa.astype(np.uint16)
    cloud_mask = (
        (qa_int & CLOUD_BIT).astype(bool)
        | (qa_int & CLOUD_SHADOW_BIT).astype(bool)
        | (qa_int & DILATED_CLOUD_BIT).astype(bool)
    )
    ndvi = np.where(cloud_mask, np.nan, ndvi)

    masked_fraction = np.isnan(ndvi).mean()
    if masked_fraction > max_cloud_masked_fraction:
        print(
            f"Landsat scene {item.id} is {masked_fraction:.0%} cloud/shadow-masked "
            f"over the area of interest; rejecting rather than using a mostly-blank image."
        )
        return None

    return ndvi.astype(np.float32)


def _read_band_clip(href, bounds, out_width, out_height, resampling=Resampling.bilinear):
    """
    Read a single band from a remote COG, reprojected onto a common
    EPSG:4326 grid matching `bounds`/`out_width`/`out_height`.

    This matters: Landsat COGs are natively stored in their scene's UTM
    projection, not EPSG:4326. Reading them with a naive
    lon/lat-as-native-CRS window (as an earlier draft of this would have
    done) silently misaligns pixels. Using a WarpedVRT here guarantees
    the returned array lines up pixel-for-pixel with imagery pulled from
    other sources (e.g. the Sentinel-2 Process API output, which is
    explicitly requested in EPSG:4326 at the same width/height), so NDVI
    delta math between two dates -- even across different sensors --
    compares the same ground locations.
    """
    dst_transform = transform_from_bounds(*bounds, out_width, out_height)
    with rasterio.open(href) as src:
        with WarpedVRT(
            src,
            crs='EPSG:4326',
            transform=dst_transform,
            width=out_width,
            height=out_height,
            resampling=resampling,
        ) as vrt:
            data = vrt.read(1)
    return data
