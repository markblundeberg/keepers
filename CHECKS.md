# Checks

The ledger of what has been checked, how, and with what result. Every check
is broken once on purpose, to show it can fail. A check's status is one of:
planned, built, passed, or failed (with what was done about it).

## The transcription

| # | Check | How | Break it once | Status |
|---|---|---|---|---|
| T1 | Every record's `quote` is an exact substring of its source text | automatic, every record (`tools/validate.py`): segments equal the source at their offsets; quotes are found in their segment and re-read from the source file | alter one character in a quote; it must be flagged | built; broken once 27 Oct (caught) |
| T2 | Fields agree with their quote (the wind in the field appears in the quote, and so on) | automatic, every field: copied fields lie inside their quote, weather inside its segment. Only a substring test: the semantic check is the rules-vs-LLM comparison (`tools/compare.py`) and T3 | swap two records' winds | built; broken once 27 Oct (caught) |
| T3 | Field accuracy against the printed page | random sample read on the IA scans by safe-mode vision helpers (`tools/t3_check.py`), every flag adjudicated against the source and, where it matters, by eye on a crop (`tools/crop.py`); report the error rate with an interval | plant known errors in a copy and see the sample catch them | 1887 v1: 15/15 plants caught; 2 extraction errors in 885 fields; see notes/PILOT.md |
| T4 | Completeness: no entries silently dropped | segments: every L.H./L.V. in the text must open a segment (found 40 misses, fixed); observations: bird-like words no quote covers (`tools/validate.py`) | delete a block's records; the comparison must flag it | 1887: built; broken once 27 Oct (caught) |
| T6 | The Gutenberg transcription against a second witness | align each date paragraph with the IA OCR and compare every number; settle same-shaped disagreements on the scan with a helper (`tools/witness.py`), errata in `data/errata.csv` | (the 12.5 vs 12.50 case, found first by T3, had to show up) | 1887: 1,938 of 1,989 numbers agree; 22 settled on scans, Gutenberg wrong once |
| T5 | Dates resolve right (month carried from headings, Old/New Style not an issue in 1880s Britain) | dates non-decreasing through each section and in the month of the heading above them (the reports give no weekdays) | shift one block a month | built; broken once 27 Oct (caught) |

## The stations and their lights (stage 2)

| | What | How | Broken once | Status |
|---|---|---|---|---|
| S1 | Station lists read exactly | text years: every row's fragments exact on their lines, every quoted field inside its row (`tools/station_lists.py check`); OCR years: read twice off the scans, fields inside the row as read, names found (softly) in the OCR | alter a fragment; drop a row | 1,887 rows; both breaks caught; key fields agree 99.8% between readings |
| S2 | No station row missed | rows against the sentence giving the number of stations, the finder's count and an independent count of numbers on the lines; differences reviewed (`data/stations/lists/reviewed.json`) | drop a row (caught as unpaired) | every list accounted for |
| S3 | Names grouped into the right stations | two independent groupings compared pair by pair (`tools/stations.py compare`) | (no break: identical partitions, 441/441 pairs) | 230 stations |
| S4 | Stations matched to the right Findlay rows | two runs per country and edition (450/450 agree); positions 1879 vs 1887 (lighthouses median 0.00 km); coast order along every printed list (no step a mismatch would make); the reports' own 1879-80 words against Findlay 1879 (159/164; the rest reviewed) | (the merge bug showed up as the one disagreement, Oyster Island) | done |
| S5 | Positions | Wikidata picks twice (181/183 agree); pick against Findlay 1887: median 0.19 km, 90% within 0.61 km | | 226 of 230 placed |
| S6 | Character by year | timelines judged twice from Findlay 1879, Edwards 1884, Findlay 1887 and the reports (agree on 'changed' 216/218); drawable patterns read twice (251/259 agree after normalising, 8 decided on the text); the regex parser as a coarse third reading (235/259 on kind and number of lights; its misses are known gaps) | | 217 stations x 9 years |

## The extraction, all nine years (stage 3; notes/EXTRACTION.md)

| | What | How | Broken once | Status |
|---|---|---|---|---|
| X1 | Quotes exact | every quote found in its chunk (`tools/check_obs.py`) | alter a quote (caught) | Gutenberg years all exact; OCR years 17 tidied quotes, flagged in records |
| X2 | Fields copied | count, time, direction inside the quote; wind, force, weather, other dates, specimen inside the chunk; names inside the chunk or flagged context, case and italics aside | swap fields (caught) | 0-34 per year, flagged in `unverified_fields` |
| X3 | Dates agree with their words | ISO date against the copied day, month and year; OCR words mended first (8/3, I/1, Noy.) | shift a date (caught) | 0-11 per year, left blank |
| X4 | Fields against the print | 100 observations per year, half lantern events, read on the scans by vision helpers with planted errors (`tools/t3_v4.py`); each flag classed by two helpers (`tools/t3_review.py`) | planted errors | 115/117 planted caught over nine years; rates: notes/EXTRACTION.md |
| X5 | The second reading helps and harms nothing | merge scored on X4's sample: known errors fixed, confirmed fields changed, read by hand (`tools/review_eval.py <year> v4m`) | (the first, all-fields merge failed it on 1880 and was narrowed) | 1879: 7 fixed, 0 broken; 1880: 3 fixed, 0 broken; other years: notes/EXTRACTION.md |
| X6 | Gutenberg against the print | impossible clock times (minutes 60+) searched in all six texts and read on the scans; T6 (numbers against the OCR) on 1887 | (the 12.50 case) | 4 slips, all 3 read as 8; Tardus for Turdus 5 times; `data/errata.csv` |
| X7 | Dates hang together | the keepers' own entries against the days the committee's summaries call a rush (`tools/rush_check.py`): distinct stations with entries per day, rush days against the other days of those months, permutation test. Not fully independent (the summaries come from the same returns): it tests the chain from text to date | shift the rush days 10 days either way (activity falls to baseline: 6.4 and 7.8) | 50 rush days in 14 months: 15.0 stations per day against 7.4 (p < 0.001) |

## The keepers as instruments

| # | Check | How | Break it once | Status |
|---|---|---|---|---|
| W1 | Keepers' wind directions agree with 20CRv3 10 m winds on the same night and place | `tools/winds.py`, `tools/wind_test.py`: agreement within 45 deg against a same-station null 7-60 days away; the speed-weighted rotation (keeper minus 20CRv3) with a by-date bootstrap, against the gufm1 declination (`tools/declination.py`) | rotate every keeper wind by 40 deg (comes back +40) | passed: 63.6% agree vs null 25.2% (5,064 winds, date ranges left out); rotation +14.3 (light-vessels +18.0, near magnetic +20.1; lighthouses +12.7, mixed); notes/TESTS.md |
| W2 | Lightvessels (at sea) agree better than headland lighthouses | split W1 by station type | shuffle the station types | passed: 68.7% against 61.7% |
| K1 | A known case: strikes concentrate on overcast or foggy, moonless nights | compare strike nights with all observed nights by weather letters and moon phase | unmark half the moonlit strike nights (0.49 -> 0.22); moon of a random 1-29 days away (1.11) | moonless: passed (odds ratio 0.49; calendar nights 3.1% vs 7.9%); overcast: not seen in the reanalysis (1.05 per tenth), keepers' "misty" fragile (+0.26 or +0.07 by outcome); notes/TESTS.md |
| L1 | Fixed lights kill more per watched night than eclipsing ones (modern lit towers) | `tools/light_test.py`: Poisson and negative binomial on station-years, coast x year effects; the 13 lights that changed kind | shuffle kinds among a coast's stations | not seen: fixed lower across stations (0.66-0.71, at the edge of the shuffle), no direction within stations (5 of 13); notes/TESTS.md |
| G2 | A rush travels light to light along a coast within a night (before drawing it) | `tools/great_nights.py`: earliest timed lantern record per station against latitude, night effects | plant 100 min per degree (97 back) | east coast: too few timed nights to test; west coast of England and Wales (added): -2.8 min/deg (-58 to +41), excludes a wave at flight speed; no wave drawn |
| K2 | A station's record follows its keeper more than its light | `tools/keeper_test.py`: change between consecutive years on keeper changed, coast x year effects | triple the records after each change (+0.82 back) | amount written: follows the keeper (+0.29 log, 0.11-0.47); strikes: suggestive; light: not estimable from consecutive years |

## The piece

| # | Check | How | Status |
|---|---|---|---|
| P1 | Every visual mark traces to a record or a reconstruction, and the page says which | a script that walks the page's data and finds each mark's source | planned |
| P2 | Light characters are the recorded 1880s ones, or are labelled modern or unknown | per station, the source of its character | planned |
| P3 | Mark perceives the feeling | show him sketches; his eye decides | planned |
