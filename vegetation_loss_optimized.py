"""
NDVI Vegetation Loss Detection - Optimized Version
Main detection script with chunked raster processing, spatial indexing, and progress feedback.
"""

import geopandas as gpd
import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.spatial_optimized import (
    ndvi_from_paths_chunked, 
    ndvi_delta,
    mask_to_polygons_optimized,
    intersect_with_zoning_spatial_indexed,
    calculate_cached_statistics,
    batch_save_geodataframe
)


def generate_summary_report_optimized(gdf, stats_cache, output_dir, config):
    """
    Generate summary statistics and report using cached statistics.
    
    Uses pre-calculated stats instead of recalculating geometry properties.
    
    Args:
        gdf: GeoDataFrame with detections
        stats_cache: Pre-calculated statistics dictionary
        output_dir: Output directory
        config: Configuration dictionary
    """
    
    report = {
        "analysis_date": datetime.now().isoformat(),
        "configuration": {
            "threshold": config.get("threshold"),
            "min_pixels": config.get("min_pixels"),
            "time_period": {
                "t0": config.get("red_t0"),
                "t1": config.get("red_t1")
            }
        },
        "results": {
            "total_polygons": stats_cache['count'],
            "total_area_sq_units": stats_cache['total_area'],
            "mean_area": stats_cache['mean_area'],
            "median_area": stats_cache['median_area'],
            "max_area": stats_cache['max_area'],
            "min_area": stats_cache['min_area'],
        }
    }
    
    # Add zoning statistics if available
    if 'zone_zoning_type' in gdf.columns or 'zone_zone' in gdf.columns:
        zone_col = 'zone_zoning_type' if 'zone_zoning_type' in gdf.columns else 'zone_zone'
        zone_counts = gdf[zone_col].value_counts().to_dict()
        report["results"]["violations_by_zone"] = zone_counts
    
    # Use cached map bounds
    report["map_bounds"] = {
        "center_lat": stats_cache['center_lat'],
        "center_lon": stats_cache['center_lon'],
        "bounds": stats_cache['bounds']
    }
    
    # Save JSON report
    report_path = os.path.join(output_dir, "summary_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print human-readable summary
    print("\n" + "="*60)
    print("VEGETATION LOSS DETECTION SUMMARY")
    print("="*60)
    print(f"Analysis Date: {report['analysis_date']}")
    print(f"NDVI Threshold: {config.get('threshold')}")
    print(f"Minimum Patch Size: {config.get('min_pixels')} pixels")
    print("\nRESULTS:")
    print(f"  Total Areas Detected: {report['results']['total_polygons']}")
    print(f"  Total Area: {report['results']['total_area_sq_units']:.2f} sq units")
    print(f"  Mean Area: {report['results']['mean_area']:.2f} sq units")
    print(f"  Median Area: {report['results']['median_area']:.2f} sq units")
    print(f"  Largest Patch: {report['results']['max_area']:.2f} sq units")
    
    if 'violations_by_zone' in report['results']:
        print("\nVIOLATIONS BY ZONING TYPE:")
        for zone, count in sorted(report['results']['violations_by_zone'].items(), 
                                 key=lambda x: x[1], reverse=True):
            print(f"  {zone}: {count}")
    
    print(f"\nDetailed report saved: {report_path}")
    print("="*60 + "\n")
    
    return report


def detect_vegetation_loss_optimized(red_t0, nir_t0, red_t1, nir_t1, 
                                     zoning_path=None, threshold=-0.25, 
                                     min_pixels=100, output_dir="outputs",
                                     generate_report=True, chunk_size=512):
    """
    Detect vegetation loss between two time periods using optimized NDVI change detection.
    
    Uses chunked raster processing, spatial indexing, and efficient file I/O.
    
    Args:
        red_t0, nir_t0: Paths to time 0 red and NIR bands
        red_t1, nir_t1: Paths to time 1 red and NIR bands
        zoning_path: Optional path to zoning shapefile/gpkg
        threshold: NDVI delta threshold (negative = loss)
        min_pixels: Minimum patch size to keep
        output_dir: Directory for output files
        generate_report: Whether to generate summary statistics
        chunk_size: Size of raster chunks for processing (default: 512x512)
    
    Returns:
        GeoDataFrame of detected polygons, statistics dictionary
    """
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*60)
    print("VEGETATION LOSS DETECTION - OPTIMIZED")
    print("="*60)
    
    # 1) Calculate NDVI for both time periods (chunked)
    print("\n[1/6] Calculating NDVI for time 0 (chunked)...")
    ndvi0, prof0 = ndvi_from_paths_chunked(red_t0, nir_t0, chunk_size=chunk_size)
    
    print("[2/6] Calculating NDVI for time 1 (chunked)...")
    ndvi1, prof1 = ndvi_from_paths_chunked(red_t1, nir_t1, chunk_size=chunk_size)
    
    # 2) Calculate change (negative = vegetation loss)
    print("\n[3/6] Computing NDVI delta...")
    delta = ndvi_delta(ndvi0, ndvi1)
    
    # 3) Create binary mask of significant loss
    loss_mask = (delta < threshold)
    loss_pixels = np.isfinite(loss_mask).sum()  # Count valid pixels
    actual_losses = loss_mask.sum()
    print(f"  Detected {actual_losses:,} pixels with NDVI < {threshold}")
    print(f"  Out of {loss_pixels:,} valid pixels ({100*actual_losses/loss_pixels:.1f}%)")
    
    # 4) Convert raster patches to vector polygons (optimized)
    print(f"\n[4/6] Polygonizing patches (min size: {min_pixels} pixels)...")
    polys = mask_to_polygons_optimized(
        loss_mask, 
        transform=prof0["transform"], 
        min_pixels=min_pixels
    )
    
    if len(polys) == 0:
        print("  ⚠ No polygons detected. Try adjusting threshold or min_pixels.")
        return None, None
    
    print(f"  ✓ Found {len(polys)} polygon patches")
    
    # 5) Create GeoDataFrame
    gdf = gpd.GeoDataFrame(geometry=polys, crs=prof0.get("crs", "EPSG:4326"))
    
    # 6) Calculate and cache statistics (before zoning)
    print("\n[5/6] Calculating statistics...")
    stats_cache = calculate_cached_statistics(gdf)
    
    # 7) Intersect with zoning if provided (spatial indexed)
    if zoning_path and os.path.exists(zoning_path):
        try:
            print(f"\n[6/6] Processing zoning data from {zoning_path}...")
            zoning = gpd.read_file(zoning_path)
            print(f"  Loaded {len(zoning)} zoning zones")
            
            print("  Intersecting with zoning boundaries (spatial indexed)...")
            gdf = intersect_with_zoning_spatial_indexed(gdf, zoning)
            
            if len(gdf) > 0:
                # Recalculate stats after zoning intersection
                stats_cache = calculate_cached_statistics(gdf)
                print(f"  ✓ Found {len(gdf)} zoning violations after intersection")
                
                # Batch save outputs
                saved_files = batch_save_geodataframe(gdf, output_dir, "violations",
                                                     formats=['GPKG', 'GeoJSON', 'Shapefile'])
            else:
                print("  ⚠ No intersections found with zoning areas")
                gdf = gpd.GeoDataFrame(geometry=polys, crs=prof0.get("crs", "EPSG:4326"))
                saved_files = batch_save_geodataframe(gdf, output_dir, "detections",
                                                     formats=['GPKG', 'GeoJSON'])
        
        except Exception as e:
            print(f"  ⚠ Warning: Could not process zoning data: {e}")
            print("  Falling back to detections without zoning...")
            saved_files = batch_save_geodataframe(gdf, output_dir, "detections",
                                                 formats=['GPKG', 'GeoJSON'])
    else:
        # Save without zoning
        saved_files = batch_save_geodataframe(gdf, output_dir, "detections",
                                             formats=['GPKG', 'GeoJSON'])
    
    # 8) Generate summary report
    if generate_report:
        config = {
            "red_t0": red_t0,
            "red_t1": red_t1,
            "threshold": threshold,
            "min_pixels": min_pixels,
            "chunk_size": chunk_size
        }
        generate_summary_report_optimized(gdf, stats_cache, output_dir, config)
    
    return gdf, stats_cache


def main():
    """CLI interface for optimized vegetation loss detection."""
    parser = argparse.ArgumentParser(
        description="Detect vegetation loss using optimized NDVI change detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python %(prog)s --red-t0 red_2020.tif --nir-t0 nir_2020.tif \\
                  --red-t1 red_2023.tif --nir-t1 nir_2023.tif

  # With zoning overlay
  python %(prog)s --red-t0 red_2020.tif --nir-t0 nir_2020.tif \\
                  --red-t1 red_2023.tif --nir-t1 nir_2023.tif \\
                  --zoning zoning.gpkg

  # Custom threshold and chunk size
  python %(prog)s --red-t0 red_2020.tif --nir-t0 nir_2020.tif \\
                  --red-t1 red_2023.tif --nir-t1 nir_2023.tif \\
                  --threshold -0.3 --min-pixels 50 --chunk-size 256
        """
    )
    
    # Required arguments
    parser.add_argument('--red-t0', required=True,
                       help='Path to time 0 red band raster')
    parser.add_argument('--nir-t0', required=True,
                       help='Path to time 0 NIR band raster')
    parser.add_argument('--red-t1', required=True,
                       help='Path to time 1 red band raster')
    parser.add_argument('--nir-t1', required=True,
                       help='Path to time 1 NIR band raster')
    
    # Optional arguments
    parser.add_argument('--zoning', default=None,
                       help='Path to zoning shapefile/geopackage (optional)')
    parser.add_argument('--threshold', type=float, default=-0.25,
                       help='NDVI delta threshold (default: -0.25)')
    parser.add_argument('--min-pixels', type=int, default=100,
                       help='Minimum patch size in pixels (default: 100)')
    parser.add_argument('--chunk-size', type=int, default=512,
                       help='Raster chunk size for processing (default: 512)')
    parser.add_argument('--output-dir', default='outputs',
                       help='Output directory (default: outputs)')
    parser.add_argument('--no-report', action='store_true',
                       help='Skip generating summary report')
    
    args = parser.parse_args()
    
    # Validate input files exist
    for path in [args.red_t0, args.nir_t0, args.red_t1, args.nir_t1]:
        if not os.path.exists(path):
            parser.error(f"Input file not found: {path}")
    
    if args.zoning and not os.path.exists(args.zoning):
        parser.error(f"Zoning file not found: {args.zoning}")
    
    # Run detection
    print("\nStarting optimized vegetation loss detection...")
    print(f"Time 0: {args.red_t0}, {args.nir_t0}")
    print(f"Time 1: {args.red_t1}, {args.nir_t1}")
    print(f"Chunk size: {args.chunk_size}x{args.chunk_size}")
    
    results, stats = detect_vegetation_loss_optimized(
        red_t0=args.red_t0,
        nir_t0=args.nir_t0,
        red_t1=args.red_t1,
        nir_t1=args.nir_t1,
        zoning_path=args.zoning,
        threshold=args.threshold,
        min_pixels=args.min_pixels,
        output_dir=args.output_dir,
        generate_report=not args.no_report,
        chunk_size=args.chunk_size
    )
    
    if results is not None:
        print(f"\n✓ Analysis complete!")
        print(f"  Detected {len(results)} total areas")
        print(f"  Total area: {stats['total_area']:.2f} sq units")
    else:
        print(f"\n⚠ No results detected. Try adjusting parameters.")
        sys.exit(1)


if __name__ == "__main__":
    main()
