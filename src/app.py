"""
DEPRECATED PROTOTYPE -- DO NOT RUN THIS FILE.

This is an early draft of the ClearLand backend. It generates 100%
synthetic imagery (np.random noise standing in for red/NIR reflectance)
with fabricated "deforestation" blobs added on every single run, and it
has no real Sentinel-2/Landsat fetch at all. It predates the real,
multi-source detection pipeline in the repo-root app.py and is not wired
to templates/index.html -- its JSON response is missing the
`data_sources` key the frontend reads, so running this instead of the
root app.py would both look broken and, worse, produce entirely fake
"violations" that look like real detections.

Left in place unmodified below so nothing is deleted without your
say-so, but recommend removing this file (or folding anything still
useful into the root app.py) to stop it from being run by accident.

---
ClearLand Flask Web Application
Environmental violation detection with user-specified locations
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


@app.route('/')
def home():
    """Main page with location input form."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """Run detection on specified location."""
    try:
        data = request.get_json()
        
        location = data.get('location', '')
        lat = data.get('lat')
        lon = data.get('lon')
        start_date = data.get('start_date', '2020-01-01')
        end_date = data.get('end_date', '2024-01-01')
        
        # For now, use synthetic data generation
        # Later we'll integrate real Sentinel-2 API
        results = run_synthetic_detection(lat, lon, start_date, end_date)
        
        return jsonify({
            'success': True,
            'message': f'Analysis complete for {location}',
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def run_synthetic_detection(lat, lon, start_date, end_date):
    """
    Generate synthetic detection results with zoning violation check.
    Uses PAD-US protected areas data for real violation detection.
    """
    import numpy as np
    from rasterio.transform import from_bounds
    import rasterio
    import geopandas as gpd
    from shapely.geometry import box, Point
    import requests
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from src.spatial import ndvi_from_paths, ndvi_delta, mask_to_polygons
    
    # Simple zoning intersection
    def simple_intersect(polygons, zoning_gdf):
        detections = gpd.GeoDataFrame(geometry=polygons, crs=zoning_gdf.crs)
        result = gpd.overlay(detections, zoning_gdf, how='intersection')
        if len(result) == 0:
            detections['zone'] = 'Unknown'
            detections['is_violation'] = False
            return detections
        result['area'] = result.geometry.area
        if 'zone' in result.columns:
            result['zoning_type'] = result['zone']
        return result
    
    # Fetch PAD-US protected areas from ArcGIS REST API
    def get_protected_areas(bounds):
        """Fetch protected areas from PAD-US via ArcGIS REST API."""
        try:
            # PAD-US Feature Service
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
                    gdf = gpd.GeoDataFrame.from_features(data['features'], crs='EPSG:4326')
                    gdf['zone'] = 'Protected Area'
                    gdf['is_protected'] = True
                    return gdf
        except Exception as e:
            print(f"Could not fetch PAD-US data: {e}")
        
        return None
    
    # Create bounds around the specified location
    buffer = 0.05
    bounds = (lon - buffer, lat - buffer, lon + buffer, lat + buffer)
    
    height, width = 500, 500
    transform = from_bounds(*bounds, width, height)
    
    profile = {
        'driver': 'GTiff',
        'dtype': 'float32',
        'width': width,
        'height': height,
        'count': 1,
        'crs': 'EPSG:4326',
        'transform': transform,
    }
    
    # Generate synthetic imagery
    os.makedirs('temp_data', exist_ok=True)
    
    # Time 0: Healthy vegetation
    red_t0 = np.random.uniform(0.03, 0.08, (height, width)).astype(np.float32)
    nir_t0 = np.random.uniform(0.40, 0.60, (height, width)).astype(np.float32)
    
    # Time 1: With deforestation patches
    red_t1 = np.random.uniform(0.03, 0.08, (height, width)).astype(np.float32)
    nir_t1 = np.random.uniform(0.40, 0.60, (height, width)).astype(np.float32)
    
    # Add random deforestation patches with NATURAL BLOB SHAPES
    np.random.seed(int(abs(lat * 1000 + lon * 1000)) % 2**31)
    num_patches = np.random.randint(4, 10)
    
    def create_blob(height, width, cy, cx, size):
        """Create a natural-looking blob using noise."""
        y, x = np.ogrid[:height, :width]
        dist = np.sqrt((y - cy)**2 + (x - cx)**2)
        noise = np.random.uniform(0.7, 1.3, (height, width))
        threshold = size * noise
        return dist < threshold
    
    for _ in range(num_patches):
        cy = np.random.randint(80, height - 80)
        cx = np.random.randint(80, width - 80)
        size = np.random.randint(20, 50)
        
        blob_mask = create_blob(height, width, cy, cx, size)
        
        red_t1[blob_mask] = np.random.uniform(0.15, 0.28, blob_mask.sum())
        nir_t1[blob_mask] = np.random.uniform(0.12, 0.22, blob_mask.sum())
    
    # Save temporary rasters
    with rasterio.open('temp_data/red_t0.tif', 'w', **profile) as dst:
        dst.write(red_t0, 1)
    with rasterio.open('temp_data/nir_t0.tif', 'w', **profile) as dst:
        dst.write(nir_t0, 1)
    with rasterio.open('temp_data/red_t1.tif', 'w', **profile) as dst:
        dst.write(red_t1, 1)
    with rasterio.open('temp_data/nir_t1.tif', 'w', **profile) as dst:
        dst.write(nir_t1, 1)
    
    # Run detection
    ndvi0, prof0 = ndvi_from_paths('temp_data/red_t0.tif', 'temp_data/nir_t0.tif')
    ndvi1, prof1 = ndvi_from_paths('temp_data/red_t1.tif', 'temp_data/nir_t1.tif')
    
    delta = ndvi_delta(ndvi0, ndvi1)
    loss_mask = delta < -0.25
    
    polys = mask_to_polygons(loss_mask, transform=prof0['transform'], min_pixels=50)
    
    if len(polys) > 0:
        gdf = gpd.GeoDataFrame(geometry=polys, crs='EPSG:4326')
        gdf['area'] = gdf.geometry.area
        gdf['detection_type'] = 'vegetation_loss'
        gdf['is_violation'] = False
        
        # Check against PAD-US protected areas
        protected_areas = get_protected_areas(bounds)
        
        if protected_areas is not None and len(protected_areas) > 0:
            # Check which detections intersect protected areas
            for idx, detection in gdf.iterrows():
                for _, protected in protected_areas.iterrows():
                    if detection.geometry.intersects(protected.geometry):
                        gdf.at[idx, 'is_violation'] = True
                        gdf.at[idx, 'detection_type'] = 'zoning_violation'
                        gdf.at[idx, 'violation_reason'] = f"Activity in {protected.get('Mang_Name', 'Protected Area')}"
                        break
        
        # Save results
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], 'violations.geojson')
        gdf.to_file(output_path, driver='GeoJSON')
        
        with open(output_path, 'r') as f:
            geojson_data = json.load(f)
        
        # Stats
        total = len(gdf)
        violations = len(gdf[gdf['is_violation'] == True])
        veg_loss = total - violations
        
        return {
            'total_detections': total,
            'vegetation_loss': veg_loss,
            'zoning_violations': violations,
            'geojson': geojson_data,
            'bounds': bounds,
            'center': [lat, lon],
            'has_protected_areas': protected_areas is not None and len(protected_areas) > 0
        }
    else:
        return {
            'total_detections': 0,
            'vegetation_loss': 0,
            'zoning_violations': 0,
            'geojson': {'type': 'FeatureCollection', 'features': []},
            'bounds': bounds,
            'center': [lat, lon],
            'has_protected_areas': False
        }


@app.route('/results')
def results():
    """Display results page."""
    return render_template('results.html')


@app.route('/download/<filename>')
def download(filename):
    """Download output files."""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
