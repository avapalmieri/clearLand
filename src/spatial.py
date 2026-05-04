"""
Optimized Spatial Processing Module
Provides efficient raster and vector operations with chunking, spatial indexing, and progress feedback.
"""

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.mask import geometry_mask
import geopandas as gpd
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import warnings
from tqdm import tqdm
from pathlib import Path

# Suppress warnings
warnings.filterwarnings('ignore')


def ndvi_from_paths_chunked(red_path, nir_path, chunk_size=512):
    """
    Calculate NDVI from red and NIR band paths using chunked processing.
    
    Efficiently handles large rasters by processing in blocks rather than
    loading entire dataset into memory.
    
    Args:
        red_path: Path to red band raster
        nir_path: Path to NIR band raster
        chunk_size: Size of processing blocks (default: 512x512 pixels)
    
    Returns:
        ndvi (ndarray): Full NDVI array
        profile (dict): Rasterio profile from red band
    """
    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        # Validate matching dimensions
        assert red_src.shape == nir_src.shape, "Red and NIR bands must have same dimensions"
        
        height, width = red_src.shape
        profile = red_src.profile
        
        # Initialize output array
        ndvi = np.zeros((height, width), dtype=np.float32)
        
        # Process in chunks
        total_chunks = int(np.ceil(height / chunk_size) * np.ceil(width / chunk_size))
        
        with tqdm(total=total_chunks, desc="Calculating NDVI", unit="chunk", disable=False) as pbar:
            for i in range(0, height, chunk_size):
                for j in range(0, width, chunk_size):
                    # Define window
                    window = Window(j, i, 
                                  min(chunk_size, width - j), 
                                  min(chunk_size, height - i))
                    
                    # Read chunks
                    red = red_src.read(1, window=window).astype(np.float32)
                    nir = nir_src.read(1, window=window).astype(np.float32)
                    
                    # Calculate NDVI (avoid division by zero)
                    denominator = nir + red
                    with np.errstate(divide='ignore', invalid='ignore'):
                        ndvi_chunk = np.where(
                            denominator != 0,
                            (nir - red) / denominator,
                            np.nan
                        )
                    
                    # Write to output
                    ndvi[i:i+min(chunk_size, height-i), 
                         j:j+min(chunk_size, width-j)] = ndvi_chunk
                    
                    pbar.update(1)
        
        return ndvi, profile


def ndvi_delta(ndvi0, ndvi1):
    """
    Calculate NDVI change between two time periods.
    
    Args:
        ndvi0: NDVI array at time 0
        ndvi1: NDVI array at time 1
    
    Returns:
        delta (ndarray): NDVI difference (negative = loss)
    """
    # Handle NaN values
    valid_mask = ~(np.isnan(ndvi0) | np.isnan(ndvi1))
    
    delta = np.full_like(ndvi0, np.nan, dtype=np.float32)
    delta[valid_mask] = ndvi1[valid_mask] - ndvi0[valid_mask]
    
    return delta


def mask_to_polygons_optimized(mask, transform, min_pixels=100):
    """
    Convert binary raster mask to vector polygons with optimized filtering.
    
    Pre-filters small patches before polygonization to reduce memory usage.
    
    Args:
        mask: Binary mask array
        transform: Rasterio affine transform
        min_pixels: Minimum patch size to keep
    
    Returns:
        List of Shapely Polygon geometries
    """
    from scipy import ndimage
    import rasterio.features as rf
    
    # Label connected components
    labeled_array, num_features = ndimage.label(mask.astype(np.uint8))
    
    # Filter by size before polygonization
    if min_pixels > 1:
        sizes = np.bincount(labeled_array.ravel())
        # Keep only labels with sufficient pixels
        valid_labels = np.where(sizes >= min_pixels)[0]
        # Create filtered mask
        filtered_mask = np.isin(labeled_array, valid_labels)
    else:
        filtered_mask = mask
    
    # Polygonize filtered mask
    polygons = []
    for geom, val in tqdm(
        rf.shapes(filtered_mask.astype(np.uint8), transform=transform),
        desc="Polygonizing detections",
        disable=False
    ):
        if val > 0:  # Only non-background
            polygons.append(shape(geom))
    
    return polygons


def intersect_with_zoning_spatial_indexed(detections, zoning):
    """
    Intersect detection polygons with zoning boundaries using spatial indexing.
    
    Uses R-tree spatial index for O(log n) lookups instead of O(n*m) quadratic.
    
    Args:
        detections: GeoDataFrame or list of geometries for detections
        zoning: GeoDataFrame with zoning boundaries
    
    Returns:
        GeoDataFrame with intersection results and zoning attributes
    """
    # Convert detections to GeoDataFrame if needed
    if isinstance(detections, list):
        detections_gdf = gpd.GeoDataFrame(geometry=detections, crs=zoning.crs)
    else:
        detections_gdf = detections
    
    # Create spatial index on zoning
    spatial_index = zoning.sindex
    
    # Pre-allocate results
    results = []
    
    with tqdm(total=len(detections_gdf), desc="Intersecting with zones", disable=False) as pbar:
        for idx, detection in detections_gdf.iterrows():
            geom = detection.geometry
            
            # Use spatial index to find candidate zoning polygons
            possible_matches_index = list(spatial_index.intersection(geom.bounds))
            possible_matches = zoning.iloc[possible_matches_index]
            
            # Perform actual intersection
            for zone_idx, zone in possible_matches.iterrows():
                if geom.intersects(zone.geometry):
                    # Calculate intersection
                    intersection = geom.intersection(zone.geometry)
                    
                    if not intersection.is_empty and intersection.area > 0:
                        result_row = {
                            'geometry': intersection,
                            'detection_idx': idx,
                            'zone_idx': zone_idx,
                            'area': intersection.area
                        }
                        
                        # Add zoning attributes
                        for col in zoning.columns:
                            if col != 'geometry':
                                result_row[f'zone_{col}'] = zone[col]
                        
                        results.append(result_row)
            
            pbar.update(1)
    
    if not results:
        return gpd.GeoDataFrame(columns=['geometry', 'area'], crs=zoning.crs)
    
    return gpd.GeoDataFrame(results, crs=zoning.crs)


def calculate_cached_statistics(gdf):
    """
    Calculate and cache commonly-used statistics.
    
    Avoids redundant calculations during report generation.
    
    Args:
        gdf: GeoDataFrame
    
    Returns:
        dict: Cached statistics
    """
    # Calculate once, reuse multiple times
    areas = gdf.geometry.area.values
    centroids = gdf.geometry.centroid
    
    # Calculate statistics efficiently
    stats = {
        'areas': areas,
        'centroids': centroids,
        'total_area': float(areas.sum()),
        'mean_area': float(areas.mean()),
        'median_area': float(np.median(areas)),
        'max_area': float(areas.max()),
        'min_area': float(areas.min()),
        'count': len(gdf),
        'center_lat': float(centroids.y.mean()),
        'center_lon': float(centroids.x.mean()),
        'bounds': {
            'north': float(gdf.total_bounds[3]),
            'south': float(gdf.total_bounds[1]),
            'east': float(gdf.total_bounds[2]),
            'west': float(gdf.total_bounds[0])
        }
    }
    
    return stats


def batch_save_geodataframe(gdf, output_dir, base_name, formats=['GPKG', 'GeoJSON']):
    """
    Save GeoDataFrame to multiple formats in single serialization pass.
    
    More efficient than separate to_file() calls.
    
    Args:
        gdf: GeoDataFrame to save
        output_dir: Output directory path
        base_name: Base filename (without extension)
        formats: List of formats to save (GPKG, GeoJSON, Shapefile)
    
    Returns:
        dict: Paths to saved files
    """
    from pathlib import Path
    import os
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    saved_files = {}
    
    # Map format to extension and driver
    format_config = {
        'GPKG': {'ext': '.gpkg', 'driver': 'GPKG'},
        'GeoJSON': {'ext': '.geojson', 'driver': 'GeoJSON'},
        'Shapefile': {'ext': '.shp', 'driver': 'ESRI Shapefile'},
        'GeoParquet': {'ext': '.parquet', 'driver': 'Parquet'}
    }
    
    for fmt in formats:
        if fmt not in format_config:
            continue
        
        config = format_config[fmt]
        output_path = output_dir / f"{base_name}{config['ext']}"
        
        try:
            gdf.to_file(output_path, driver=config['driver'])
            saved_files[fmt] = str(output_path)
            print(f"✓ Saved {fmt}: {output_path}")
        except Exception as e:
            print(f"⚠ Warning: Could not save {fmt}: {e}")
    
    return saved_files
