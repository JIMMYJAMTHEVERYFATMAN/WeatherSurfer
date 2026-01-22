import os
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-features=DirectComposition"
# os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"  # only if needed

import sys
import json
import asyncio

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtWebEngineWidgets import QWebEngineView

import math
import urllib.parse
import urllib.request





def error_message(error, msg):
	error.emit(str(msg))
	print(f"ERROR: {msg}")


def build_map_html(lat, lon, accuracy_m=None, spots=None):
	if spots is None:
		spots = []

	payload = {
		"lat": lat,
		"lon": lon,
		"acc": accuracy_m,
		"spots": spots,  # list of dicts: name/lat/lon/dist_km
	}
	js_payload = json.dumps(payload)

	return f"""<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>Map</title>

	<link
		rel="stylesheet"
		href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
		integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
		crossorigin=""
	/>

	<style>
		:root {{
			--bg: #0b0c10;
			--card: rgba(255, 255, 255, 0.06);
			--card2: rgba(255, 255, 255, 0.08);
			--text: rgba(255, 255, 255, 0.92);
			--muted: rgba(255, 255, 255, 0.62);
			--border: rgba(255,255,255,0.10);
		}}

		html, body {{
			height: 100%;
			margin: 0;
			background: var(--bg);
			font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
			color: var(--text);
		}}

		#wrap {{
			height: 100%;
			display: grid;
			grid-template-rows: auto 1fr;
			gap: 12px;
			padding: 14px;
			box-sizing: border-box;
		}}

		#topbar {{
			background: var(--card);
			border: 1px solid var(--border);
			border-radius: 14px;
			padding: 12px 14px;
			display: flex;
			align-items: baseline;
			justify-content: space-between;
			backdrop-filter: blur(10px);
		}}

		#title {{
			font-size: 14px;
			letter-spacing: 0.2px;
		}}

		#coords {{
			font-size: 12px;
			color: var(--muted);
			text-align: right;
			margin-left: 16px;
		}}

		#content {{
			display: grid;
			grid-template-columns: 320px 1fr;
			gap: 12px;
			min-height: 0;
		}}

		#sidebar {{
			background: var(--card);
			border: 1px solid var(--border);
			border-radius: 16px;
			overflow: hidden;
			display: flex;
			flex-direction: column;
			min-height: 0;
		}}

		#sidebarHeader {{
			padding: 12px 14px;
			border-bottom: 1px solid var(--border);
			display: flex;
			gap: 10px;
			align-items: center;
			justify-content: space-between;
		}}

		#sidebarHeader .left {{
			display: grid;
			gap: 2px;
		}}

		#sidebarHeader .h {{
			font-size: 13px;
			font-weight: 600;
		}}

		#sidebarHeader .s {{
			font-size: 11px;
			color: var(--muted);
		}}

		#list {{
			overflow: auto;
			padding: 10px;
			display: grid;
			gap: 10px;
		}}

		.card {{
			background: var(--card2);
			border: 1px solid var(--border);
			border-radius: 14px;
			padding: 10px 10px;
			cursor: pointer;
			transition: transform 120ms ease, background 120ms ease, border 120ms ease;
		}}
		.card:hover {{
			transform: translateY(-1px);
			border-color: rgba(255,255,255,0.18);
		}}
		.card .name {{
			font-size: 12.5px;
			font-weight: 600;
			line-height: 1.2;
		}}
		.card .meta {{
			margin-top: 6px;
			font-size: 11px;
			color: var(--muted);
			display: flex;
			gap: 10px;
			flex-wrap: wrap;
		}}

		#map {{
			border-radius: 16px;
			overflow: hidden;
			border: 1px solid var(--border);
			box-shadow: 0 20px 60px rgba(0,0,0,0.45);
			min-height: 0;
		}}

		.leaflet-control-zoom a {{
			background: rgba(20, 20, 24, 0.75) !important;
			color: rgba(255,255,255,0.85) !important;
			border: 1px solid rgba(255,255,255,0.10) !important;
			backdrop-filter: blur(8px);
		}}
		.leaflet-control-attribution {{
			background: rgba(20, 20, 24, 0.55) !important;
			color: rgba(255,255,255,0.60) !important;
			border-radius: 10px;
			margin: 10px !important;
			padding: 6px 10px !important;
			border: 1px solid rgba(255,255,255,0.08) !important;
			backdrop-filter: blur(8px);
		}}
	</style>
</head>
<body>
	<div id="wrap">
		<div id="topbar">
			<div id="title">Nearby windsurf spots</div>
			<div id="coords">—</div>
		</div>

		<div id="content">
			<div id="sidebar">
				<div id="sidebarHeader">
					<div class="left">
						<div class="h">Spots</div>
						<div class="s" id="count">Loading…</div>
					</div>
				</div>
				<div id="list"></div>
			</div>
			<div id="map"></div>
		</div>
	</div>

	<script
		src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
		integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
		crossorigin=""
	></script>

	<script>
		const data = {js_payload};

		const coordsEl = document.getElementById("coords");
		const countEl = document.getElementById("count");
		const listEl = document.getElementById("list");

		const fmt = (n) => (Math.round(n * 100000) / 100000).toFixed(5);

		let line = `${{fmt(data.lat)}}, ${{fmt(data.lon)}}`;
		if (typeof data.acc === "number") {{
			line += ` · ±${{(data.acc/1000).toFixed(1)}} km`;
		}}
		coordsEl.textContent = line;

		// Make Leaflet smoother
		const map = L.map("map", {{
			zoomControl: true,
			preferCanvas: true,          // BIG win if you add lots of markers
			updateWhenZooming: false,    // reduces stutter while zooming
			updateWhenIdle: true,
		}}).setView([data.lat, data.lon], 12);

		L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
			maxZoom: 19,
			attribution: "&copy; OpenStreetMap contributors",
			updateWhenIdle: true,
			keepBuffer: 2
		}}).addTo(map);
		// User marker
		L.circleMarker([data.lat, data.lon], {{
			radius: 7,
			weight: 2,
			color: "rgba(255,255,255,0.9)",
			fillColor: "rgba(255,255,255,0.35)",
			fillOpacity: 1
		}}).addTo(map).bindPopup("You are here");

		if (typeof data.acc === "number") {{
			L.circle([data.lat, data.lon], {{ radius: data.acc }}).addTo(map);
		}}

		// Spots markers + sidebar cards
		const markers = [];
		function flyToSpot(i) {{
			const s = data.spots[i];
			if (!s) return;
			map.flyTo([s.lat, s.lon], 13, {{ animate: true, duration: 0.6 }});
			const m = markers[i];
			if (m) m.openPopup();
		}}

		function makeCard(i, s) {{
			const el = document.createElement("div");
			el.className = "card";
			el.innerHTML = `
				<div class="name">${{s.name}}</div>
				<div class="meta">
					<span>${{s.dist_km.toFixed(1)}} km</span>
					<span>${{fmt(s.lat)}}, ${{fmt(s.lon)}}</span>
				</div>
			`;
			el.addEventListener("click", () => flyToSpot(i));
			return el;
		}}

		(data.spots || []).forEach((s, i) => {{
			const m = L.marker([s.lat, s.lon]).addTo(map)
				.bindPopup(`<b>${{s.name}}</b><br>${{s.dist_km.toFixed(1)}} km away`);
			markers.push(m);
			listEl.appendChild(makeCard(i, s));
		}});

		countEl.textContent = `${{(data.spots || []).length}} spots found`;
	</script>
</body>
</html>
"""


def haversine_km(lat1, lon1, lat2, lon2):
	R = 6371.0
	phi1 = math.radians(lat1)
	phi2 = math.radians(lat2)
	dphi = math.radians(lat2 - lat1)
	dlam = math.radians(lon2 - lon1)

	a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	return R * c


def overpass_query(lat, lon, radius_m=30000, include_beaches=False, limit=120):
	parts = f"""
	node(around:{radius_m},{lat},{lon})["sport"="windsurfing"];
	way(around:{radius_m},{lat},{lon})["sport"="windsurfing"];
	relation(around:{radius_m},{lat},{lon})["sport"="windsurfing"];

	node(around:{radius_m},{lat},{lon})["leisure"="sports_centre"]["sport"~"windsurfing|sailing|kitesurfing"];
	way(around:{radius_m},{lat},{lon})["leisure"="sports_centre"]["sport"~"windsurfing|sailing|kitesurfing"];
	relation(around:{radius_m},{lat},{lon})["leisure"="sports_centre"]["sport"~"windsurfing|sailing|kitesurfing"];
	"""

	if include_beaches:
		parts += f"""
		node(around:{radius_m},{lat},{lon})["natural"="beach"];
		way(around:{radius_m},{lat},{lon})["natural"="beach"];
		relation(around:{radius_m},{lat},{lon})["natural"="beach"];
		"""

	return f"""
	[out:json][timeout:25];
	(
		{parts}
	);
	out center {limit};
	"""

OVERPASS_ENDPOINTS = [
	"https://overpass-api.de/api/interpreter",
	"https://overpass.kumi.systems/api/interpreter",
	"https://overpass.openstreetmap.ru/api/interpreter",
]

async def fetch_overpass(lat, lon, radius_m=60000, want_min=15):
	# Overpass is HTTP, so do it in a thread via asyncio.to_thread to keep UI smooth
	def _http():
		query = overpass_query(lat, lon, radius_m=radius_m, limit=120)
		data = urllib.parse.urlencode({"data": query}).encode("utf-8")

		last_err = None
		for endpoint in OVERPASS_ENDPOINTS:
			for attempt in range(4):
				try:
					req = urllib.request.Request(
						endpoint,
						data=data,
						headers={"User-Agent": "WindsurfFinder/1.0 (contact: none)"}
					)
					with urllib.request.urlopen(req, timeout=60) as resp:
						return json.loads(resp.read().decode("utf-8"))
				except Exception as e:
					last_err = e
					# Exponential backoff: 0.8s, 1.6s, 3.2s, 6.4s
					import time
					time.sleep(0.8 * (2 ** attempt))

		raise last_err

	raw = await asyncio.to_thread(_http)

	results = []
	for el in raw.get("elements", []):
		tags = el.get("tags", {}) or {}

		name = tags.get("name") or tags.get("operator") or tags.get("brand") or "Unnamed spot"

		# Coords: nodes have lat/lon; ways/relations come with center
		if "lat" in el and "lon" in el:
			plat, plon = el["lat"], el["lon"]
		else:
			center = el.get("center")
			if not center:
				continue
			plat, plon = center.get("lat"), center.get("lon")
			if plat is None or plon is None:
				continue

		dist_km = haversine_km(lat, lon, plat, plon)

		# Score: prefer explicit windsurf tags, then sports centers, then beaches
		score = 0
		if tags.get("sport") == "windsurfing":
			score += 100
		if "windsurf" in (tags.get("sport") or ""):
			score += 80
		if tags.get("leisure") == "sports_centre":
			score += 40
		if tags.get("natural") == "beach":
			score += 20
		if tags.get("name"):
			score += 10

		results.append({
			"name": name,
			"lat": float(plat),
			"lon": float(plon),
			"dist_km": float(dist_km),
			"score": score,
			"tags": tags,
		})

	# De-dupe by rounded coords + name
	seen = set()
	unique = []
	for r in sorted(results, key=lambda x: (-x["score"], x["dist_km"])):
		key = (r["name"].lower(), round(r["lat"], 5), round(r["lon"], 5))
		if key in seen:
			continue
		seen.add(key)
		unique.append(r)

	# If we still don't have 15, expand radius
	if len(unique) < want_min and radius_m < 200_000:
		return await fetch_overpass(lat, lon, radius_m=radius_m * 2, want_min=want_min)

