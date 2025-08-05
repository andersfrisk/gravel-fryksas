"""
Script to generate static HTML pages for the Gravel Fryksås site.

The script reads YAML front matter from markdown files located under
``areas/<area>/metadata`` and produces:

* an index page per area listing all routes with filtering options
* a dedicated page for each route with map, facts and description
* a root index page linking to all areas

To run the script simply execute it with python. It will overwrite
existing HTML files in the output directories.
"""

import os
import yaml
import json
from pathlib import Path


def load_routes(area_path: Path):
    """Load all route metadata files for a given area.

    Args:
        area_path: Path to the area directory (e.g. areas/fryksas).

    Returns:
        List of route metadata dictionaries.
    """
    metadata_dir = area_path / "metadata"
    routes = []
    for md_file in sorted(metadata_dir.glob("*.md")):
        with md_file.open("r", encoding="utf-8") as f:
            content = f.read().strip()
        # Strip starting/ending --- delimiters if present
        if content.startswith("---"):
            content = content.strip("-").strip()
        # Parse YAML front matter
        meta = yaml.safe_load(content)
        routes.append(meta)
    return routes


def generate_area_index(area: str, routes: list, output_path: Path):
    """Generate an index page for a single area.

    The page lists all routes in a table and provides simple filters for
    maximum distance and elevation.

    Args:
        area: Name of the area (slug)
        routes: List of route metadata dictionaries
        output_path: Destination file for the generated HTML
    """
    # Prepare JavaScript data array of routes for client-side filtering
    routes_json = json.dumps([
        {
            "title": r["title"],
            "slug": r["slug"],
            "distance": r.get("distance_km"),
            "elevation": r.get("elevation_m"),
            "asphalt": r.get("asphalt_pct"),
            "gravel": r.get("gravel_pct"),
        }
        for r in routes
    ], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang=\"sv\">
<head>
  <meta charset=\"utf-8\">
  <title>Gravel {area.capitalize()}</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <link rel=\"stylesheet\" href=\"../../shared/style.css\">
  <script src=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js\"></script>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css\" />
</head>
<body>
  <header class=\"header\">
    <h1>Gravelrutter i {area.capitalize()}</h1>
    <nav><a href=\"/index.html\">Till startsidan</a></nav>
  </header>
  <section class=\"filter\">
    <label>Max distans (km): <input id=\"maxDist\" type=\"number\" min=\"0\" step=\"1\" placeholder=\"Alla\"></label>
    <label>Max höjdmeter: <input id=\"maxElev\" type=\"number\" min=\"0\" step=\"50\" placeholder=\"Alla\"></label>
    <button onclick=\"applyFilters()\">Filtrera</button>
    <button onclick=\"resetFilters()\">Återställ</button>
  </section>
  <section id=\"routeList\"></section>
  <script>
    const routes = {routes_json};
    function renderList(data) {{
      const container = document.getElementById('routeList');
      container.innerHTML = '';
      if (!data.length) {{
        container.innerHTML = '<p>Inga rutter matchar filtren.</p>';
        return;
      }}
      data.forEach(r => {{
        const div = document.createElement('div');
        div.className = 'route-card';
        div.innerHTML = `
          <h2><a href=\"./routes/${{r.slug}}.html\">${{r.title}}</a></h2>
          <p><strong>Distans:</strong> ${{r.distance}} km<br>
          <strong>Höjdmeter:</strong> ${{r.elevation}} m<br>
          <strong>Asfalt:</strong> ${{r.asphalt}} %<br>
          <strong>Grus:</strong> ${{r.gravel}} %</p>
        `;
        container.appendChild(div);
      }});
    }}
    function applyFilters() {{
      const maxD = parseFloat(document.getElementById('maxDist').value);
      const maxE = parseFloat(document.getElementById('maxElev').value);
      const filtered = routes.filter(r => {{
        return (isNaN(maxD) || r.distance <= maxD) &&
               (isNaN(maxE) || r.elevation <= maxE);
      }});
      renderList(filtered);
    }}
    function resetFilters() {{
      document.getElementById('maxDist').value = '';
      document.getElementById('maxElev').value = '';
      renderList(routes);
    }}
    // Initial render
    renderList(routes);
  </script>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def generate_route_page(area: str, route: dict, output_path: Path):
    """Generate a single route page.

    Args:
        area: Area slug
        route: Route metadata dict
        output_path: Destination file path
    """
    title = route["title"]
    slug = route["slug"]
    distance = route.get("distance_km")
    elevation = route.get("elevation_m")
    asphalt = route.get("asphalt_pct")
    gravel = route.get("gravel_pct")
    gpx_file = route.get("gpx_file")
    description = route.get("description", "")
    # For placeholder images we just reference the thumbnail; user can replace later
    thumbnail = route.get("thumbnail")
    photos = route.get("photos", [])
    # Create HTML content.  Avoid using f-strings for the entire document so we can
    # safely embed curly braces used by Leaflet templates without triggering
    # Python formatting. We'll build the page incrementally.
    description_html = description.replace("\n", "<br>")
    # Build the list of photo <li> elements
    photo_items = "".join([
        f'<li><img src="../images/{img}" alt="Foto {title}"></li>' for img in photos
    ])
    # Build a map script with doubled braces so Python's .format doesn't try to
    # interpret them. Only the gpx_file placeholder remains single-braced.
    map_script_template = '''
    <script>
      const map = L.map('map');
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: 'Map data © <a href="https://openstreetmap.org">OpenStreetMap</a> contributors'
      }}).addTo(map);
      const gpxPath = '../../gpx/{gpx_file}';
      new L.GPX(gpxPath, {{
        async: true,
        marker_options: {{
          startIconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.gpx/1.7.0/pin-icon-start.png',
          endIconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.gpx/1.7.0/pin-icon-end.png',
          shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.gpx/1.7.0/pin-shadow.png'
        }}
      }}).on('loaded', function(e) {{
        map.fitBounds(e.target.getBounds());
      }}).addTo(map);
    </script>
    '''
    map_script = map_script_template.format(gpx_file=gpx_file)
    html = (
        "<!DOCTYPE html>\n"
        "<html lang='sv'>\n"
        "<head>\n"
        "  <meta charset='utf-8'>\n"
        f"  <title>{title} – Gravelrutt</title>\n"
        "  <meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        "  <link rel='stylesheet' href='../../../shared/style.css'>\n"
        "  <script src='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js'></script>\n"
        "  <script src='https://cdnjs.cloudflare.com/ajax/libs/leaflet.gpx/1.7.0/gpx.min.js'></script>\n"
        "  <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css' />\n"
        "</head>\n"
        "<body>\n"
        "  <header class='header'>\n"
        f"    <h1>{title}</h1>\n"
        "    <nav><a href='../index.html'>Tillbaka till ruttlistan</a> | <a href='/index.html'>Startsida</a></nav>\n"
        "  </header>\n"
        "  <section class='route-content'>\n"
        "    <div class='route-facts'>\n"
        f"      <p><strong>Distans:</strong> {distance} km</p>\n"
        f"      <p><strong>Höjdmeter:</strong> {elevation} m</p>\n"
        f"      <p><strong>Andel asfalt:</strong> {asphalt} %</p>\n"
        f"      <p><strong>Andel grus:</strong> {gravel} %</p>\n"
        "    </div>\n"
        "    <div id='map' style='height:400px; margin-bottom:1em;'></div>\n"
        + map_script +
        "    <article class='description'>\n"
        f"      <p>{description_html}</p>\n"
        "    </article>\n"
        "    <section class='photos'>\n"
        "      <h2>Bilder</h2>\n"
        "      <ul class='photo-gallery'>" + photo_items + "</ul>\n"
        "    </section>\n"
        f"    <p><a href='../../gpx/{gpx_file}'>Ladda ned GPX-fil</a></p>\n"
        "  </section>\n"
        "</body>\n"
        "</html>"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def generate_root_index(areas: list, output_path: Path):
    """Generate the root index page listing all areas."""
    html = """<!DOCTYPE html>
<html lang='sv'>
<head>
  <meta charset='utf-8'>
  <title>Gravelrutter</title>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <link rel='stylesheet' href='shared/style.css'>
</head>
<body>
  <header class='header'>
    <h1>Gravelrutter</h1>
  </header>
  <section>
    <p>Välj område:</p>
    <ul>
"""
    for area in areas:
        html += f"      <li><a href='areas/{area}/index.html'>{area.capitalize()}</a></li>\n"
    html += """    </ul>
  </section>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def main():
    project_root = Path(__file__).resolve().parent
    areas_dir = project_root / "areas"
    areas = []
    for area_path in areas_dir.iterdir():
        if area_path.is_dir():
            area = area_path.name
            areas.append(area)
            routes = load_routes(area_path)
            # Generate area index
            generate_area_index(area, routes, area_path / "index.html")
            # Generate route pages
            for route in routes:
                out_path = area_path / "routes" / f"{route['slug']}.html"
                generate_route_page(area, route, out_path)
    # Generate root index
    generate_root_index(areas, project_root / "index.html")


if __name__ == "__main__":
    main()