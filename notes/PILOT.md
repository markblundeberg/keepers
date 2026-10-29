# Pilot: the 1887 English diaries

Stage 1 of PLAN.md, done 27 Oct 2026. What was built, what each check found,
and the method for the other eight reports.

## The text

Project Gutenberg #66152, the two diary sections: the East Coast of England,
and the West Coast of England and Wales with the Isle of Man. One paragraph
per date; each station's entry opens with its name in italics; the weather is
in brackets, keyed by the report itself ("the force of the wind ranges from
0 to 12"; Beaufort's letters "B. blue sky; C. detached clouds; ... W. dew").
The West Coast preface adds: "The diction of the observers has been closely
adhered to."

## Pipeline

| step | tool | output |
|---|---|---|
| pages | `tools/pages.py`: anchors the HTML page markers in the text (177 of 180; the misses are front matter and a continued table); scan image = IA leaf − 1, checked by eye (n60 is p. 47) | `data/pages/1887.json` |
| segments | `tools/segment_diary.py`: one segment per station per date, exact text and offsets | 1,621 segments (East 1,024, West 597) on 440 section-dates; 1,334 name L.H. or L.V. in their head, 287 don't (mostly land observers: Yarmouth, Redcar, Tetney, Merionethshire) |
| rules | `tools/rules.py`: weather brackets, clock times, flight directions, words for deaths, strikes and the lantern | the independent reading for the comparison |
| extraction | `tools/extract_llm.py` with `tools/prompts/extract_diary_v2.md`: Opus 5.5, effort high, `claude -p --safe-mode --tools ""`, JSON schema; every field except `note` copied exactly from the text | 3,686 observations; $15.03, about 40 min with 6 workers |
| numbers | `tools/normalize.py`: times to minutes, counts to ranges and categories, directions to bearings, the death tally per segment, all by fixed rules; the model never produces a number | |

## What the checks found

| check | result |
|---|---|
| T1 exact quotes | all 3,686 quotes re-read from the source file. Broken once (one character altered): caught. |
| T2 fields inside quotes | all 9,743 copied fields and 2,102 weather fields. Broken once (two winds swapped): caught. A substring test only; the semantic checks are below. |
| T4 completeness, segments | every L.H./L.V. in the text must open a segment. The first segmenter missed 40: italic names wrapped across lines ("_Outer\nDowsing_"), `=bold=` markup, "East _Goodwin_", "_Chickens Rock_, L.H.", a name in plain type. Now none. No false splits found (short segments and odd openings read by eye). |
| T4 completeness, observations | bird-like words no quote covers: 31 segments flagged in v1, 3 real misses (a printed total beside its breakdown; "Abundant on April 10th"; "nearly a hundred ducks"); 28 in v2, the rest commentary, people and places ("Mr Black says", "the carcase of a Pig"). Broken once (one segment's records deleted): caught. |
| T5 dates | non-decreasing through each section, each under its month's heading. Broken once (a block shifted a month): caught. |
| rules vs LLM (v2) | clock times 99.6%, flight directions 98.6%, wind 97.1%, force 96.1%, weather 98.5%, any death 97.0% of segments. Reading the disagreements: the LLM is right in nearly all. The rules read "not killed" as a death, a flight direction "(E. to W.)" as wind, "about to S.E. of island" as a flight. The LLM's one systematic miss (v1: "passing S." directions, 16 on the West Coast) was fixed in v2 (flight agreement 96.2% to 98.6%). |
| v1 against v2 | two runs, prompt changed only in its new rules: identical (species, behaviour) sets in 94.3% of segments (the new `round_station` category accounts for most of the rest); on matched observations, normalised time 98.6%, count 99.4%, at_light 99.4%; segment weather 99.6–99.9%. Death tallies (by the rule in `normalize.deaths`) differ in 5 of 229 segments, v2 right in all 5. |
| T3 against the print (v1) | 100 observations sampled (seed 1887), read on the scans by safe-mode vision helpers; 15 planted errors, 15 caught. Of 885 unplanted fields, 12 flagged: 2 real extraction errors (both fixed in v2), 6 Gutenberg slips, 1 elliptical name ("*Pied and *Yellow Wagtails" gives "Pied"), 3 checker misjudgments. |
| T3 against the print (v2) | a fresh sample (seed 18872), half uniform, half lantern events (dead, struck, round the lantern or station, caught, or at the light); 16 planted errors, 16 caught. Of 884 unplanted fields, 8 flagged: 6 winds missing a final stop (no value changes), 1 misfiled behaviour ("Sandwich Terns, great many fishing round island" as `round_station`; feeding near the station isn't circling it, and the checker's brief lacked the new category), 1 Gutenberg slip ("O. P. V." for the printed "O. R. V."). So: 1 extraction error in 884 fields (0.1%; 95% interval about 0.003% to 0.6%), and at most 1 of 100 observations wrong. |
| sex symbols | T3 found two ♂ in the Gutenberg text where the print has ♀ (both confirmed by eye). All 20 symbols in the diaries were then read on the scans: 5 wrong in Gutenberg, all in the East Coast section (4 of them ♂ for ♀); the West Coast's 9 are right. In `data/errata.csv`; the East section's sexes need the scan. |
| T6 second witness | every number in the Gutenberg text aligned with the IA OCR: 1,938 of 1,989 agree. 22 same-shaped disagreements settled on the scans by a helper (two by eye): Gutenberg right in 20, a footnote renumbered once, and wrong once: "12.50 A.M." where the print has "12.5 A.M." (Skerries Rock, Flycatchers striking the glass). The OCR confuses 3 and 5 in this type. Corrections go to `data/errata.csv`; quotes stay exactly as Gutenberg has them. |

## Things the data must carry

- **Totals and parts.** "Forty-four birds killed., _viz._, twenty-five Starlings, four Redwings, eleven Larks, and one Missel Thrush": the parts sum to 41. Both are kept as printed; the tally takes the printed total when larger.
- **Shared counts.** "hundreds of birds ... Swallows, Wheatears, ... many of which were killed": one count over several kinds counts once.
- **Elliptical names.** "*Pied and *Yellow Wagtails": the copied species is "Pied"; the species table must resolve it from the quote.
- **Times.** "12 P.M." was often midnight in Victorian usage: flagged as ambiguous, not guessed. Ranges into the next morning run past 1440 minutes. "till the light was extinguished" and "lighting time" are dusk and dawn, to resolve with the sun.
- **Round the ship.** On a light-vessel at night, "flying round the ship" is recorded as `round_station`, not as round the lantern; whether it means the light is an analysis question.
- **Source quirks** (`notes/QUIRKS.md`): winds printed "K"; "W. by E."; 39 asterisks where the text says thirty-four.

## Decision: the method for the other reports

1. **Segment deterministically, per layout, with an independent count.** Diary layout: as here. Station-ordered (Irish coast, Scotland from 1885): cut at station heads, then dates. Species-ordered (most of 1879–1886): cut at species heads, which fall mid-paragraph ("Common Thrush, _T. musicus_.--Spring, 1885: Longstone L.H., ..."); there the extractor also copies the station and date words. T4's count adapts: station mentions and day tokens must fall inside some segment and some quote.
2. **Extract with the LLM, everything copied exactly, numbers by code.** Prompt v2 plus a short layout note. Safe mode, no tools, JSON schema, cached by prompt hash.
3. **Check every year** with T1, T2, T4, T5 (automatic), the rules comparison (weather, times, directions, deaths), a stratified T3 sample with planted errors (100 per year), and T6 where there is a Gutenberg text.
4. **OCR-only years (1883, 1884, 1886)**: the quote must be the OCR text exactly, errors and all ("Farn L.H#.", "Turpus Viscivorus"), so a `reading` field is needed for what the print says, from the scan, and T3 becomes the main transcription check there. To try on a few pages before committing.
5. **Cost.** About $0.0093 per segment for extraction, and about $4 per 100-item T3. If the whole collection is about 10,000 segments, extraction is about $100.
