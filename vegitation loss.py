"""
NDVI Vegetation Loss Detection
Main detection script with CLI interface and reporting
"""

import geopandas as gpd
import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.spatial import (
    mask_to_polygons, 
    intersect_with_zoning,
    ndvi_from_paths,
    ndvi_delta
)


def generate_summary_report(gdf, output_dir, config):
    """Generate summary statistics and report."""
    
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
            "total_polygons": len(gdf),
            "total_area_sq_units": float(gdf.geometry.area.sum()),
            "mean_area": float(gdf.geometry.area.mean()),
            "median_area": float(gdf.geometry.area.median()),
            "max_area": float(gdf.geometry.area.max()),
            "min_area": float(gdf.geometry.area.min()),
        }
    }
    
    # Add zoning statistics if available
    if 'zoning_type' in gdf.columns or 'zone' in gdf.columns:
        zone_col = 'zoning_type' if 'zoning_type' in gdf.columns else 'zone'
        zone_counts = gdf[zone_col].value_counts().to_dict()
        report["results"]["violations_by_zone"] = zone_counts
    
    # Calculate centroid bounds for map centering
    centroids = gdf.geometry.centroid
    report["map_bounds"] = {
        "center_lat": float(centroids.y.mean()),
        "center_lon": float(centroids.x.mean()),
        "bounds": {
            "north": float(gdf.total_bounds[3]),
            "south": float(gdf.total_bounds[1]),
            "east": float(gdf.total_bounds[2]),
            "west": float(gdf.total_bounds[0])
        }
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
        for zone, count in report['results']['violations_by_zone'].items():
            print(f"  {zone}: {count}")
    
    print(f"\nDetailed report saved: {report_path}")
    print("="*60 + "\n")
    
    return report


def detect_vegetation_loss(red_t0, nir_t0, red_t1, nir_t1, 
                          zoning_path=None, threshold=-0.25, 
                          min_pixels=100, output_dir="outputs",
                          generate_report=True):
    """
    Detect vegetation loss between two time periods using NDVI change detection.
    
    Args:
        red_t0, nir_t0: Paths to time 0 red and NIR bands
        red_t1, nir_t1: Paths to time 1 red and NIR bands
        zoning_path: Optional path to zoning shapefile/gpkg
        threshold: NDVI delta threshold (negative = loss)
        min_pixels: Minimum patch size to keep
        output_dir: Directory for output files
        generate_report: Whether to generate summary statistics
    
    Returns:
        GeoDataFrame of detected polygons
    """
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # 1) Calculate NDVI for both time periods
    print("Calculating NDVI for time 0...")
    ndvi0, prof0 = ndvi_from_paths(red_t0, nir_t0)
    
    print("Calculating NDVI for time 1...")
    ndvi1, prof1 = ndvi_from_paths(red_t1, nir_t1)
    
    # 2) Calculate change (negative = vegetation loss)
    print("Computing NDVI delta...")
    delta = ndvi_delta(ndvi0, ndvi1)
    
    # 3) Create binary mask of significant loss
    loss_mask = (delta < threshold)
    loss_pixels = loss_mask.sum()
    print(f"Detected {loss_pixels:,} pixels with NDVI < {threshold}")
    
    # 4) Convert raster patches to vector polygons
    print(f"Polygonizing patches (min size: {min_pixels} pixels)...")
    polys = mask_to_polygons(
        loss_mask, 
        transform=prof0["transform"], 
        min_pixels=min_pixels
    )
    
    if len(polys) == 0:
        print("No polygons detected. Try adjusting threshold or min_pixels.")
        return None
    
    print(f"Found {len(polys)} polygon patches")
    
    # 5) Intersect with zoning if provided
    if zoning_path and os.path.exists(zoning_path):
        try:
            print(f"Loading zoning data from {zoning_path}...")
            zoning = gpd.read_file(zoning_path)
            
            print("Intersecting with zoning boundaries...")
            gdf = intersect_with_zoning(polys, zoning)
            
            out_path = os.path.join(output_dir, "violations.gpkg")
            gdf.to_file(out_path, driver="GPKG")
            print(f"✓ Saved {len(gdf)} zoning violations → {out_path}")
            
            # Also save as GeoJSON for web display
            geojson_path = os.path.join(output_dir, "violations.geojson")
            gdf.to_file(geojson_path, driver="GeoJSON")
            print(f"✓ Saved web-ready GeoJSON → {geojson_path}")
            
        except Exception as e:
            print(f"⚠ Warning: Could not process zoning data: {e}")
            print("Falling back to detections without zoning...")
            gdf = None
    else:
        gdf = None
    
    # 6) Save without zoning intersection if needed
    if gdf is None:
        gdf = gpd.GeoDataFrame(geometry=polys, crs=prof0.get("crs", "EPSG:4326"))
        
        out_path = os.path.join(output_dir, "detections.gpkg")
        gdf.to_file(out_path, driver="GPKG")
        print(f"✓ Saved {len(polys)} detections → {out_path}")
        
        # Save GeoJSON for web
        geojson_path = os.path.join(output_dir, "detections.geojson")
        gdf.to_file(geojson_path, driver="GeoJSON")
        print(f"✓ Saved web-ready GeoJSON → {geojson_path}")
    
    # 7) Generate summary report
    if generate_report:
        config = {
            "red_t0": red_t0,
            "red_t1": red_t1,
            "threshold": threshold,
            "min_pixels": min_pixels
        }
        generate_summary_report(gdf, output_dir, config)
    
    return gdf


def main():
    """CLI interface for vegetation loss detection."""
    parser = argparse.ArgumentParser(
        description="Detect vegetation loss using NDVI change detection",
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

  # Custom threshold and minimum size
  python %(prog)s --red-t0 red_2020.tif --nir-t0 nir_2020.tif \\
                  --red-t1 red_2023.tif --nir-t1 nir_2023.tif \\
                  --threshold -0.3 --min-pixels 50
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
    print("\nStarting vegetation loss detection...")
    print(f"Time 0: {args.red_t0}, {args.nir_t0}")
    print(f"Time 1: {args.red_t1}, {args.nir_t1}")
    
    results = detect_vegetation_loss(
        red_t0=args.red_t0,
        nir_t0=args.nir_t0,
        red_t1=args.red_t1,
        nir_t1=args.nir_t1,
        zoning_path=args.zoning,
        threshold=args.threshold,
        min_pixels=args.min_pixels,
        output_dir=args.output_dir,
        generate_report=not args.no_report
    )
    
    if results is not None:
        print(f"\n✓ Analysis complete!")
    else:
        print(f"\n⚠ No results detected. Try adjusting parameters.")
        sys.exit(1)


if __name__ == "__main__":
    main()