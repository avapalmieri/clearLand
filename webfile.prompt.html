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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
            background: #f8f9fa;
            color: #1a1a1a;
        }}

        .header {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            padding: 24px 32px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            color: white;
        }}

        .header h1 {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}

        .header p {{
            opacity: 0.95;
            font-size: 15px;
            font-weight: 400;
            line-height: 1.5;
        }}

        .container {{
            display: flex;
            height: calc(100vh - 120px);
            gap: 0;
        }}

        .sidebar {{
            width: 380px;
            background: #ffffff;
            padding: 24px;
            overflow-y: auto;
            border-right: 1px solid #e5e7eb;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        }}

        .sidebar::-webkit-scrollbar {{
            width: 6px;
        }}

        .sidebar::-webkit-scrollbar-track {{
            background: transparent;
        }}

        .sidebar::-webkit-scrollbar-thumb {{
            background: #d1d5db;
            border-radius: 3px;
        }}

        .sidebar::-webkit-scrollbar-thumb:hover {{
            background: #9ca3af;
        }}

        .map-container {{
            flex: 1;
            position: relative;
            background: #f3f4f6;
        }}

        #map {{
            width: 100%;
            height: 100%;
        }}

        .section {{
            margin-bottom: 28px;
        }}

        .section:last-child {{
            margin-bottom: 0;
        }}

        .section-title {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6b7280;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .stat-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}

        .stat-card {{
            background: #f9fafb;
            padding: 14px;
            border-radius: 8px;
            border: 1px solid #f3f4f6;
            transition: all 0.2s ease;
        }}

        .stat-card:hover {{
            background: #f3f4f6;
            border-color: #e5e7eb;
        }}

        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            font-weight: 500;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}

        .stat-value {{
            font-size: 18px;
            font-weight: 700;
            color: #10b981;
            line-height: 1.2;
            word-break: break-word;
        }}

        .legend {{
            background: #f9fafb;
            padding: 14px;
            border-radius: 8px;
            border: 1px solid #f3f4f6;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            color: #374151;
        }}

        .legend-color {{
            width: 24px;
            height: 24px;
            border-radius: 4px;
            flex-shrink: 0;
            border: 2px solid rgba(0, 0, 0, 0.1);
        }}

        .zone-stats {{
            background: #f9fafb;
            padding: 14px;
            border-radius: 8px;
            border: 1px solid #f3f4f6;
        }}

        .zone-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            font-size: 13px;
            color: #374151;
            border-bottom: 1px solid #e5e7eb;
        }}

        .zone-item:last-child {{
            border-bottom: none;
        }}

        .zone-item span:last-child {{
            font-weight: 600;
            color: #10b981;
        }}

        .controls {{
            position: absolute;
            top: 16px;
            right: 16px;
            z-index: 1000;
            background: white;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
            min-width: 220px;
        }}

        .control-group {{
            margin-bottom: 12px;
        }}

        .control-group:last-child {{
            margin-bottom: 0;
        }}

        .control-label {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
            font-weight: 500;
            color: #374151;
            margin-bottom: 6px;
        }}

        .controls input[type="range"] {{
            width: 100%;
            height: 4px;
            border-radius: 2px;
            background: #e5e7eb;
            outline: none;
            -webkit-appearance: none;
            appearance: none;
            cursor: pointer;
        }}

        .controls input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #10b981;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }}

        .controls input[type="range"]::-moz-range-thumb {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #10b981;
            cursor: pointer;
            border: none;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }}

        .opacity-value {{
            font-weight: 600;
            color: #10b981;
        }}

        .export-btn {{
            margin-top: 12px;
            padding: 10px 14px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border: none;
            border-radius: 6px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            width: 100%;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
        }}

        .export-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
        }}

        .export-btn:active {{
            transform: translateY(0);
        }}

        .leaflet-popup-content {{
            color: #1a1a1a;
            font-size: 13px;
        }}

        .leaflet-popup-content h3 {{
            margin-bottom: 10px;
            color: #10b981;
            font-size: 14px;
            font-weight: 700;
        }}

        .popup-detail {{
            margin: 6px 0;
            font-size: 12px;
            line-height: 1.4;
        }}

        .popup-detail strong {{
            color: #374151;
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .sidebar {{
                width: 320px;
                padding: 16px;
            }}

            .stat-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 24px;
            }}

            .header {{
                padding: 16px 20px;
            }}
        }}

        @media (max-width: 768px) {{
            .container {{
                flex-direction: column;
                height: auto;
            }}

            .sidebar {{
                width: 100%;
                border-right: none;
                border-bottom: 1px solid #e5e7eb;
                max-height: 300px;
            }}

            .map-container {{
                height: 400px;
            }}

            .header h1 {{
                font-size: 20px;
            }}

            .controls {{
                top: 8px;
                right: 8px;
                min-width: auto;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌍 Vegetation Loss Detection</h1>
        <p>{description}</p>
    </div>

    <div class="container">
        <div class="sidebar">
            <div class="section">
                <div class="section-title">📊 Summary Statistics</div>
                <div class="stat-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Detections</div>
                        <div class="stat-value" id="total-areas">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Area</div>
                        <div class="stat-value" id="total-area" style="font-size: 15px;">0 sq</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Average</div>
                        <div class="stat-value" id="avg-area" style="font-size: 15px;">0 sq</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Largest Patch</div>
                        <div class="stat-value" id="max-area" style="font-size: 15px;">0 sq</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">🗺️ Legend</div>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color" style="background: rgba(239, 68, 68, 0.6);"></div>
                        <span>Vegetation Loss Area</span>
                    </div>
                </div>
            </div>

            <div class="section" id="zone-stats" style="display: none;">
                <div class="section-title">📍 Zone Breakdown</div>
                <div class="zone-stats">
                    <div id="zone-list"></div>
                    <button class="export-btn" onclick="exportZoneStats()">📥 Export Stats</button>
                </div>
            </div>
        </div>

        <div class="map-container">
            <div id="map"></div>
            <div class="controls">
                <div class="control-group">
                    <div class="control-label">
                        <span>Opacity</span>
                        <span class="opacity-value" id="opacity-value">60%</span>
                    </div>
                    <input type="range" id="opacity-slider" min="0" max="100" value="60">
                </div>
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
                        fillColor: '#ef4444',
                        fillOpacity: 0.6,
                        color: '#991b1b',
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
            document.getElementById('total-area').textContent = totalArea.toFixed(0);
            document.getElementById('avg-area').textContent = avgArea.toFixed(0);
            document.getElementById('max-area').textContent = maxArea.toFixed(0);

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
            document.getElementById('opacity-value').textContent = e.target.value + '%';
            
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
  python generate_viewer.py outputs/violations.geojson \
      -o report.html \
      -t "Conservation Zone Analysis" \
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
