# The extraction: all nine reports (stage 3 notes)

Stage 3 of PLAN.md, 28-29 Oct 2026. How every observation in the nine
reports (1879-1887) became a record with an exact quote, a page and a scan,
what each check found, and what the records can and cannot be trusted for.
The method was settled on the 1887 diaries (notes/PILOT.md); this note is
what changed when it met the other eight years.

## The texts

| year | text read | sections | chunks |
|---|---|---|---|
| 1879 | Gutenberg #65621 | 27 | 84 |
| 1880 | Gutenberg #65411 | 35 | 217 |
| 1881 | Gutenberg #65471 | 31 | 172 |
| 1882 | Gutenberg #65515 | 27 | 167 |
| 1883 | IA OCR (no transcription exists) | 33 | 220 |
| 1884 | IA OCR | 54 | 331 |
| 1885 | Gutenberg #65840 | 41 | 288 |
| 1886 | IA OCR | 38 | 296 |
| 1887 | Gutenberg #66152 | 33 | 293 |

In the OCR years the quote is the OCR's text exactly, garbles and all
("Farn t.x.", "§.W.", "Turpus Viscivorus"); what the print says is for the
scan, and every record links to its scan.

## Pipeline

| step | tool | what it does |
|---|---|---|
| sections | `tools/sections.py` | each report cut into sections by its headings, each with a layout (diary, station letters, species accounts, prose, table, station list) and a role (primary observations or the committee's summary); `data/sections/<year>.json` |
| chunks | `tools/chunks.py` | sections cut at paragraph breaks into chunks of about 1,400 characters, each with the 700 characters before it as context; offsets into the source checked exactly; `data/chunks/<year>.jsonl` |
| first reading | `tools/extract.py`, prompt `tools/prompts/extract_v4.md` (v4.1) | Opus 5.5, effort high, safe mode, no tools, a JSON schema; about four chunks per call; every field copied exactly from the chunk (station, date and species may come from the context, flagged); the date also read as an ISO date |
| second reading | `tools/second_reading.py run` | the chunks of primary sections that mention the light, the lantern, striking, killing or catching (1,393 of 2,068) read again, one per call, same prompt, cached apart |
| disputes | `tools/second_reading.py diff` | the two readings' observations paired one to one; each field compared after setting aside wording that changes no value ("at 3 p.m." and "3 p.m.") |
| adjudication | `tools/second_reading.py adjudicate` | a third reader decides only the disputes (reading 1, reading 2, or neither with a copied value) and whether each observation only one reading has is real; the merge is built from its decisions, so a field both readings agree on cannot change |
| records | `tools/records.py` | one row per observation: the copied words beside values computed by fixed rules (`tools/normalize.py`, `tools/rules.py`), page and scan link, the station and species tables joined, headings carried forward where a heading governs (see below); `data/records.csv` |

### Rules that came from the data

- **Headings beyond the context.** A station, date or species heading can
  stand further back than a chunk's context. Within a section, a null field
  takes the last value only where a heading governs what follows: the date
  in diaries; the station in diaries, station letters and tables; the
  species in species accounts; Heligoland's section is Heligoland. The
  record says so in `carried`. (Carrying everything everywhere filled 23% of
  records, many wrongly: an undated remark in a letter is undated.)
- **Dates.** The model's ISO date is kept only where it agrees with the
  copied words (day, month where named, year where printed). In OCR years the
  words are mended first: 3 read as 8 ("Noy. 8rd"), 1 as I ("Ist"), Nov. as
  "Noy.".
- **Winds.** A single point; two points ("E. to S.E.", "S.E. and S.") by
  their circular mean; a shifting wind by its first point; quadrant words
  ("westerly"); in OCR years § and 8 read as S, H as E. `wind_how` says
  which. Force from the force field or the wind words ("strong").
- **Times.** The print writes one-digit minutes: "9.5 a.m." is 9.05 (the
  OCR agrees). "12 P.M." is flagged as ambiguous, not guessed.
- **Gutenberg slips.** Quotes stay exactly as Gutenberg has them; where the
  print differs (read on the scan), `data/errata.csv` holds the print's
  words and records.py reads the value from them (column `errata`).

## Checks

| check | what | result |
|---|---|---|
| T1 | every quote an exact copy of its chunk | Gutenberg years: all; OCR years 1883 8, 1884 2, 1886 7 quotes where the model tidied the OCR (kept, flagged in `unverified_fields`) |
| T2 | every copied field inside its quote (count, time, direction) or chunk (wind, force, weather, other dates, specimen); names inside the chunk or, flagged, the context, case and italics aside | 0 to 34 per year; the rest are tidied OCR or a heading further back than the context (1880's "Sky Lark", 29 records) |
| TD | ISO date agrees with the copied words | 0 to 11 per year; left blank in records |
| T3 | a sample of 100 observations per year read on the scans by vision helpers, with planted errors | see below |
| merge | the second reading and adjudication scored on T3's sample | see below |

Each check was broken once and caught the break (T1, T2, TD: `tools/check_obs.py --break`; T3: the planted errors; the merge: scored on known errors).

### T3: planted errors and what the flags mean

Each year, 100 observations (seed = the year), half drawn uniformly and half
from lantern events (dead, struck, caught, round the lantern or station, at
the light), were read on the scans by safe-mode vision helpers with one
item in six carrying a planted error. They caught 115 of 117 planted
errors. Every other field they called wrong was then classed by two
independent helpers (`tools/t3_review.py`; 33 disagreements decided by hand
on the chunk, `data/checks/t3review/decided.json`). This is the first
reading, before the second reading and merge.

| year | fields checked | flags | extraction errors | rate (95%) | checker | OCR copy | Gutenberg | judgement | open |
|---|---|---|---|---|---|---|---|---|---|
| 1879 | 57 | 23 | 14 | 1.3% (0.8%-2.2%) | 6 | 0 | 1 | 2 | 0 |
| 1880 | 141 | 15 | 4 | 0.4% (0.1%-0.9%) | 5 | 0 | 2 | 4 | 0 |
| 1881 | 101 | 21 | 12 | 1.1% (0.6%-1.9%) | 3 | 0 | 1 | 5 | 0 |
| 1882 | 100 | 7 | 3 | 0.3% (0.1%-0.8%) | 1 | 0 | 0 | 3 | 0 |
| 1883 | 156 | 48 | 7 | 0.6% (0.3%-1.3%) | 11 | 27 | 0 | 3 | 0 |
| 1884 | 215 | 69 | 4 | 0.4% (0.1%-0.9%) | 4 | 57 | 0 | 4 | 0 |
| 1885 | 195 | 22 | 4 | 0.4% (0.1%-0.9%) | 15 | 0 | 0 | 3 | 0 |
| 1886 | 203 | 67 | 2 | 0.2% (0.1%-0.7%) | 7 | 49 | 0 | 9 | 0 |
| 1887 | 225 | 10 | 4 | 0.4% (0.1%-0.9%) | 1 | 0 | 1 | 4 | 0 |

Over all nine years: **54 extraction errors in 9,770 checked fields, 0.55%
(95% 0.42-0.72%)**; uniform half 0.43% (0.28-0.66%), lantern half 0.68%
(0.48-0.95%). By field: time 1.6% (0.9-2.6%), at_light 1.0% (0.5-1.9%),
species 0.9%, behaviour 0.5%, direction, force and weather 0.4%, wind 0.3%,
count 0.2%, station and date 0.1%. The errors run one way: a time stated
earlier in the sentence left out, at_light false where the text ties the
birds to the light, a group of named kinds left without a species, the
heading's bird replaced by its companion.

The checker's own errors (53) are mostly over-reading (a count it thought
shared; a time it carried across a sentence); "OCR copy" (133, all in 1883,
1884 and 1886) are fields copied faithfully from garbled OCR ("t.v." for
L.V.), which the rules require and the scan link resolves. In 1886 the OCR
breaks some tables into columns, and the station or species of a row
cannot be read from it: a real loss in that year.

Recall (observations missed altogether) is not what T3 measures. Two
flags noticed a missing observation beside the checked one ("stopped on
island"; "the second flock rested about ten minutes"); the second reading
adds such observations where it finds them.

### The second reading

The chunks with lantern words were read a second time, independently, one
chunk per call (`tools/second_reading.py`, cache tag v4b); the two readings'
observations were paired and compared field by field after normalising, and
a third reader, shown both and the chunk, decided only the disputes (so a
field both readings agree on cannot change). Merged files:
`data/obs/<year>_v4m.jsonl`, every decision in `_v4m_decisions.json`.

| year | chunks read twice | fields changed (count, behaviour, time, at_light) | observations added | dropped | T3 errors fixed | T3-confirmed fields changed |
|---|---|---|---|---|---|---|
| 1879 | 57 | 49 | 21 | 8 | 6 of 12 | 3 of 857 |
| 1880 | 141 | 51 | 34 | 27 | 2 of 4 | 1 of 760 |
| 1881 | 101 | 78 | 51 | 25 | 2 of 12 | 5 of 777 |
| 1882 | 100 | 79 | 72 | 6 | 1 of 3 | 2 of 857 |
| 1883 | 156 | 191 | 60 | 12 | 3 of 6 | 5 of 820 |
| 1884 | 215 | 165 | 85 | 22 | 0 of 3 | 1 of 784 |
| 1885 | 195 | 167 | 71 | 19 | 0 of 4 | 1 of 893 |
| 1886 | 203 | 187 | 100 | 13 | 0 of 2 | 3 of 854 |
| 1887 | 225 | 198 | 76 | 20 | 1 of 4 | 2 of 850 |

(1,393 chunks in all. "Added" are observations
only the second reading found, kept by the third reader and not repeating a
kept one; "dropped", observations only the first reading had, judged not
observations by the rules.) The T3 columns score the merge on the first
reading's checked sample: of the 50 extraction errors T3 found whose
observation the evaluation could pair (of 54), it **fixed 15**; of 7,452 fields T3 confirmed right, it
**changed 23**. All 23 were read by hand: 19 are equal or better ("same_as"
for "All those as yesterday"; a time of "midnight" carried from the
sentence; a bat dropped), and 4 are worse. The worse ones:
at_light set false for birds "killed at the Hasbro' L.v." and at Lynn Well
L.V. (1883, a footnote list), and for "caught at lighthouse" (1881); a
time of "nights" lost (1883).

That at_light flip is not rare. Over all years the merge set at_light
true on 76 strike records and false on 74, 59 of the latter in the 1883
light-vessel lists: the rule asks whether the text ties the birds to the
lantern, and "killed at the L.V." sits on the line. The strike tests
therefore don't rest on at_light for killed birds (notes/TESTS.md, K1
amendment).

The first version adopted every field the third reader decided. On 1880 it
broke the rule of one observation per species (it preferred "Thrushes,
Blackbirds, and Ring Ouzels" as one record) and changed wording that was
right. The merge now takes only behaviour, at_light, time and count (where
the first reading's errors fall, all one way) and the observations only one
reading found; species, station, date, wind, force, weather and direction
stay as the first reading has them.

The errors the two readings share (most of them) no second reading of this
kind can find: a time stated earlier in a long sentence, "seen" where the
text says "five killed" of two kinds together, the heading's species taken
over by a companion bird. They are what the error rates measure.

## What to trust

- **Every record can be checked.** Each carries the exact printed words it
  came from and a page and scan link; corrections (25 errata) change values,
  never the quote.
- **Copied fields: about 1 in 200 wrong** (T3, 0.55%, 95% 0.42-0.72%,
  before the merge). Worst are time (1.6%) and at_light (1.0%), wrong
  mostly by leaving out what the sentence says earlier.
- **at_light follows wording.** For killed birds it says whether the
  sentence names the lantern, not where they died: half the 2,766 killed
  records are false. Use behaviour (struck, dead, round_lantern) for
  strikes.
- **Recall is not measured.** The second reading found 570 observations
  the first had missed in its 1,393 chunks (2.0% on the first
  reading's 28,068 there);
  how many both missed is unknown.
- **Species: 83% of records resolve to a species**; the rest to a genus or
  a group. Some mappings are assumptions about Victorian usage, applied
  everywhere: "Larks" is the Sky Lark, "Thrushes" the Song Thrush, "Crows"
  and "Black Crow" the genus *Corvus* (`data/species.csv`, column `how`).
- **Stations: 92.7%** of primary records naming a place resolve to one
  station; 127 names don't.
- **1886's tables** were broken into columns by the OCR, and for some rows
  the station or species can't be read: a real loss in that year, flagged
  rather than guessed.
- **Winds** agree with the reanalysis (63% within 45 deg, chance 25%).
  Treat light-vessels' directions as magnetic and lighthouses' as of
  uncertain north unless a station's own rotation is measured (TESTS.md
  W1).
- **The reports are extracts.** The editors printed what they chose from
  the keepers' schedules; a station's silence is not an empty sky.
