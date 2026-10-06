# DFW Low-Altitude Surveillance Survey

How much of the low-altitude air traffic over Dallas–Fort Worth broadcasts its position, and how much of that a public receiver network can actually hear. Measured over the operating area published in the FAA's Dallas–Fort Worth environmental assessment for Zipline, from the surface to 1,200 ft above the ground.

Based on public data only.

## Findings

<!-- findings:start -->
- Window: 2026-09-28 to 2026-10-04 (UTC archive days), 168 hours.
- Operating area: 10894 sq mi computed, 10904 stated in the assessment.
- Broadcasting is required below 1,200 ft over 34.4% of the area.
- The feed heard at least three aircraft below 580 ft in 9.7% of map cells, and below 1,200 ft in 50.1%.
- At 22 of 44 airports with enough traffic to check, most arrivals and departures were heard to within 100 ft of the ground.
- On average 2.6 crewed aircraft were in the 80–580 ft band and 7.6 below 1,200 ft, over the whole area.
- 81.8% of that low time was within 3 NM of a public-use runway.
- A receiver on 1090 MHz alone would miss at least 7.2% of observed low time; one on both bands at least 0.5%.
<!-- findings:end -->

These lines are written by the pipeline from `web/public/data/findings.json`. The site reads the same file; no number on it is typed by hand.

## What is on the site

- A map of low traffic, of how low the feed hears, and of traffic not on 1090 MHz, filtered by altitude band, aircraft class, and hour of day.
- A 10-mile brief for any point you click: traffic, nearby runways and heliports, how much of the circle is inside the runway stand-off and the Mode C veil, and how well the feed hears there.
- Five findings with their caveats, the busiest areas away from public runways, the airport reception check, and the height calibration.

## Reproduce

```sh
python3 -m venv .venv && .venv/bin/pip install polars pyarrow numpy shapely pyproj rasterio h3 orjson pytest
make layers     # FAA airspace and airports, terrain, geoid, METARs
make all        # downloads seven adsb.lol daily archives (about 4 GB each, deleted after use)
make test
cd web && yarn install && yarn build
```

`make all` takes other dates: `.venv/bin/python -m survey.run --dates 2026-10-05 2026-10-06`. After the first run, `--from-raw` skips the downloads and `--from-prepared` skips the height and zone step.

## Layout

- `pipeline/survey/` — one module per step: `fetch_tracks`, `fetch_layers`, `prepare` (height, zones, time), `reception`, `hotspots`, `metrics`, `export_web`.
- `pipeline/tests/` — unit tests on synthetic tracks.
- `web/` — the static site (Vite, MapLibre, deck.gl).
- `METHODS.md` — every definition. `LIMITS.md` — what the numbers do not mean.

## Licence

Code is MIT. Aggregates derived from adsb.lol are under the Open Database License, with attribution to adsb.lol and its feeders. The published files hold no aircraft addresses, registrations, or hex codes.
