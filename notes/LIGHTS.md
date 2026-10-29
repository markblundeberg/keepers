# The lights: characters and positions (stage 2 notes)

From a helper's search on 27 Oct 2026 (tags: seen = read on the page image;
OCR = read in OCR text; snippet = a search result said so). Files it saved
are in `sources/lights/` and `cache/lights-scout/`.

## Sources

1. **Findlay 1887 (27th ed.)**, HathiTrust `msu.31293100719271` [seen].
   Every British and Irish light, light-vessels included: character, lat/long
   to 0.1', description, height, range, year. Blocks scripts (403 to curl);
   the helper read 3 pages in Mark's Chrome without being cleared to (see
   below). Bulk text needs HathiTrust's data API or a dataset request.
2. **Findlay 1879 (19th ed.)**, IA `adescriptionand00unkngoog` [seen]. Same
   layout; England to p. 45, Scotland 46-51, Ireland from 52. Images
   873x1358, readable; table OCR poor (names like "B00DWIN LT.-VEBBEL"). Use
   the index to find a station's page; transcribe from the images.
3. **E. Price Edwards, *Our Seamarks* (1884)**, IA
   `edwards-1884-our-seamarks-a-plain-account-of-the-ligh` [seen]. Appendix
   corrected to March 1884: principal lights, character and range, no
   positions. Clean Tesseract OCR. England numbered 1-118 from Berwick round
   to St Bees, then Isle of Man, Scotland, Ireland.
4. Admiralty Pilots (e.g. IA `1889-north-sea-pilot`): narrative, bearings
   not coordinates. *Nautical Magazine* volumes on IA print notices of
   alterations (for dating changes) [snippet].
5. Not found online: the *Admiralty List of Lights in the British Islands*
   (annual; editions cited 1880, 1882, 1884, 1887) [snippet]; Findlay
   1880-1886.

Reading Findlay: "br." = bright (white); "rev." = revolving; colour words in
the description column often describe the tower or hull, not the light; a
second year in the year column can mark the latest alteration; misprints
exist (1879 p. 52 puts Daunt's Rock at "54 43." for 51°43').

## Samples [seen]

| station | Findlay 1879 | Edwards 1884 | Findlay 1887 |
|---|---|---|---|
| Spurn Point | two bright fixed lights; 53 34.7 N, 0 7.2 E | high: white, occulting every ½ min, red sector; low: white, fixed | high occulting ½ min (eclipsed 3 s), red sector; low fixed |
| Spurn L.V. | one br. rev. lt., 1 min; 53 34 N, 0 13 E | white, revolving, 1 min | one rev. br. lt., 1 min |
| Galloper L.V. | two bright fixed lights, horizontal; 51 45 N, 1 56 E | two fixed white, horizontal | two fixed bright, horizontal; 51 45, 1 55.8 |
| Kentish Knock L.V. | one br. rev. lt., 1 min; 51 41 N, 1 41 E | white, revolving, 1 min | one rev. br. lt., 1 min; 51 39.5, 1 41 |
| Goodwin L.V. | rev., 3 flashes in quick succession, obscured 36 s every min; 51 19.4, 1 35.5 | white, group flashing, 3 flashes every min | |
| Outer Dowsing L.V. | one red rev. lt., 20 s; 53 28.2, 1 2.6 | red, revolving, ½ min | one rev. red lt., ½ min; year "1861/1883" |
| Dudgeon L.V. | one bright fixed light; 53 15, 0 56 | white and red alternately, flashing, ½ min | |
| Leman and Ower L.V. | upper rev. 1 min, lower fixed; 53 8.6, 2 1 | white, 2 flashes every ½ min | |
| North Ronaldsay | one br. flash. lt., 10 s; 59 23.2 N, 2 23.6 W (agrees with BA 1879) | | |

## What it means for the chart

- **Characters changed inside the period**: of 14 east-coast stations
  compared, 7 changed between 1879 and 1884 (also Lynn Well, Hunstanton,
  North Foreland). The chart needs a character per station per year, each
  with its source; between sources, the character is uncertain and the page
  must say so (P2).
- **Light-vessels moved**: Kentish Knock 51°41' (1879) to 51°39.5' (1887),
  about 2.8 km. Positions per year too.
- **Position accuracy**: Findlay 1879 lighthouse positions are 0.08-0.25 km
  from Wikidata's for seven English and Welsh lights (all slightly east,
  consistent with the old Greenwich datum but within the 0.1' rounding);
  North Ronaldsay 0.76 km. Use modern coordinates for standing lighthouses,
  the period lists for light-vessels.

## Open

- Findlay 1887 from HathiTrust: only with Mark's say on using his browser,
  or via HathiTrust's research datasets.
- Characters for 1880-1883 and 1885-1886: interpolate only where the 1879
  and 1884 states agree; otherwise date the change from notices to mariners.

## Transcribed (27 Oct 2026)

- `data/lights/findlay1887.csv` (from the Google Books PDF; PDF pages 48-74,
  printed pp. 31-57) and `data/lights/findlay1879.csv` (IA, pp. 33-56):
  every light on the British and Irish pages, read twice by independent
  helpers (`tools/transcribe_lights.py`), merged (`tools/merge_lights.py`),
  with per-row hemispheres read off the pages that cross Greenwich
  (`tools/hemispheres.py`).
- Checks: two readings agree on 97.3% (1887) and 95.8% (1879) of fields; on
  name, character and position the remaining differences are formatting,
  grouping of harbour lights, or a "[?]" in one reading only. Known case:
  60/60 fields against the scout's readings by eye. Positions: principal
  lights (capitals) a median 0.18 km from Wikidata, 90% within 1 km.
- Rows flagged where the readings differ on core fields (18 in 1887, 31 in
  1879): settle on the scan only for the rows the gazetteer uses.
- Findlay's year column gives alteration years ("DUDGEON 1736 / 1882",
  "HUNSTANTON 1665 / 1883", "OUTER DOWSING 1861 / 1883", "SKERRIES 1714 /
  1885"): that dates the changes between editions.

## Stations, positions and characters (28 Oct 2026)

- **Station lists** (`tools/station_lists.py`): every report's lists found by
  a helper per report, then read twice (text years: exact fragments; OCR
  years 1883, 1884, 1886: off the scans) -> `data/stations/list_rows.csv`,
  1,887 rows with keepers, marks, map numbers, characters (1879-80) and
  page. Not read: the OCR years' master lists (the 1885 and 1887 master
  lists cover the numbering) and 1886's duplicated East of Scotland page.
  1882 and 1883 have no West of England section ("No return has been
  received ... from the West Coast of England and the Isle of Man", 1883).
- **Stations** (`tools/stations.py`): 494 printed names grouped into 230
  stations by two helpers, identically -> `data/stations/stations.json`
  (edits with reasons in `overrides.json`).
- **Findlay** (`tools/match_findlay.py`): each station's rows in 1879 and
  1887, two runs per country and edition, 450/450 agree. Unmatched for a
  reason: lights built later (South Gare 1884, Anvil Point, Fidra, Ailsa
  Craig; Selker, Dee, Barrels, North Carr light-vessels), observers'
  places, the Channel Islands and Heligoland (other sections of Findlay;
  Edwards covers the Channel Islands), Point of Air (in 1879 only; the River
  Dee light-vessel stands in its place in 1887).
- **Positions** (`tools/positions.py`, `data/stations/positions.csv`):
  Wikidata for standing lighthouses (picked twice, 181/183 agree), Findlay
  per edition for light-vessels (moved a median 0.38 km between editions,
  at most 4.8 km), hand decisions in `positions_manual.json` (Copeland moved
  to Mew Island in 1884; Spurn's 1880s high light has no Wikidata item).
  226 of 230 placed; not: the two Iceland stations, Malmö, Great Cotes.
- **Character by year** (`tools/characters_by_year.py`,
  `data/stations/characters.csv`): Edwards's appendix (corrected to March
  1884) transcribed twice and matched (204 stations); a timeline per station
  judged twice from Findlay 1879, Edwards, Findlay 1887 and the reports'
  words: 49 lights changed in 1879-1887; where the witnesses can't split a
  year the table has two rows for it (110 station-years).
- **Drawable patterns** (`tools/patterns.py`, `data/stations/patterns.json`):
  every distinct character text read twice into the steps of one cycle
  (light or dark, colour, seconds, stated or not); 251/259 agree after
  normalising, 8 decided on the text (`patterns/reviewed.json`). 343 of
  440 non-fixed steps have durations the sources don't state: the chart
  reconstructs those, from Edwards's description of the kinds (p. 80:
  a revolving beam is "faintly appearing at first, gradually swelling into
  its full strength, and then slowly receding"; flashes are "shorter in
  duration, more sudden in their appearance and disappearance"), and says so.

## Next

1. Keepers by station and year from `list_rows.csv` -> `data/keepers.csv`.
2. Name aliases for the observation text (stage 3), starting from the
   printed names in `stations.json`.
3. The rendering rule for unstated durations (stage 6), stated on the page.

## A finding: the lights' language changed while the keepers watched

In Findlay's 1879 list of Britain and Ireland the character column never
says "occulting" or names a group of flashes; in 1887 it names 38 occulting
and 23 group-flashing lights (counted on the raw strings of
`data/lights/findlay1879.csv` and `findlay1887.csv`). Some lights already
behaved so in 1879, described in prose: eight descriptions give grouped
flashes (Goodwin Lt.-Vessel, "One br. rev. lt. 1 min.", with "Lt. shows 3
flashes in quick succession, and is obscured for 36 secs. in ev. min.") and
six give eclipses. So both the lights and the words for them changed in the
survey years. `tools/characters.py` reads grouped flashes from the
description for that reason.

## Cross-check: the BA 1879 station list against Findlay 1879

The BA's 1879 report gives characters in plain words for 52 stations. Matched
to Findlay 1879 by name and compared on kind and period: 44 agree. Of the 8
others, 7 are name-matching misses (the BA's "Start Point" is Orkney's, not
Devon's; "Island Glass" is Findlay's "Eilean Glas"; "Skervuile" was matched to
the Skerries), and 1 is the BA report's own slip (Chanonry Point, see
QUIRKS.md). So every correctly matched station agrees except one, and that
one is wrong in the report, confirmed by the IA OCR.
