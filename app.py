"""
ClearLand Flask Web Application
Environmental violation detection with multiple satellite data sources:
- Sentinel-2 (2015-present) - 10m resolution, via Copernicus Data Space
- Landsat 8/9, 7, 5 (1984-present) - 30m resolution, via Microsoft
  Planetary Computer's public STAC catalog

REAL DATA ONLY. Earlier versions of this app silently fell back to
np.random-generated "synthetic" NDVI and then unconditionally injected
fabricated deforestation blobs into every result, regardless of whether
real imagery had been fetched -- meaning every analysis reported fake
violations no matter what. That fallback and blob-injection code has
been removed. If real imagery can't be obtained for a requested date,
`run_detection` now returns an explicit "no data available" result
instead of making something up.
"""

import io
import json
import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Sentinel Hub / Copernicus Data Space credentials.
# Set these in the environment (e.g. a .env file, see .env.example) --
# do NOT hardcode them here. Create an OAuth client at
# https://shapps.dataspace.copernicus.eu/dashboard/
SENTINELHUB_CLIENT_ID = os.environ.get('SENTINELHUB_CLIENT_ID')
SENTINELHUB_CLIENT_SECRET = os.environ.get('SENTINELHUB_CLIENT_SECRET')

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('temp_data', exist_ok=True)


class ImageFetchError(Exception):
    """Raised when real satellite imagery cannot be obtained for a date.
    Callers must surface this to the user, not substitute fake data."""


def get_data_source_for_date(date_str):
    """Determine best satellite data source based on date."""
    date = datetime.strptime(date_str, '%Y-%m-%d')

    if date >= datetime(2015, 6, 23):
        return 'sentinel-2'
    elif date >= datetime(2013, 2, 11):
        return 'landsat-8'
    elif date >= datetime(1999, 4, 15):
        return 'landsat-7'
    elif date >= datetime(1984, 3, 1):
        return 'landsat-5'
    else:
        return 'unavailable'


def get_sentinelhub_token():
    """Get OAuth token for Sentinel Hub / Copernicus Data Space API."""
    if not SENTINELHUB_CLIENT_ID or not SENTINELHUB_CLIENT_SECRET:
        print(
            "SENTINELHUB_CLIENT_ID / SENTINELHUB_CLIENT_SECRET are not set "
            "(see .env.example) -- cannot fetch real Sentinel-2 data."
        )
        return None
    try:
        response = requests.post(
            'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': SENTINELHUB_CLIENT_ID,
                'client_secret': SENTINELHUB_CLIENT_SECRET
            },
            timeout=15
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Sentinel Hub auth failed: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"Failed to get Sentinel Hub token: {e}")
    return None


def fetch_sentinel_ndvi(bounds, date_str, token, out_size=512):
    """Fetch real NDVI from Sentinel-2 via Copernicus Data Space Process API."""
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        from_date = (target_date - timedelta(days=15)).strftime('%Y-%m-%d')
        to_date = (target_date + timedelta(days=15)).strftime('%Y-%m-%d')

        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["B04", "B08"],
                output: { bands: 1, sampleType: "FLOAT32" }
            };
        }
        function evaluatePixel(sample) {
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            return [ndvi];
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "bbox": list(bounds),
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": f"{from_date}T00:00:00Z", "to": f"{to_date}T23:59:59Z"},
                        "maxCloudCoverage": 20,
                        "mosaickingOrder": "leastCC"
                    }
                }]
            },
            "output": {
                "width": out_size,
                "height": out_size,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
            },
            "evalscript": evalscript
        }

        response = requests.post(
            'https://sh.dataspace.copernicus.eu/api/v1/process',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            return response.content
        else:
            print(f"Sentinel API error: {response.status_code} - {response.text[:200]}")

    except Exception as e:
        print(f"Sentinel fetch error: {e}")
    return None


def fetch_ndvi_for_date(bounds, date_str, out_size=512):
    """
    Fetch REAL NDVI imagery for a date, using whichever data source
    actually covers it. Raises ImageFetchError (never returns fabricated
    data) if no real imagery can be obtained.

    Returns (ndvi_array, source_label).
    """
    import rasterio

    source = get_data_source_for_date(date_str)

    if source == 'sentinel-2':
        token = get_sentinelhub_token()
        if not token:
            raise ImageFetchError(
                f"Could not authenticate with Copernicus Data Space for {date_str} "
                f"(check SENTINELHUB_CLIENT_ID/SECRET)."
            )
        data = fetch_sentinel_ndvi(bounds, date_str, token, out_size=out_size)
        if data is None:
            raise ImageFetchError(
                f"No cloud-free Sentinel-2 scene found within 15 days of {date_str} "
                f"(cloud coverage threshold: 20%)."
            )
        with rasterio.open(io.BytesIO(data)) as src:
            return src.read(1), 'sentinel-2'

    elif source.startswith('landsat'):
        from src.landsat import fetch_landsat_ndvi
        ndvi = fetch_landsat_ndvi(bounds, date_str, out_size=out_size)
        if ndvi is None:
            raise ImageFetchError(
                f"No usable Landsat scene found within 30 days of {date_str} "
                f"(cloud coverage threshold: 20%, or scene was mostly cloud-masked)."
            )
        return ndvi, source

    else:
        raise ImageFetchError(
            f"{date_str} is outside the supported data range (1984-03-01 to present)."
        )


def run_detection(lat, lon, start_date, end_date):
    """
    Detect vegetation loss using real satellite imagery only. If real
    imagery isn't available for either date, returns
    `data_available: False` with a per-date explanation instead of
    fabricating a result.
    """
    import numpy as np
    import geopandas as gpd
    from rasterio.transform import from_bounds

    from src.spatial import mask_to_polygons, polygon_area_hectares

    buffer = 0.05
    bounds = (lon - buffer, lat - buffer, lon + buffer, lat + buffer)
    out_size = 512
    transform = from_bounds(*bounds, out_size, out_size)

    fetch_errors = {}
    ndvi_start = source_start = None
    ndvi_end = source_end = None

    try:
        ndvi_start, source_start = fetch_ndvi_for_date(bounds, start_date, out_size=out_size)
    except ImageFetchError as e:
        fetch_errors['start'] = str(e)

    try:
        ndvi_end, source_end = fetch_ndvi_for_date(bounds, end_date, out_size=out_size)
    except ImageFetchError as e:
        fetch_errors['end'] = str(e)

    if fetch_errors:
        return {
            'data_available': False,
            'errors': fetch_errors,
            'total_detections': 0,
            'vegetation_loss': 0,
            'zoning_violations': 0,
            'geojson': {'type': 'FeatureCollection', 'features': []},
            'bounds': bounds,
            'center': [lat, lon],
            'has_protected_areas': False,
            'data_sources': {
                'start': source_start or 'unavailable',
                'end': source_end or 'unavailable'
            }
        }

    # Persist rasters for debugging/inspection.
    import rasterio
    profile = {
        'driver': 'GTiff', 'dtype': 'float32', 'width': out_size, 'height': out_size,
        'count': 1, 'crs': 'EPSG:4326', 'transform': transform,
    }
    with rasterio.open('temp_data/ndvi_start.tif', 'w', **profile) as dst:
        dst.write(np.nan_to_num(ndvi_start, nan=-2.0).astype('float32'), 1)
    with rasterio.open('temp_data/ndvi_end.tif', 'w', **profile) as dst:
        dst.write(np.nan_to_num(ndvi_end, nan=-2.0).astype('float32'), 1)

    delta = ndvi_end - ndvi_start
    valid = ~(np.isnan(delta))
    loss_mask = np.where(valid, delta < -0.25, False)

    polys = mask_to_polygons(loss_mask, transform=transform, min_pixels=50)

    protected_areas = get_protected_areas(bounds)

    if len(polys) > 0:
        gdf = gpd.GeoDataFrame(geometry=polys, crs='EPSG:4326')
        gdf['area_ha'] = polygon_area_hectares(gdf)
        gdf['detection_type'] = 'vegetation_loss'
        gdf['is_violation'] = False

        if protected_areas is not None and len(protected_areas) > 0:
            for idx, detection in gdf.iterrows():
                for _, protected in protected_areas.iterrows():
                    if detection.geometry.intersects(protected.geometry):
                        gdf.at[idx, 'is_violation'] = True
                        gdf.at[idx, 'detection_type'] = 'zoning_violation'
                        gdf.at[idx, 'violation_reason'] = f"Activity in {protected.get('Mang_Name', 'Protected Area')}"
                        break

        output_path = os.path.join(app.config['OUTPUT_FOLDER'], 'violations.geojson')
        gdf.to_file(output_path, driver='GeoJSON')

        with open(output_path, 'r') as f:
            geojson_data = json.load(f)

        total = len(gdf)
        violations = len(gdf[gdf['is_violation'] == True])
        veg_loss = total - violations

        return {
            'data_available': True,
            'total_detections': total,
            'vegetation_loss': veg_loss,
            'zoning_violations': violations,
            'geojson': geojson_data,
            'bounds': bounds,
            'center': [lat, lon],
            'has_protected_areas': protected_areas is not None and len(protected_areas) > 0,
            'data_sources': {'start': source_start, 'end': source_end}
        }
    else:
        return {
            'data_available': True,
            'total_detections': 0,
            'vegetation_loss': 0,
            'zoning_violations': 0,
            'geojson': {'type': 'FeatureCollection', 'features': []},
            'bounds': bounds,
            'center': [lat, lon],
            'has_protected_areas': False,
            'data_sources': {'start': source_start, 'end': source_end}
        }


def get_protected_areas(bounds):
    """
    Fetch protected areas from PAD-US via ArcGIS REST API.

    NOTE: PAD-US only covers the United States. Outside the US this will
    always return None, and every detection will read
    `is_violation: False` regardless of whether it's actually inside a
    protected/zoned area -- there's no false positive here, but there
    IS a silent false negative for any non-US location. If you need
    zoning checks outside the US, this needs a different data source
    (e.g. WDPA for global protected areas).
    """
    try:
        url = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS3_0Fee/FeatureServer/0/query"

        params = {
            'where': '1=1',
            'geometry': f'{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}',
            'geometryType': 'esriGeometryEnvelope',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': 'Mang_Name,Mang_Type,Des_Tp,Loc_Nm',
            'returnGeometry': 'true',
            'f': 'geojson',
            'outSR': '4326'
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                import geopandas as gpd
                gdf = gpd.GeoDataFrame.from_features(data['features'], crs='EPSG:4326')
                gdf['zone'] = 'Protected Area'
                gdf['is_protected'] = True
                return gdf
    except Exception as e:
        print(f"Could not fetch PAD-US data: {e}")

    return None


@app.route('/')
def home():
    """Main page with location input form."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """Run detection on specified location using real satellite data only."""
    try:
        data = request.get_json(force=True) or {}

        location = data.get('location', '')
        lat = data.get('lat')
        lon = data.get('lon')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if lat is None or lon is None:
            return jsonify({'success': False, 'error': 'lat and lon are required'}), 400
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'lat and lon must be numbers'}), 400
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return jsonify({'success': False, 'error': 'lat/lon out of valid range'}), 400
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'start_date and end_date are required'}), 400

        results = run_detection(lat, lon, start_date, end_date)

        if results.get('data_available', True):
            message = f'Analysis complete for {location}'
        else:
            message = f'Could not complete analysis for {location}: real satellite imagery unavailable for one or both dates'

        return jsonify({
            'success': True,
            'message': message,
            'results': results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/data-availability', methods=['POST'])
def check_data_availability():
    """
    Check which satellite data source theoretically covers a date range.
    This reflects source coverage windows, not a live scene-availability
    check -- an actual scene still has to be found by /analyze.
    """
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        start_source = get_data_source_for_date(start_date)
        end_source = get_data_source_for_date(end_date)

        return jsonify({
            'success': True,
            'availability': {
                'start_date': {
                    'date': start_date,
                    'source': start_source,
                    'resolution': '10m' if start_source == 'sentinel-2' else '30m',
                    'available': start_source != 'unavailable'
                },
                'end_date': {
                    'date': end_date,
                    'source': end_source,
                    'resolution': '10m' if end_source == 'sentinel-2' else '30m',
                    'available': end_source != 'unavailable'
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/<filename>')
def download(filename):
    """Download output files."""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    if not SENTINELHUB_CLIENT_ID or not SENTINELHUB_CLIENT_SECRET:
        print(
            "WARNING: SENTINELHUB_CLIENT_ID/SECRET are not set. Sentinel-2 dates "
            "(2015-present) will fail to fetch real data until these are configured "
            "in your environment or a .env file -- see .env.example."
        )
    app.run(debug=True, port=5000)
