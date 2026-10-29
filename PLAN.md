# Plan

Working title: **Round the Lantern**, a phrase the keepers use again and again.

## What this is

From 1879 to 1887 a British Association committee sent printed schedules to
lighthouses and lightships around Britain and Ireland. The keepers wrote down
the birds that passed, circled the lantern, struck it or died, with the time,
wind, wind force and weather. The committee printed nine annual reports. This
project turns them back into data, checks the keepers as instruments, and
makes a piece from it.

The feeling it's built on: each keeper saw one beam's worth of a migration
crossing a sea, and nobody saw the whole night. The reports, put back
together, let us see it.

## What gets made

1. **The dataset.** Every observation as a row (schema below), with a link to
   the printed page and an exact quote. Released openly, with a datasheet.
2. **The checks.** Were the keepers good instruments? Their winds against the
   20th Century Reanalysis, with a date-shifted null. Do lantern strikes fall
   on overcast, foggy, moonless nights, as modern studies say? (CHECKS.md.)
3. **The piece: a night chart, dawn to dawn.** A dark chart of Britain and
   Ireland with every light flashing its recorded 1880s rhythm.
   - By day: the keepers' flight directions ("S.E. to N.W.") against the wind.
   - At dusk: the lamps come on.
   - At night: entries come due at their lights, in the keepers' printed
     words, with that night's reanalysis wind underneath.
   - On a great night, the coast lights up station by station. Test whether a
     rush really passes light to light before drawing it.
   - An essay alongside: how the scheme ran, what the numbers say and what
     they can't.
   - A roll of the keepers at the end: every name, station and year.

## Tone and look (decided 27 Oct 2026, why in brackets)

- **The piece is about the looking.** Birds are the signal, keepers the
  receivers, the reports the only place the whole message was read.
- **Factual in every mark.** Every flash, mark, arrow and quote is recorded or
  reconstructed, and the page says which. (The warmth is already in the
  sources; adding romance would cover it up.)
- **Keepers as real people, not heroic loners.** Some sent "a very short single
  schedule", others nineteen schedules and a jar of birds.
- **Strikes are usually deaths, so draw them quietly**, as tally marks that
  stay, never as sparkle.
- **Period means only:** night paper, chart linework, the lights' true
  characters, and the keepers' words in period type, not imitation handwriting
  (we only have them in print). No drawn birds.
- **The house:** this is a piece with its own world, so it may leave the house
  style, but it keeps the top line home and an honest credit line (see
  `~/claude-inspo/house-style/README.md`).
- Mark mentioned Pratchett's clacks. The only thing taken from it is the rush
  passing tower to tower, and only if the data show it. The roll of keepers
  predates the mention; the "GNU" resonance stays private.

## Sources (`sources/`, provenance in `sources/MANIFEST.json`)

- Nine reports, all on the Internet Archive (`reportonmigratio{1..9}{1879..1887}harv`).
  Six have clean Project Gutenberg transcriptions (1879, 1880, 1881, 1882,
  1885, 1887); 1883, 1884 and 1886 exist only as OCR.
- Layouts vary by year and section (see `notes/SURVEY.md`):
  - **Species-ordered**, "SEPARATE REPORT ON EACH SPECIES": most English and
    early Scottish sections, 1879–1886. Example: "Gannet, _Sula bassana_.--At
    Spurn L.V., Oct. 1st to 16th, many to S. At Cockle L.V., Oct. 16th,
    several; 25th, fifteen to W."
  - **Station-ordered**: the Irish coast, and the Scottish coasts from 1885.
    Example: "_North Maidens._--October 21st, striking, 9 P.M. to 1 A.M.; wind
    N.W., fresh, two killed."
  - **Diary, by date**: only the 1887 English coasts. Example: "October
    21st.--_Coquet_ L.H., One Woodcock, 10.30 A.M., shot. _Outer Dowsing_
    L.V., 200 Starlings, 11.30 A.M., S.E. to N.W."
- The OCR years misread the small capitals "L.H."/"L.V." as "t.x.", "u.H.",
  "u.u.", "u.n.", and garble fractions ("84 in." for 8½ in.).
- The Gutenberg HTML carries page markers (44–180 per report), so records can
  link to printed pages and from there to the scans.
- The reports' station lists give each light's character, at least in 1879
  ("North Ronaldshay, Orkney; white, flash every 10 seconds"), and name the
  keepers ("Spurn L.H.: Annie Rose Smith and J. B. Smith").
- Heligoland (British until 1890; Gätke's notes) and outlying stations
  (Stevns, Malmö, the Channel Islands) appear too. Keep them, flagged.

## Data model (first draft; revise in stage 1)

`data/records.csv`, one row per observation (station × date × species × event):
- Source: `report_year`, `section`, `layout`, `page`, `quote` (exact source
  substring), `source_offset`.
- Station: `station_id`, `station_raw`.
- Time: `date` (ISO), `date_raw`, `time_raw`, `t_start`, `t_end` (local; part
  of the night when given).
- Bird: `species_raw`, `species_id` (crosswalk), `count_raw`, `count_lo`,
  `count_hi` (null for "great numbers"; also a category: one, few, several,
  many, great numbers, thousands).
- Event: `behaviour`, one of passing, round_lantern, round_station, struck,
  dead, caught, shot, settled, heard, seen, same_as (definitions in
  `tools/prompts/extract_diary_v2.md`); `at_light`; `total` (a printed total
  that the segment breaks down); `count_shared`.
- Direction and weather: `direction_raw`, `from_deg`, `to_deg`, `wind_raw`,
  `wind_deg`, `force_raw`, `force_bft`, `weather_raw`, `weather_codes`
  (Beaufort letters: b c d f g h l m o p q r s t u v w z).
- Flags: `specimen` ("[Leg and wing received.]"), `note`.

Other tables:
- `data/stations.csv`: id, names, type (L.H./L.V.), lat, lon, position source,
  light character by year, keepers by year.
- `data/species.csv`: the Victorian name crosswalk (e.g. "Titlark" → Meadow
  Pipit, "Golden-crested Wren" → Goldcrest, "Solan Goose" → Gannet, "Black
  Crow" → Carrion Crow, "Grey Crow" → Hooded Crow).
- `data/keepers.csv`: name, station, years, from the station lists.

## Stages

0. **Framework**: sources, survey, this plan, the checks ledger. Done 27 Oct.
1. **Pilot on the 1887 English diaries** (the most regular text). Done 27 Oct;
   results and the method decision in `notes/PILOT.md`.
   - Write a deterministic parser and an LLM extractor for the same text and
     compare them.
   - Hand-check a random sample against the page images.
   - Break each check once.
   - Decide the method for the rest. (Expectation: an LLM extractor in
     blocks, run in safe mode, with exact quotes so every field can be
     verified against the source.)
2. **Gazetteer**: stations with coordinates (lightvessels approximate),
   light characters by year from the reports, keepers by year.
3. **Full extraction**: all three layouts and all nine years, through the
   validators, plus a completeness check against an independent count.
4. **Weather and sky**:
   - 20CRv3 10 m winds at each station (PSL THREDDS answers; the 1880s are
     covered).
   - Moon phase and altitude (skyfield).
   - The wind test with its date-shifted null. Measure, don't assume, the
     keepers' compass: fit the rotation that best aligns their winds with
     20CRv3; if they read magnetic bearings it should land near the 1880s
     declination at each station (about 18-25 deg W; from a historical field
     model, not a guess). (Raised by Gemini Argon via Mark, 28 Oct 2026.)
   - The strike test against overcast, fog and moon.
5. **Great nights**: rank by stations and counts; measure whether a rush
   travels down a coast. And the lights as traps: deaths at fixed against
   flashing or occulting lights, and light-vessels against towers, with the
   49 lights whose character changed in 1879-1887 as before-and-after cases
   at the same place (data/stations/characters.csv).
   - Keeper or lantern? (Raised by Gemini Argon via Mark, 28 Oct 2026.) A
     station's record can change because the season differed, the light
     changed, or the keeper changed. Changes of keeper (about 144 of 540
     consecutive named station-years show no surname in common, a crude
     count) and of light (43 of the 49 under named keepers) fall in different
     years at different stations, so a station-year model with station and
     coast-by-year effects (season, and the committee's editor for that
     coast) can try to separate them. Effort measures beyond the names: the
     records per station-year, the schedules filled in (Scottish lists
     1885-87), the returns marks, and the committee's own "Values" (I-VI) for
     each station. Caveats to state with any answer: deaths come in a few
     great nights, so power is low; the printed reports are the editors'
     extracts, not the schedules; a listed reporter is not always the
     principal keeper.
6. **The piece**: sketches as private artifacts for Mark, then the site page,
   the essay, the dataset release and the roll.
7. **Publish**, with Mark's OK: a public `markblundeberg/keepers` repo and
   GitHub Pages at marklundeberg.com/keepers, like driftlet.

## Size (measured on 1887's English diaries; the rest is estimated)

- 65 stations, 228 dates, 1,216 station-day entries (each listing 1–5
  species).
- Per date: median 3, mean 5.3, 90th percentile 12, maximum 65 (21 Oct 1887).
- The whole set is probably around 10,000 station-day entries over
  1,500–2,000 dates, within a factor of two.

## Prior art (27 Oct 2026)

Three searches found no transcription or quantitative reanalysis of the
1879–87 schedules. A 2025 BOU blog post on lighthouse kills cites the reports
but uses later data. The Scottish Ornithologists' Club holds several hundred
original early-1900s schedules, apparently untranscribed. Re-check before
publishing.
