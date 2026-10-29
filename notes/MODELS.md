# Which model for which job

Mark's question (27 Oct 2026): are Opus agents needed for this? On his
subscription the marginal cost is zero, so the question is accuracy (and
speed). The jobs differ:

1. extraction from a clean transcription (the Gutenberg years): structured
   reading with judgment calls (totals and parts, shared counts, direction
   or position, which weather bracket);
2. extraction from OCR only (1883, 1884, 1886): reading through garbled text;
3. the checks of record (T3 scan reading, scan questions): small volume.

## The bar, written before the results

Sonnet 5.5 and Haiku 5.5 run prompt v2 on the same 1,621 segments of the
1887 English diaries. A model is good enough for job 1 if:

- T1/T2: at least 99.5% of its quotes and fields are exact copies
  (failures are caught and can be rerun, but many would mean sloppiness);
- against the Opus v2 run, on matched observations: normalised time, count
  and direction within about one point of the Opus v1-v2 run-to-run
  agreement (98.6%, 99.4%, 99.4%), and death tallies agreeing in at least
  97% of segments with deaths (Opus v1-v2: 224 of 229, v2 right in all 5);
- T3 by the Opus checker with planted errors, same procedure as Opus v2
  (stratified, 100 items): no more than 3 real extraction errors in about
  880 unplanted fields (Opus v2: 1);
- reading the disagreements with Opus: no systematic error on the judgment
  calls.

Checks of record stay on Opus whatever the extractor; a checker that isn't
the extractor's model also shares fewer of its blind spots.

## Results

### Sonnet 5.5 (prompt v2, effort high), 1887 English diaries

| test | bar | Sonnet | Opus (for reference) |
|---|---|---|---|
| exact copies (T1, T2) | 99.5% | 99.97%: 4 slips in about 15,600 strings, one a wind and force taken from no text in its segment (ENE-0904) | 100% |
| time, count, direction against Opus (normalised) | about 97.6, 98.4, 98.4% | 98.3, 99.2, 99.9% | v1-v2: 98.6, 99.4, 99.4% |
| death tallies against Opus | 97% of segments | 96.5% (221 of 229) | v1-v2: 97.8% |
| T3, Opus checker, planted errors | at most 3 real errors in about 880 fields | 17/17 plants caught; about 13 real extraction errors in 883 fields | 16/16; 1 in 884 |
| speed | | 98 s per 42-segment batch | 110 s |

Reading the disagreements and the T3 flags: Sonnet's errors fall on the lantern
entries: "struck lantern and killed" and "killed striking" filed as struck
rather than dead; "Hundreds must have been killed by striking the lantern"
as struck; lantern kills marked not at the light; "all night" given to Wrens
it doesn't belong to; species and times left off "some striking"; a printed
total not flagged; "one Starling, Thrush, and Snipe killed" read as one.
Those are the records the piece and the strike analysis rest on.

Five of the eight death-tally disagreements were neither model's error but a
gap in the schema: birds "lost over" (struck, then fell over the gallery into
the sea). Opus counted them dead, an inference; Sonnet didn't, the literal
reading. Prompt v3 adds `lost_over`, fate not stated.

**Decision for job 1: Opus.** Sonnet clears the exact-copy and numbers bars
but fails T3 by a wide margin (about 13 against 1), on exactly the lantern
events, and is barely faster at this effort.

### Haiku 5.5 (prompt v2, effort high), same segments

| test | bar | Haiku |
|---|---|---|
| exact copies (T1, T2) | 99.5% | 99.88%: 15 quotes not exact (e.g. "the same as on 20th" for "on the 20th") and 4 fields outside their quotes |
| time, count, direction against Opus (normalised) | about 97.6, 98.4, 98.4% | 96.8, 98.9, 99.9%: time below the bar |
| death tallies against Opus | 97% of segments | 94.4% (218 of 231): below the bar |
| speed | | 152 s per batch, the slowest of the three |

It fails two bars before the scan check, so T3 wasn't run.

### What the comparison taught

The cheap automatic checks barely tell the models apart: against the rules
reader all three agree 97-99% on wind, force, weather, clock times and flight
directions, and all copy exactly 99.9% of the time. What separates them is
meaning, not copying: the scan check with planted errors (Opus 1 real error
in 884 fields, Sonnet about 13 in 883) and the death tallies (Opus runs agree
in 97.8% of segments, Sonnet 96.5%, Haiku 94.4%). A model choice judged on
the automatic checks alone would have picked wrong.

**Decision: Opus 5.5 for extraction (job 1) and for the checks (job 3).**
Job 2, the OCR years, is harder reading than job 1, so the same follows a
fortiori; it gets its own test on a few pages in stage 3.
