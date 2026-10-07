# DFW Conspicuity Audit — design spec

Date: 2026-10-06
Status: draft for review
Working name: **DFW Conspicuity Audit** (repo `dfw-conspicuity-audit`)

## 1. What this is, in one paragraph

An open, reproducible audit of what public cooperative surveillance (ADS-B and
related feeds) does and does not see in the lowest 1,200 ft of airspace over
Zipline's FAA-published Dallas–Fort Worth operating area. It answers five
fixed questions with measured numbers, shows its instrument's blind spots
before it shows any result, and ships as a short field report plus an
interactive map, with the full pipeline and data extract in a public repo.

It is not a collision-risk estimate, not a tracker of Zipline aircraft, and
not affiliated with Zipline.

## 2. Why this project

### Purpose

Show Zipline's team that the author studied their actual operating
constraints and can do careful, honest measurement work on a question the
team already asks. Secondary purpose: leave behind a public artifact that is
independently citable.

### Why this question

Zipline's own filings put electronic conspicuity at the centre of how its
aircraft share airspace:

- Its Part 108 comment (2025-10-06) asks the FAA to require all crewed
  aircraft to carry ADS-B Out or an equivalent device, and to remove the
  requirement for drones to detect non-cooperative aircraft (p.11). It
  recommends each drone carry an ADS-B In receiver on 978 and 1090 MHz (p.12).
- Its Texas Metros Draft EA (2026-09-11) lists "use of its onboard ADS-B
  detect and avoid ('DAA') system" first among its deconfliction measures
  (p.15).
- Its exemption (No. 19111F, 2026-05-27) requires it to avoid "known areas
  with increased aviation activity", stay 3 NM from public-use runways unless
  mitigated, and report monthly every crewed-aircraft encounter within
  2,000 ft horizontally and 250 ft vertically.
- It posted a Director of Airspace Policy role (2026-09-17) covering
  "detection and avoidance of cooperative and non-cooperative crewed
  aircraft" and electronic conspicuity. (Quote via a job-board summary;
  re-check before repeating to Zipline.)

How much low-altitude traffic actually broadcasts, where, and what a
broadcast-only picture misses is therefore the empirical question underneath
Zipline's regulatory position. No public, reproducible answer exists for any
drone-delivery operating area; the main public tracker (DroneXL) lists
crewed-traffic interaction as missing.

### Zipline's point of view, candidly

| Reader | Useful? | Why |
|---|---|---|
| Airspace policy / regulatory | Most useful | Independent, public, reproducible evidence on electronic conspicuity that a third party produced. Zipline cannot easily publish fleet data; it can cite or point to this. |
| Flight Test | Method resonates, data is not new | The work mirrors the job: Python/SQL over track logs, instrument characterisation, anomaly hunting, honest error bars. |
| Autonomy / DAA | Mildly interesting | The "what is left away from airports" characterisation is their problem, but they have ADS-B In logs from every flight. |
| CTO | Cool if rigorous | A specific question from their filings, answered with stated limits. |

Zipline has better data than any outsider. The value is the public,
reproducible form and the demonstration of judgement, not new information.
The spec is built around what their engineers would attack first: altitude
error against a 330 ft band, receiver coverage near the ground, airport
pattern traffic swamping counts, and UAT aircraft. Each has a named control
in section 6.

Note for the author: "Applications" at Zipline is ground-systems deployment
and construction (civil, mechanical, electrical), per the internship posting.
This project fits Flight Test and airspace roles, not Applications.

## 3. The five questions

Every number on the site comes from one of these. Results are whatever the
pipeline produces; none are assumed here.

**Q1 — Where is broadcasting mandatory?**
What share of the DFW operating area lies inside the DFW Mode C veil, where
ADS-B Out is required from the surface (14 CFR 91.225), and what share lies
outside it, where it is not required at low altitude? Pure geometry.
(Back-of-envelope: a 30 NM veil is about 3,740 sq mi against a 10,904 sq mi
box, so roughly a third inside. To be computed from the FAA polygons.)

**Q2 — How low can the instrument see?**
For each map cell, what is the lowest height above ground at which the
receiver network ever reported an airborne aircraft during the study window?
This is the coverage floor. Cells with a floor above the band of interest are
marked "not observable" and excluded from Q3–Q5.

**Q3 — Who is down low, where and when?**
Observed crewed-aircraft time in two bands, per cell and hour of day:
- the cruise-adjacent band, 80–580 ft AGL (330 ft cruise ± the 250 ft
  vertical distance in Zipline's own encounter-reporting condition);
- the wider low band, surface–1,200 ft AGL.
Broken down by aircraft class (rotorcraft, light fixed-wing, large
fixed-wing, other) and day type (weekday, weekend).

**Q4 — What does the runway stand-off remove, and what is left?**
What share of observed low-band traffic time falls within 3 NM of a
public-use runway (the stand-off in exemption condition 18b)? Of the
remainder, what is it: which aircraft classes, near which heliports
(57 hospital pads are flagged in FAA data for the wider bbox), at what hours?

**Q5 — What does a broadcast-only picture miss, at minimum?**
Share of observed low-band traffic time that arrived by a route other than
direct 1090 MHz ADS-B, inside versus outside the veil:
- MLAT (Mode S transponder, no ADS-B position): invisible to ADS-B In.
- ADS-R (UAT aircraft rebroadcast): visible on 978 MHz, not 1090 MHz.
- TIS-B (radar-derived targets).
This is a lower bound. Aircraft with no transponder, and anything below the
coverage floor, cannot be counted at all, and the site says so beside the
number.

## 4. Non-goals

- No collision probability, risk ratio, or "encounter rate" headline. The
  metric is observed traffic exposure.
- No claims about Zipline's DAA performance, and no assertion about acoustic
  DAA (no 2025–2026 primary source confirms its status).
- No tracking, identification or mapping of Zipline aircraft, sites or staff.
- No simulated Zipline flights. Site locations are not public.
- No Texas metros (Houston, Austin, San Antonio, Amarillo, El Paso). Their
  approval is pending and their boundaries are published only as pictures.
- No noise analysis.
- No LAANC / UAS Facility Map layer. Those ceilings are Part 107 processing
  thresholds and do not describe how Zipline operates.
- No live data and no backend.

## 5. Data sources

All verified live on 2026-10-06 unless noted.

| Layer | Source | Terms | Notes |
|---|---|---|---|
| Operating area | DFW Final EA, p.10 footnote 12: four corner coordinates | US federal document | One longitude is printed without its decimal point ("-95924358"); use -95.924358 and flag the correction. Check computed area against the stated 10,904 sq mi. |
| Aircraft tracks | adsb.lol `globe_history_2026` daily releases (GitHub) | ODbL 1.0 | About 3.9 GB per day, split tar of per-aircraft gzip JSON traces. Fields include baro and geometric altitude, source type, emitter category, type code. |
| Mode C veil, Class B/D surface areas | FAA `Class_Airspace` feature service | "for public use" | 27 features for the area after filtering. |
| Airports, runways, heliports | FAA NASR 28-day subscription, APT CSVs (2026-10-01 cycle) | FAA product | Has public/private use and a medical-use flag. |
| Terrain | USGS 3DEP elevation service | Public domain | Sampled at build time; no terrain shipped to the browser. |
| Geoid | NOAA GEOID18 | Public domain | About -27 m at DFW. |
| Surface pressure | Hourly METARs for area airports | Public | For barometric correction. |
| Basemap | OpenFreeMap | No key, attribution required | Carto now requires an API key and is excluded. |

Study window: seven consecutive days, Monday 2026-09-28 through Sunday
2026-10-04. Build and validate on one day first.

Sources rejected for licensing: OpenSky (no redistribution outside the
institution), ADS-B Exchange (internal business use only), adsb.fi and
airplanes.live (personal, non-commercial).

## 6. Method and controls

### Height above ground

1. Prefer geometric altitude: ellipsoid height, corrected by the geoid, minus
   terrain elevation.
2. Fall back to barometric altitude corrected with the nearest hourly
   altimeter setting, minus terrain.
3. **Calibration:** compare computed height for aircraft reporting "on
   ground" and at touchdown against known runway elevations. Publish the
   residual distribution. A live probe found geometric-minus-barometric
   differences larger than the geoid alone explains, so some avionics may
   report MSL; the calibration decides the correction, not an assumption.
4. **Sensitivity:** every band statistic is reported at the nominal bounds
   and with the bounds shifted ±100 ft. A finding that flips under that shift
   is reported as inconclusive.

### Traffic time

- Integrate time between consecutive trace points of one aircraft; cap any
  gap at 30 s so coverage drop-outs are not counted as presence.
- Report aircraft-seconds per km² per hour and distinct aircraft counts.
  Cells with fewer than a stated minimum of distinct aircraft are shown as
  "too few observations", not as zero.

### Zones

Each point is tagged: inside the operating area; inside the Mode C veil;
within 3 NM of a public-use runway; inside a Class B or D surface area;
H3 cell (resolution 7, about 5 km²).

### Controls for the predictable objections

| Objection | Control |
|---|---|
| Altitude error is as big as the band | Calibration residuals published; ±100 ft sensitivity on every band figure. |
| Receivers cannot see near the ground | Q2 coverage floor is shown first and gates Q3–Q5. |
| Counts are just airport traffic patterns | Q4 separates traffic within 3 NM of runways from the rest. |
| UAT aircraft are under-represented | ADS-R reported as its own category; stated as a known undercount. |
| Absence of data read as absence of aircraft | Unobservable cells drawn hatched; every figure carries its lower-bound label. |
| One odd week | Window dates on every figure; weekday and weekend reported separately; pipeline re-runnable on any dates. |

### Pre-committed fallback

If the coverage floor shows the network cannot observe the cruise-adjacent
band over most of the operating area, that is the headline finding. Q3–Q5 are
then reported only for observable cells, with the observable share stated.
The project is still publishable in that form.

### Privacy

- The published web payload uses per-day anonymous track IDs, with no
  registrations or hex codes.
- Aircraft flagged in the feed as privacy-listed (LADD, PIA) or military are
  counted in aggregates and omitted from the track replay.
- The repo documents how to rebuild the raw extract from the source; it does
  not need to host identifiers.

## 7. What gets built

### 7.1 Pipeline (Python)

Each unit has one job and a file-based interface, so it can be tested alone.

| Unit | Does | In → out |
|---|---|---|
| `fetch_tracks` | Streams one day's archive, keeps points inside the operating-area bbox | release URL → `raw/YYYY-MM-DD.parquet` |
| `fetch_layers` | Pulls FAA airspace and NASR airport data, builds the operating-area polygon | URLs → `layers/*.geojson` |
| `altitude` | Computes height above ground and runs calibration | raw + terrain + METAR → `agl/*.parquet`, `calibration.json` |
| `classify` | Aircraft class and surveillance-source class per point | agl → same, with two columns |
| `zones` | Tags veil, runway stand-off, surface areas, H3 cell | classified + layers → `tagged/*.parquet` |
| `metrics` | Answers Q1–Q5 | tagged → `findings.json`, `cells.parquet` |
| `export_web` | Writes compact payloads for the site | metrics + one day of low tracks → `web/public/data/*` |

One command, `make all DATES=...`, reproduces everything from sources.

### 7.2 Site

A static single page, in two parts.

**Part one — the field report.** A scrolling page with:
1. Title, one-sentence statement of what it is, the "independent, not
   affiliated" line, study window.
2. "What this instrument can and cannot see" — the coverage-floor map and the
   lower-bound statement, before any result.
3. Five short sections, one per question: the number, one figure, two or
   three sentences, and the caveat that applies.
4. Method summary with the calibration plot and a link to the full methods
   file.
5. Sources, with page-level links into the FAA documents.

**Part two — the explorer.** A full-width map:
- Layers: operating area, Mode C veil, Class B/D surface areas, public-use
  runways with 3 NM rings, heliports (hospital pads distinguished).
- Cell colouring switchable between traffic time in band, coverage floor, and
  non-ADS-B share.
- Hour-of-day histogram that filters the map when brushed.
- Click a cell: a vertical profile (histogram of observed height above
  ground) with reference lines at 330, 400 and 500 ft, plus the class
  breakdown.
- Replay of one sample day of tracks below 1,500 ft AGL, with a scrubber.

### 7.3 Visual style

The page should read as a flight-test report crossed with an aeronautical
chart, not a dashboard or a marketing page.

- **Tone:** plain, measured, numbers with units and dates. No exclamation, no
  superlatives, no "risk" or "danger" language.
- **Background and ink:** warm off-white paper, near-black navy text.
- **Chart colours:** magenta and blue for airspace boundaries, following
  sectional-chart convention; one sequential scale for traffic time; a single
  distinct hue reserved for "not broadcast"; grey hatching for unobservable.
- **Type:** a humanist sans for prose, a monospace for every number, label
  and coordinate.
- **Figures:** thin rules, direct labels, no legends where a label will do,
  the study window and sample size printed under each figure.
- **Branding:** none of Zipline's name styling, logo, colours or imagery.
  "Zipline" appears only as a plain-text reference to the public filings.

### 7.4 Stack

- Pipeline: Python 3.12, polars or DuckDB, shapely/pyproj, rasterio, h3,
  pytest.
- Site: Vite, TypeScript, MapLibre GL, deck.gl (H3 cells, paths, replay),
  Observable Plot for charts.
- Hosting: GitHub Pages or any static host. Payload budget: under 2 MB to
  first interactive view, replay tracks lazy-loaded and under 5 MB.

### 7.5 Repo contents

`README.md` (what it is, findings, how to reproduce), `METHODS.md` (every
definition and correction), `LIMITS.md` (what cannot be concluded),
`pipeline/`, `web/`, `data/` (derived tables under ODbL with adsb.lol
attribution), licence files (code MIT, data ODbL).

## 8. Testing and acceptance

**Unit tests (synthetic inputs):**
- Height conversion for geometric and barometric paths against hand-computed
  cases.
- Time integration, including the 30 s gap cap.
- Zone tagging at boundaries (veil edge, 3 NM ring, box corner).
- Class and source-type mapping tables.

**Data checks (real inputs):**
- Operating-area polygon area within 0.5% of 10,904 sq mi.
- On-ground reports within a stated tolerance of terrain after calibration.
- Airport and heliport counts consistent with the FAA file for the cycle.
- Totals reconcile: band time by class sums to band time by zone.

**Acceptance:**
- `make all` reproduces `findings.json` from sources on a clean machine.
- Every number on the site is read from `findings.json`, none typed by hand.
- Each figure states window, sample size and its caveat.
- An independent review pass finds no claim that goes beyond section 3.

## 9. Build plan

| Phase | Outcome | Rough effort |
|---|---|---|
| 1. Ground truth | Operating-area polygon, FAA layers, Q1 answered | half a day |
| 2. One day of tracks | Fetch and filter one day; raw extract in hand | half a day |
| 3. Altitude | Height above ground, calibration plot, go/no-go on altitude quality | 1 day |
| 4. Metrics | Zones, Q2–Q5 on one day, tests passing | 1 day |
| 5. Full window | Seven days processed, sensitivity runs, findings frozen | half a day |
| 6. Site | Field report and explorer | 1.5 days |
| 7. Review and write-up | Independent check of claims, README/METHODS/LIMITS, the note | half a day |

About five to six focused days. Phase 3 is the real gate: if altitude cannot
be calibrated to roughly ±100 ft, the bands widen and the report says so.

## 10. Sharing

- **Private first.** Send the link to the team before posting publicly, and
  say so. Public posting follows only after that, and not before the Texas
  comment period closes on 2026-10-11.
- **Watch the rule.** The Part 108 final rule was reported in White House
  review through about 2026-10-08. If it publishes before sending, add one
  line on what it decided about electronic conspicuity.
- **The note** (three or four sentences): what was studied and why it came
  from their filings; the single most interesting measured result with its
  caveat; the biggest limitation; one genuine question for them (for example,
  how the public coverage floor compares with what their own receivers see).
  State plainly that it is independent and uses only public data.
- **Do not** imply they missed something, quote their staff from secondary
  sources, or attach numbers to the pending Texas metros.

## 11. Risks

| Risk | Handling |
|---|---|
| Result is quoted as "drones face X hidden aircraft" | Neutral metric names, lower-bound labels on every figure, private-first sharing, `LIMITS.md`. |
| Altitude quality too poor for a 250 ft band | Phase 3 gate; widen bands and report the achieved accuracy. |
| Coverage too thin outside the urban core | Pre-committed fallback in section 6. |
| adsb.lol archive layout or availability changes | Pin release tags; keep the derived extract in the repo. |
| Looks like tracking individuals | No identifiers published; privacy-listed aircraft excluded from replay. |
| Reads as naive next to Zipline's internal data | Say so first; frame as public, reproducible evidence and ask a question. |

## 12. Open items to verify during the build

- That DFW is listed in 14 CFR 91 appendix D (the FAA data does carry a DFW
  Mode C veil polygon, which is what the pipeline uses).
- The exact service rules for TIS-B and ADS-R, before describing what an
  ADS-B In receiver would or would not receive.
- That ASTM F3442's current edition keeps the 2,000 ft / 250 ft volume. The
  spec relies on the exemption's own 250 ft figure, so this is context only.
- Zipline quotes that reached this research through summaries (job postings,
  podcast, trade press) must be re-read at source before being repeated.

## 13. Sources

FAA and regulatory:
- DFW Final EA: https://www.faa.gov/uas/advanced_operations/nepa_and_drones/20251223_Zipline_Final_DFW_EA_508_signed.pdf
- DFW FONSI/ROD: https://www.faa.gov/uas/advanced_operations/nepa_and_drones/20251223_Zipline_DFW_EA_FONSI-ROD_signed.pdf
- Texas Metros Draft EA: https://www.faa.gov/uas/advanced_operations/nepa_and_drones/20260911_Zipline_Texas_Metros_Draft_EA_CLEAN_ADA_Signed.pdf
- Exemption No. 19111F: https://downloads.regulations.gov/FAA-2020-0499-0060/attachment_1.pdf
- September 2026 petition: https://downloads.regulations.gov/FAA-2020-0499-0062/attachment_1.pdf
- Zipline Part 108 comment (2025-10-06): https://downloads.regulations.gov/FAA-2025-1908-2767/attachment_1.pdf
- Zipline Part 108 comment (2026-02-11): https://downloads.regulations.gov/FAA-2025-1908-3843/attachment_1.pdf
- FAA drone environmental review index: https://www.faa.gov/uas/advanced_operations/nepa_and_drones

Data:
- adsb.lol history: https://github.com/adsblol/globe_history_2026
- FAA Class Airspace service: https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/Class_Airspace/FeatureServer/0
- FAA NASR subscription: https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/
- USGS 3DEP elevation: https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer
- OpenFreeMap: https://openfreemap.org/

Context:
- DroneXL Zipline tracker: https://dronexl.co/tracker/drone-delivery/operators/zipline/
- GAO-26-107648: https://files.gao.gov/reports/GAO-26-107648/index.html
- MIT LL low-altitude encounter models (Weinert et al.): https://arxiv.org/abs/2103.04753
- Senior Flight Test Engineer posting: https://jobs.techstars.com/companies/zipline/jobs/86978899-senior-flight-test-engineer
- Applications Engineer Intern posting: https://www.builtinsf.com/job/applications-engineer-intern-fall-2026/9653536
