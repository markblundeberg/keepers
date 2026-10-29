# Stage 4-5 tests, written before running them

Written 29 Oct 2026, before any of these was run on the full data (the wind
test had one smoke run on 1879 alone, 155 winds, reported in CHECKS.md W1;
nothing below was changed after it). Each test says what it measures, what
would count as each answer, and how it can be broken to show it can fail.
Results go below each test, dated, without editing the plan above them.

## W1. Do the keepers' winds agree with the reanalysis, and by which north?

- Data: every distinct printed wind with a single placed station and a
  single day (`tools/winds.py`): the 20CRv3 10 m wind at the printed time
  (Irish clocks on Dublin time), else the day's mean vector.
- Agreement: share within 45 deg, against a null pairing each wind with the
  same station's reanalysis 7-60 days away. Pass: agreement above the
  null's range.
- Rotation: speed-weighted circular mean of keeper minus reanalysis for
  winds of 4 m/s and more; 95% interval by resampling days.
  - Magnetic compass: rotation near the mean of minus the declination
    (gufm1; about +19 to +23 deg on most coasts), and following the
    declination across stations: in a regression of each station's rotation
    on its minus-declination (stations with 30+ winds), a slope near 1.
  - True bearings: rotation near 0, slope near 0.
  - Anything else (a rotation of +10, a slope of 0.5) is reported as it is;
    the reanalysis's own coastal biases and the keepers' mixed practice are
    both possible and not separable here.
- Splits reported whatever they show: light-vessels against lighthouses
  (W2: vessels at sea should agree better, the headlands being sheltered or
  funnelled); printed time against day mean; by coast; by report year.
- Broken once: keeper winds rotated by 40 deg must come back +40.

### Result, 29 Oct 2026 (all nine years; first-reading winds, which the merge never changes)

- 5,367 distinct winds at a single placed station and day (2,337 at a
  printed time). **Agreement: 63.2% within 45 deg (95% 61.6-64.7%)
  against a null of 25.2% (range of 20 draws 24.2-26.2%).** The keepers'
  winds are measurements of the weather the reanalysis reconstructs.
- **Rotation, winds of 4 m/s and more (3,548): +13.8 deg (95% +12.1 to
  +15.6), against +21.1 for a magnetic compass.** Neither pure answer.
- **By station kind:** light-vessels (37 stations, 604 winds) **+17.3 deg
  (+14.7 to +19.8)** against a magnetic +20.1; lighthouses (132 stations,
  2,670 winds) **+12.2 (+10.1 to +14.3)** against +21.9; Heligoland and
  four other land stations +19.1 (+15.0 to +23.1) against +15.3. The five
  light-vessels with 30+ strong winds each sit within 7 deg of their
  magnetic value (Morecambe Bay +14.7, Arklow South +17.2, Coningbeg +20.7,
  Barrels +21.5, Arklow North +22.1).
- **Per station** (33 with 30+ strong winds): from -54 (Cromer) and -48
  (Bell Rock) through near 0 (Sumburgh Head 0.0, Eddystone +0.7, Tuskar
  +2.8) to near or past magnetic (Nash Point +24.9, Inner Farne +27.3,
  Fastnet +32.8). No clean split into two groups. The slope against
  declination is undetermined (-0.64, 95% -2.6 to +5.3): the declination
  varies too little between stations (14-24 deg W) to test it this way.
- Light-vessels agree better than lighthouses (W2): 68.4% against 61.3%.
- **Reading.** The light-vessels look like magnetic compasses, a few
  degrees short (a reanalysis bias of that size near coasts would not
  surprise). The lighthouses are a mixture, of practice or of setting:
  some read true or near it, some magnetic, and a few are far off in a way
  no compass explains (Cromer, Bell Rock), more likely local winds round a
  headland, the reanalysis's 1-degree grid at a coast, or the station's
  record. What this cannot separate: a keeper reading true from a
  magnetic reading bent by local terrain. Whichever, for any analysis that
  uses the keepers' wind directions, a light-vessel's wind should be
  treated as magnetic, and a lighthouse's as of uncertain north, unless
  its own rotation is measured.
- **Corrected later the same day.** Records dated by a range ("Oct. 10th
  to Jan. 3rd", 2,580 primary records) had been compared on their first
  day; they are now left out (tools/winds.py, nights.py, great_nights.py).
  Rerun: 5,064 winds, **agreement 63.6% (61.9-65.1%)** against 25.2%;
  **rotation +14.3 (+12.6 to +15.9)**; light-vessels +18.0 (568 strong
  winds), lighthouses +12.7 (2,528); W2 68.7% against 61.7%; Bell Rock
  drops below 30 strong winds; the others above move by 2 deg or less.
  Nothing in the reading changes.

## K1. Strikes against moon and cloud

- Unit: a station-night with any primary record (the keeper was watching
  and reporting). Outcome: a strike night, any record at the light with
  behaviour struck, dead, caught or round_lantern.
- Moon: lit fraction, and altitude at local midnight (skyfield, DE440s);
  "moonlit" = lit fraction > 0.5 and above the horizon at midnight.
- Cloud: 20CRv3 total cloud cover at the station at local midnight; the
  keepers' own weather letters (o overcast, f fog, m mist, r rain, b clear)
  where printed.
- Expected from the literature (lighthouse kills on overcast, misty,
  moonless nights): strike nights less moonlit and more overcast than other
  reporting nights at the same stations in the same months.
- Analysis: conditional (matched) comparison within station x month;
  logistic regression of strike on moonlit, cloud, rain, with station and
  year x month effects; intervals by resampling nights.
- Null and break: moon taken from 14-15 days away (phase reversed) must
  erase a moon effect; cloud from 7-60 days away must erase a cloud effect.
- Caveats to state: reporting effort varies; a strike night may also be a
  night of more birds overall (a rush), so a second model adds the night's
  number of reporting stations on that coast as a measure of passage.

### Amendment, 29 Oct 2026 (before any K1 or L1 result was computed)

Reading the merged at_light changes showed the outcome above leans on a
field that follows wording, not events. Of 2,766 records of birds killed
(behaviour dead; shot birds have their own word), at_light is true for
1,305: the extraction rule asks whether the text names the lantern, and
"Coningbeg Light-ship, two killed, 9 p.m." or "the list of birds killed at
the Hasbro' L.v." does not. The two readings flip it both ways on the same
records (76 one way, 74 the other). A bird killed at a light station in
these reports was killed at the light. So:

- **Primary outcome (amended):** a strike night has any record of struck,
  dead or round_lantern, whatever at_light says, or caught with at_light
  true (caught alone can be on the rocks or by hand). Column `strike_wide`.
- The registered outcome (`strike`, at_light required) is reported beside
  it. If the two disagree in sign, neither is claimed.

### Result, 29 Oct 2026 (`tools/strike_test.py`; strike_wide, registered `strike` in brackets)

Numbers after the date-range correction (see W1); the first run, with
ranges counted as their first night, gave every effect's odds ratio within
0.02 of these (the nulls moved by up to 0.07), except the keepers' "misty"
(below).

- 13,325 station-nights with reanalysis weather; 2,196 strike nights
  [1,569]. Matched comparisons use the 4,885 nights [4,120] in the 872
  station-months [712] that have both a strike night and another.
- **Moon: strike nights are half as often moonlit.** Within station-month,
  25% of strike nights against 42% of other reporting nights; conditional
  logit **odds ratio 0.49 (model 95% 0.42-0.57; resampling dates
  0.36-0.54)** [0.52 (0.38-0.59)]. With passage and the night's number of
  records added: 0.53 (0.40-0.60) [0.57]. Lighthouses 0.49, light-vessels
  0.48.
- **Cloud (reanalysis): almost nothing.** Means 7.15 against 7.12 tenths;
  odds ratio 1.05 per tenth (1.00-1.15) [1.06], 1.04 (0.99-1.12) with
  passage. **Rain (reanalysis): less on strike nights**, 0.78 (0.60-0.92)
  [0.71].
- **Keepers' own letters** (about 300 nights carry any; 43 station-months
  [45] have both kinds): **misty is fragile.** +0.26 (95% +0.08 to +0.41)
  on strike_wide, but +0.07 (-0.05 to +0.18) on the registered outcome;
  same sign, and only one clear of zero, so not claimed. Overcast, rain,
  blue sky: within noise on both.
- **Nulls.** Cloud of 7-60 days away: 1.03 (erased). The registered moon
  null was mis-specified: the moon of 14-15 days away is the opposite
  phase, so it mirrors the effect (1.84 [1.73], near 1/0.49) instead of
  erasing it. That mirror is what a lunar effect predicts, but it is not a
  null. Added after the first run: the moon of a random 1-29 days later,
  **1.11 (0.97-1.26)** [1.03 (0.89-1.20)]: erased.
- **Broken:** half the moonlit strike nights unmarked; the odds ratio fell
  from 0.49 to 0.22, as it should.
- **Added after the first run: the calendar check.** The odds ratio above
  compares reporting nights; if keepers simply sent in more ordinary
  sightings on bright nights, it would fall without any change in kills.
  Counted over every calendar night of each station-month with a strike:
  strikes on **3.1% of moonlit nights against 7.9% of others**
  (Mantel-Haenszel within station-month **0.37, 95% by resampling stations
  0.33-0.42**) [2.9% against 7.4%, 0.38]. Not a reporting effect.
- **Added: does the moon matter less under overcast?** If moonlight is the
  mechanism it should. It doesn't, on reanalysis cloud: 0.45 under 6
  tenths, 0.41 (0.22-0.77) at 9 tenths or more. Either the reanalysis's
  cloud over one point is too poor a proxy for the sky at the lantern (its
  near-zero cloud effect suggests so), or a full moon brightens even an
  overcast sky enough, or something lunar besides light is at work. Not
  separable here.
- **Reading.** The moon result is large, the same at towers and vessels,
  survives the calendar check and the passage control, and vanishes under
  a decorrelated moon: dark nights killed birds. The overcast half of the
  expectation is not seen: not in the reanalysis (which may say more about
  the reanalysis at a point than about the birds), and not robustly in the
  keepers' own letters.

## L1. Lights as traps: fixed against flashing

- Unit: a station-year with primary records. Outcome: number of strike
  nights (as K1); exposure: nights with any record.
- Light: the character that year (data/stations/characters.csv): fixed
  (steady) against eclipsing (revolving, flashing, group flashing,
  occulting, intermittent).
- Expected: from modern work on lit towers (flashing obstruction lights
  draw fewer birds than steady ones), fixed lights kill more per watched
  night. No direction is assumed for revolving against occulting.
- Analysis: Poisson (or negative binomial) regression of strike nights with
  log exposure, light kind, station type (vessel or tower), coast x year
  effects. The within-station test: the lights whose character changed in
  1879-1887, strike rate per watched night before and after, paired; a sign
  test across stations.
- Broken: shuffle the light kinds among stations within a coast; the
  effect must vanish.
- Caveats: few great nights carry most deaths; the printed reports are the
  editors' extracts; light-vessels and towers differ in height and setting
  as well as light.

### Result, 29 Oct 2026 (`tools/light_test.py`; outcome strike_wide, registered `strike` in brackets)

Numbers after the date-range correction (see W1); the first run differed
by 0.01-0.02 in each ratio.

- 882 station-years of known kind (a year the witnesses can't split counts
  only if both states are of one kind). Raw rates, strike nights per
  watched night: **fixed 12.2% (lighthouses, 79 stations) and 12.9%
  (light-vessels, 9); eclipsing 21.5% (73) and 21.7% (35).**
- **Across stations, fixed lights strike less, not more:** rate ratio fixed
  against eclipsing 0.71 (Poisson, coast x year effects, clustered by
  station; 95% 0.48-1.03) and 0.66 (negative binomial, 0.49-0.90)
  [registered outcome: 0.65 (0.46-0.93) and 0.67 (0.49-0.92)]. Kinds
  shuffled among the stations of a coast, 200 draws: median 0.99, 95% of
  draws 0.65-1.40; 9% of draws as far from 1 as the real one [6%].
- **Within stations, nothing:** 13 lights went between fixed and eclipsing
  in years of known state; the fixed years struck more at 5 of 13 [6 of
  13], sign test p = 0.58 [1.00]. Few stations, few nights on one side at
  most of them: this test can see only a large effect.
- Added after the first run, not planned: tower height (Findlay) as a
  first control for the great lights. The fixed lights are not the lower
  ones (median 110 ft against 101), and the ratio stays 0.68 (0.49-0.95).
- **Reading.** The expectation from modern lit towers (steady lights draw
  more birds) is not borne out. The difference across stations runs the
  other way and is about at the edge of the shuffle's range; the one test
  that holds the place fixed shows no direction. What separates fixed from
  eclipsing stations in 1879-1887 is more than the light: the revolving
  lights were the new, powerful apparatus of the headlands and rocks, the
  fixed ones often older or harbour lights, and the keepers at each wrote
  differently (K2). The apparatus column in Findlay (lens order) would be
  the next control; its notation isn't decoded here yet.

## K2. Keeper or lantern?

- Later, after L1: does a station's record change more with a change of
  keeper (surnames, data/keepers.csv) than with a change of light, with
  coast x year effects? Written out in PLAN.md stage 5.

## Stage 5 tests, written 29 Oct 2026 before running them

### G1. Great nights (descriptive)

- A night's size: the number of stations with a strike night (strike_wide,
  K1 amendment) on that date, over all coasts; beside it the birds recorded
  killed (the sum of count_lo over dead and struck records with a number;
  "many" counts nothing, so this is a floor).
- Ranked list of the top 20, with the coasts involved, the moon, and the
  reanalysis wind at the stations. No test; it is the list the piece draws
  from. Check: the editors' own prose names great nights (e.g. 1886's
  autumn rushes); the top of the list should contain the nights they name,
  read from the general remarks, not chosen to fit.
- The editors' windows, read from the prose chunks (rush, immense,
  enormous, destruction, with a date) before any ranking was computed;
  windows over 9 days left out (1887's "Sept. 29th to Nov. 3d"):
  1882-10-06..08, 1882-10-12..15; 1883-09-21..23, 1883-10-13..14,
  1883-10-28..30; 1884-10-14..20, 1884-10-28, 1884-11-04, 1884-11-11..13;
  1885-10-14..17, 1885-10-22..24, 1885-11-11..12; 1886-10-20..28,
  1886-12-17..24. Check: the share of the top 20 nights inside a window
  (a day either side), against the share of all strike nights of
  September-December 1882-1886 inside one.

### G2. Does a rush travel along the coast within a night?

- The piece's plan says: test before drawing the coast lighting up station
  by station.
- Data: nights with timed lantern records (struck, dead, caught at the
  light, round_lantern; a clock time) at 5 or more stations on the east
  coasts of Great Britain (EAST COAST OF SCOTLAND and EAST COAST OF
  ENGLAND sections). For each station, the earliest such time that night
  (times before noon count as after midnight, +24 h).
- Model: time against latitude with night effects (each night its own
  mean), autumn (Aug-Dec) and spring (Feb-Jun) apart. Report the slope in
  minutes later per degree further south, and the speed it implies.
- Null: times shuffled among a night's stations, 1,000 draws. Interval:
  resampling nights.
- What would count: "a rush travels south in autumn" only if the slope is
  positive (later to the south) beyond the shuffle's 95% and the interval
  excludes 0; then the piece may draw it as a passage. Otherwise the piece
  draws each light at its own printed time and implies no wave. Expected
  physics, for the record: birds fly at 30-60 km/h, so a wave down 8 deg
  of coast (900 km) would take 15-30 hours, longer than a night; arrival
  from across the North Sea broadside would give little slope, or one set
  by the crossing distance (wider in the north). A small or zero slope is
  the likelier answer.
- Broken: add 100 minutes per degree south to every time; the slope must
  come back near 100.

### K2. Keeper or lantern (written in full)

- Unit: consecutive station-years (t-1, t) at the same station, both with
  primary records and a keeper named in data/keepers.csv.
- Keeper changed: no surname in common between the two years' printed
  names (a crude measure: a son succeeding a father counts as no change;
  an assistant named one year and the principal the next counts as one).
  Light changed: the kind (fixed, eclipsing, mixed; L1) differs between two
  years of known state.
- Outcomes, as the change from t-1 to t: |change in log records| (how much
  the keeper writes) and |change in strike nights per watched night|.
- Model: least squares of each outcome on keeper changed and light
  changed, with coast x year effects; standard errors clustered by
  station. Null: keeper-change flags shuffled among the station-years of a
  coast and year, 500 draws.
- Expected: the amount written follows the keeper (a larger change when
  the keeper changes); strikes, if they follow the light, change with it.
  The light changes are few (L1: 13 stations with known states either
  side), so the lantern side may say nothing; say so if it does.
- Broken: triple the records in each year after a keeper change; the
  keeper effect on the first outcome must appear.
- Caveats: the printed report is the editors' extract; a listed reporter is
  not always the principal keeper; deaths come in a few great nights, so
  the strike outcome is noisy.

## Stage 5 results, 29 Oct 2026

### G1. Great nights (`tools/great_nights.py`)

- 1,004 nights with a strike somewhere. The top 20 by stations with a
  strike run from 22 stations (1887-11-10 and 11) down to 10. All but one
  had the moon under half lit at the stations (mean lit 0-43%; 1886-10-05
  at 60%).
- **The ranking reflects the reports as well as the birds.** 9 of the top
  20 are in 1887 and almost all are on the west coast of England and Wales
  and the Irish coast. Those sections print day-by-day entries with dates
  and times; the east coast of England's reports, where the editors place
  most of the great rushes, are mostly species summaries, with fewer dated
  strikes (strike nights 13.3% of its reporting nights, against 44.7% on the
  west coast of England and Wales).
- **Check against the editors:** 5 of the top 20 fall in their windows
  (a day either side), no more than the 22% of all September-December
  1882-86 strike nights that do; but 1887 has no window. Within 1882-86,
  the years the windows cover, **9 of the top 20** (45%, binomial p = 0.017
  against 22%). The editors' great nights are among the keepers' great
  nights, about twice as often as chance.
- Most birds recorded killed in one night (numbers only, a shared count
  once, the printed total where larger than its parts): **1887-10-21, 507
  at 16 stations**, 272 of them at the South Bishop between 11 P.M. and
  2.30 A.M. ("Larks," 146; Starlings, 64; Blackbirds, 38; Thrushes, 24),
  82 at the Eddystone, about 100 at the Maidens. Then 1881-05-01 (197 at
  4; 196 Chiffchaffs at Nash Point, "counted from 1 a.m. to sunrise"), 1887-10-10 (196), 1880-11-03 (186).
- Fixed in the first run before anything was recorded: a count shared by
  several kinds ("135 of these species killed") had been summed once per
  kind, and word counts ("countless numbers") had entered as numbers.

### G2. Does a rush travel along the coast within a night?

- **As registered, it can't be run:** no night has timed lantern records
  at 5 or more stations on the east coasts of Great Britain (at most 3;
  the same layout difference as G1). For the piece, that alone means no
  drawn wave on the east coast.
- Added after that: the one coast with enough, the west coast of England
  and Wales (49.8-55.5 N), autumn: 10 nights, 57 station-nights, a mean
  span of 3.3 deg of latitude. **Slope -2.8 min later per degree further
  south (resampled nights 95% -58 to +41); shuffle null -46 to +39.**
  Broken: 100 min per degree planted, 97 back (+43 to +141).
- **Reading.** No sign of a rush passing light to light. A wave carried
  south at a bird's 40 km/h would put each degree about 170 minutes later;
  the interval excludes that (only a wave faster than about 160 km/h, far
  beyond any flight, would hide in it). The great nights on this coast
  arrive broadside: on 1885-11-08 Langness (Isle of Man) at 20:00 and the
  Eddystone at 21:00, 4 degrees apart, with the stations between them
  later. The piece draws each light at its own printed time and implies
  no wave.

### K2. Keeper or lantern (`tools/keeper_test.py`)

- 481 consecutive station-year pairs with keepers named; the keeper
  changed (no surname in common) in 77.
- **The amount written follows the keeper.** |Change in log records| 0.72
  when the keeper stayed, 0.92 when it changed; with coast x year effects
  **+0.29 (95% +0.11 to +0.47)**; shuffled keeper flags, 500 draws: 95%
  within -0.15 to +0.15, none as large. Broken: records tripled after each
  change gives +0.82, as it should (log 3 = 1.10, diluted by pairs already
  apart).
- **Strikes: suggestive only.** |Change in strike nights per watched
  night| 0.10 against 0.14 (302 pairs with 5+ watched nights both years);
  +0.048 (95% -0.011 to +0.106) with station-clustered errors, though no
  shuffle reached it (the shuffle ignores clustering by station, so the
  model's interval is the one to trust).
- **The lantern side can't be estimated this way:** no pair of
  consecutive years of known state spans a change of light kind. Every
  change falls in a year the witnesses can't split (two rows), so the
  years either side are never adjacent. L1's within-station test is the
  only one there is, and it found no direction.
- **Reading.** A station's record is partly a portrait of its keeper: a
  new name brings a larger change in how much the station reports, beyond
  what the season and the coast's editor explain. Whether the birds
  killed follow the keeper (in what is reported) is not settled here.
