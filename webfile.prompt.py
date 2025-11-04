#!/usr/bin/env python3
"""
Generate Standalone Web Viewer
Creates a single HTML file with embedded GeoJSON data that can be shared and opened in any browser.
Usage: python generate_viewer.py path/to/your/data.geojson
"""

import json
import argparse
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vegetation Loss Detection - {title}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a1a;
            color: #fff;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}

        .header h1 {{
            font-size: 28px;
            margin-bottom: 8px;
        }}

        .header p {{
            opacity: 0.9;
            font-size: 14px;
        }}

        .container {{
            display: flex;
            height: calc(100vh - 110px);
        }}

        .sidebar {{
            width: 350px;
            background: #2d2d2d;
            padding: 20px;
            overflow-y: auto;
            border-right: 1px solid #444;
        }}

        .map-container {{
            flex: 1;
            position: relative;
        }}

        #map {{
            width: 100%;
            height: 100%;
        }}

        .stats-section {{
            margin-bottom: 25px;
            padding: 20px;
            background: #3a3a3a;
            border-radius: 8px;
        }}

        .stats-section h2 {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #667eea;
        }}

        .stat-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #4a4a4a;
        }}

        .stat-item:last-child {{
            border-bottom: none;
        }}

        .stat-label {{
            color: #aaa;
            font-size: 14px;
        }}

        .stat-value {{
            color: #fff;
            font-weight: 600;
            font-size: 14px;
        }}

        .legend {{
            padding: 15px;
            background: #3a3a3a;
            border-radius: 8px;
            margin-bottom: 20px;
        }}

        .legend h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            color: #667eea;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 10px;
            border: 2px solid #fff;
        }}

        .zone-stats {{
            padding: 15px;
            background: #3a3a3a;
            border-radius: 8px;
        }}

        .zone-stats h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            color: #667eea;
        }}

        .zone-item {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 13px;
        }}

        .leaflet-popup-content {{
            color: #000;
        }}

        .leaflet-popup-content h3 {{
            margin-bottom: 10px;
            color: #667eea;
        }}

        .popup-detail {{
            margin: 5px 0;
            font-size: 13px;
        }}

        .controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(45, 45, 45, 0.95);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}

        .controls label {{
            display: block;
            margin-bottom: 5px;
            font-size: 13px;
            color: #aaa;
        }}

        .controls input[type="range"] {{
            width: 150px;
        }}

        .opacity-value {{
            display: inline-block;
            width: 30px;
            text-align: right;
            font-size: 13px;
            color: #fff;
        }}

        .export-btn {{
            margin-top: 15px;
            padding: 8px 15px;
            background: #667eea;
            border: none;
            border-radius: 6px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            width: 100%;
            transition: background 0.3s;
        }}

        .export-btn:hover {{
            background: #764ba2;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌳 Vegetation Loss Detection</h1>
        <p>{description}</p>
    </div>

    <div class="container">
        <div class="sidebar">
            <div class="stats-section">
                <h2>📊 Summary Statistics</h2>
                <div class="stat-item">
                    <span class="stat-label">Total Areas Detected:</span>
                    <span class="stat-value" id="total-areas">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Area:</span>
                    <span class="stat-value" id="total-area">0 sq units</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Average Area:</span>
                    <span class="stat-value" id="avg-area">0 sq units</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Median Area:</span>
                    <span class="stat-value" id="median-area">0 sq units</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Largest Patch:</span>
                    <span class="stat-value" id="max-area">0 sq units</span>
                </div>
            </div>

            <div class="legend">
                <h3>🗺️ Legend</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: rgba(255, 59, 48, 0.6);"></div>
                    <span>Vegetation Loss Areas</span>
                </div>
            </div>

            <div class="zone-stats" id="zone-stats" style="display: none;">
                <h3>📍 By Zone Type</h3>
                <div id="zone-list"></div>
                <button class="export-btn" onclick="exportZoneStats()">📥 Export Zone Stats</button>
            </div>
        </div>

        <div class="map-container">
            <div id="map"></div>
            <div class="controls">
                <label>Opacity: <span class="opacity-value" id="opacity-value">60</span>%</label>
                <input type="range" id="opacity-slider" min="0" max="100" value="60">
            </div>
        </div>
    </div>

    <script>
        // Embedded GeoJSON data
        const geojsonData = {geojson_data};

        // Initialize map
        const map = L.map('map');
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }}).addTo(map);

        let dataLayer = null;

        function initMap() {{
            // Add data layer
            dataLayer = L.geoJSON(geojsonData, {{
                style: function(feature) {{
                    return {{
                        fillColor: '#ff3b30',
                        fillOpacity: 0.6,
                        color: '#c41e3a',
                        weight: 2
                    }};
                }},
                onEachFeature: function(feature, layer) {{
                    // Create popup
                    let popupContent = '<h3>Detection Details</h3>';
                    
                    if (feature.properties) {{
                        for (let key in feature.properties) {{
                            let value = feature.properties[key];
                            if (typeof value === 'number' && key.toLowerCase().includes('area')) {{
                                value = value.toFixed(2) + ' sq units';
                            }}
                            popupContent += `<div class="popup-detail"><strong>${{key}}:</strong> ${{value}}</div>`;
                        }}
                    }}
                    
                    layer.bindPopup(popupContent);
                    
                    // Highlight on hover
                    layer.on('mouseover', function() {{
                        layer.setStyle({{
                            fillOpacity: 0.8,
                            weight: 3
                        }});
                    }});
                    
                    layer.on('mouseout', function() {{
                        layer.setStyle({{
                            fillOpacity: parseFloat(document.getElementById('opacity-slider').value) / 100,
                            weight: 2
                        }});
                    }});
                }}
            }}).addTo(map);

            // Fit map to data bounds
            if (geojsonData.features && geojsonData.features.length > 0) {{
                map.fitBounds(dataLayer.getBounds());
            }}

            // Calculate and display statistics
            updateStatistics();
        }}

        function updateStatistics() {{
            const features = geojsonData.features || [];
            
            if (features.length === 0) return;

            let areas = [];
            let zoneCount = {{}};
            
            features.forEach(feature => {{
                const area = feature.properties?.area || feature.properties?.area_sq_units || 0;
                areas.push(area);
                
                // Count by zone if available
                const zone = feature.properties?.zone || feature.properties?.zoning_type || feature.properties?.zoning;
                if (zone) {{
                    zoneCount[zone] = (zoneCount[zone] || 0) + 1;
                }}
            }});

            const totalArea = areas.reduce((a, b) => a + b, 0);
            const avgArea = totalArea / areas.length;
            const maxArea = Math.max(...areas);
            
            // Calculate median
            areas.sort((a, b) => a - b);
            const medianArea = areas.length % 2 === 0
                ? (areas[areas.length / 2 - 1] + areas[areas.length / 2]) / 2
                : areas[Math.floor(areas.length / 2)];

            // Update UI
            document.getElementById('total-areas').textContent = features.length;
            document.getElementById('total-area').textContent = totalArea.toFixed(2) + ' sq units';
            document.getElementById('avg-area').textContent = avgArea.toFixed(2) + ' sq units';
            document.getElementById('median-area').textContent = medianArea.toFixed(2) + ' sq units';
            document.getElementById('max-area').textContent = maxArea.toFixed(2) + ' sq units';

            // Display zone statistics if available
            if (Object.keys(zoneCount).length > 0) {{
                const zoneStats = document.getElementById('zone-stats');
                const zoneList = document.getElementById('zone-list');
                zoneStats.style.display = 'block';
                
                let zoneHTML = '';
                for (let [zone, count] of Object.entries(zoneCount).sort((a, b) => b[1] - a[1])) {{
                    zoneHTML += `<div class="zone-item"><span>${{zone}}</span><span>${{count}}</span></div>`;
                }}
                zoneList.innerHTML = zoneHTML;
                
                // Store for export
                window.zoneStats = zoneCount;
            }}
        }}

        // Opacity control
        document.getElementById('opacity-slider').addEventListener('input', function(e) {{
            const opacity = e.target.value / 100;
            document.getElementById('opacity-value').textContent = e.target.value;
            
            if (dataLayer) {{
                dataLayer.setStyle({{
                    fillOpacity: opacity
                }});
            }}
        }});

        // Export zone statistics
        function exportZoneStats() {{
            if (!window.zoneStats) return;
            
            let csv = 'Zone,Count\\n';
            for (let [zone, count] of Object.entries(window.zoneStats)) {{
                csv += `"${{zone}}",${{count}}\\n`;
            }}
            
            const blob = new Blob([csv], {{ type: 'text/csv' }});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'zone_statistics.csv';
            a.click();
        }}

        // Initialize on load
        initMap();
    </script>
</body>
</html>
"""


def generate_viewer(geojson_path, output_path=None, title=None, description=None):
    """
    Generate a standalone HTML viewer with embedded GeoJSON data.
    
    Args:
        geojson_path: Path to GeoJSON file
        output_path: Path for output HTML (default: same name as input)
        title: Title for the viewer
        description: Description text
    """
    geojson_path = Path(geojson_path)
    
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")
    
    # Read GeoJSON
    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)
    
    # Determine output path
    if output_path is None:
        output_path = geojson_path.with_suffix('.html')
    else:
        output_path = Path(output_path)
    
    # Set defaults
    if title is None:
        title = geojson_path.stem.replace('_', ' ').title()
    
    if description is None:
        num_features = len(geojson_data.get('features', []))
        description = f"Detected {num_features} areas of vegetation loss"
    
    # Generate HTML
    html = HTML_TEMPLATE.format(
        title=title,
        description=description,
        geojson_data=json.dumps(geojson_data)
    )
    
    # Write output
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✓ Generated web viewer: {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"  Open in browser: file://{output_path.absolute()}")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate standalone HTML viewer for vegetation loss detection results",
        epilog="""
Examples:
  # Basic usage
  python generate_viewer.py outputs/violations.geojson
  
  # With custom output and metadata
  python generate_viewer.py outputs/violations.geojson -o report.html -t "Q4 2024 Analysis"
  
  # Full customization
  python generate_viewer.py outputs/violations.geojson \\
      -o report.html \\
      -t "Conservation Zone Analysis" \\
      -d "Detected vegetation loss in protected areas from Jan-Oct 2024"
        """
    )
    
    parser.add_argument('geojson', 
                       help='Path to GeoJSON file')
    parser.add_argument('-o', '--output',
                       help='Output HTML file path (default: same as input with .html extension)')
    parser.add_argument('-t', '--title',
                       help='Title for the viewer')
    parser.add_argument('-d', '--description',
                       help='Description text')
    
    args = parser.parse_args()
    
    try:
        generate_viewer(
            args.geojson,
            args.output,
            args.title,
            args.description
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())