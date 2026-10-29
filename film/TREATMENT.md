# Round the Lantern: the film (treatment, 29 Oct 2026)

A trailer of about 100 seconds that carries the story; the explorer
(sketches/round-the-lantern.html, to be grown) carries the data. Mark's brief
(29 Oct): start local, zoom out into "the disconnected but shared experience
of the collective"; put real effort into story and visuals, with helpers;
birds may be shown, including the aftermath; an ElevenLabs voice is available
(ask tsubomi). His frame for the feeling, which is right: closer to amateur
astronomy than to *The Lighthouse* (2019). From that film only the look:
monochrome, period optics, a narrow frame.

## What it should do to a viewer

Each keeper saw one beam's worth of the night. Only laid together do their
notes show what happened. The line runs solitude, then simultaneity, then a
pattern made of everyone's fragments. That is also the honest scientific
claim, so the story and the evidence are one thing. The feeling is quiet
diligence: someone on a rock at 2 A.M. writing "Thrushes, 24" carefully,
and posting a leg and a wing to strangers who will lay it beside a hundred
others. Not madness, not heroics, not pathos.

## Rules (why in brackets)

- **Every word spoken or shown is printed in the reports**, except the
  framing cards, which are ours and say only what notes/TESTS.md supports.
  (The truth of the words carries the weight; invented narration would cover
  it.)
- **Every light turns at its recorded 1887 rhythm**, in real seconds, and the
  durations the sources don't state follow the rule in tools/sketch_night.py.
  (Make the ornament true.)
- **Birds: as the keepers saw them.** Specks and shapes in the beam (Marian
  Eagle Clarke's Eddystone painting, 12 Oct 1901, is the visual key: the beam
  a solid cone, full of birds), and the aftermath at daylight, plainly: on the
  gallery and the rock, counted. No gore, no lingering, no cute birds.
- **No wave from light to light** (G2: the night came broadside).
- **Colour is the label:** the world is monochrome (aquatint, sepia ink on
  dark paper); the only colour is the lights' own red and green.

## Structure (about 100 s; times approximate, the voice track sets them)

**Cold open (0:00-0:08).** Dark. Wind, sea, the tick of the clockwork that
turns the lens. One beam passes. Card, small: *South Bishop Lighthouse,
21 October 1887.*

**I. One lantern (0:08-0:45).** Close on the lantern; eight beams turn
through the mist, one sweeping past every 20 seconds (its character: "One
rev. br. lt., 20 secs.", from an eight-faced first-order lens turning once in
160 s; film/research/south-bishop.md). Mist in the beam
(the entry's weather: "S.E., 4; O. M.", overcast and misty). Specks arrive,
then many. Voice, plain: *"Hundreds of birds of all sorts, flying around the
lantern, from eleven P.M. to two-thirty A.M."* Soft strikes on glass. A
tally grows at the frame's edge, in fives. Dawn: the gallery and the rock,
grey light. *"Several birds seen on the rock at daylight with broken wings."*
The count, set like the printed line: *272 killed, viz., "Larks," 146;
Starlings, 64; Blackbirds, 38 (caught three old males); Thrushes, 24.* A
leg and a wing go into an envelope: *"in the envelopes provided for this
purpose"* (the committee's request, 1886 report).

**II. The same hours, elsewhere (0:45-1:12).** Pull up and out over the
Irish Sea at night; other beams turning at their own rhythms, none touching.
Voices overlap, each a different reader, each unaware of the others:
- the Maidens: *"striking nine P.M. to one A.M.; about one hundred killed"*
  (one printed sentence; "constantly striking" is a different species'
  entry and must not be spliced in)
- the Eddystone: *"eighty-two killed"*
- Coningbeg light-ship: *"many killed striking, dropped into the sea"*
- Chickens Rock: *"numbers killed, from three A.M. till morning"*
- the Tuskar: *"numbers striking at midnight, fifteen killed. [Leg and wing
  received.]"* (the bracket is the editor's: the envelope from movement I,
  arriving)
Card: *Sixteen lanterns that night. Each keeper wrote down only their own.*
(G1: 16 stations with a strike on the night of 21 October 1887.) The moon had
set before dusk. The first draft's second line, "None could see another",
failed its check: three pairs of the sixteen are 24-36 km apart (South Stack
and Caernarvon Bay L.V., whose position Findlay gives from South Stack;
Godrevy and the Longships; Coningbeg and the Tuskar, whose keepers wrote
"clear" that night), inside a first-order light's range. "Their", not "his": the 1887 list names Annie
Rose Smith at Spurn Point (p. 17).

**III. The pattern (1:12-1:32).** Further back: nine years of nights laid
side by side, a strip per station-month or a calendar; strike nights as
tally marks; the moon's light as the paper's brightness. The marks gather in
the dark. Card: *Strikes on 3 in 100 moonlit nights; 8 in 100 dark ones.*
Then: *No keeper could see it from one rock. It is there when their notes are
laid together.* (K1 and the calendar check.)

**Title (1:32-1:40).** ROUND THE LANTERN. *The keepers' reports, 1879-1887:
36,000 observations, read again.* Then the roll begins: names, stations,
years (data/keepers.csv), and the link to the explorer.

## The roll (end)

The committee wrote a line about each station's returns, and those lines
carry the film's feeling of quiet diligence better than anything we could
write. 1887, Scotland ("Diary from the Stations", data/chunks/1887.jsonl):
- Sumburgh Head: *"Mr James Youngclause.--A very short single schedule.
  Birds very scarce."*
- Rhinns of Islay: *"Messrs Peter Anderson and James Ducat send nine
  carefully filled sheets, and write nearly each time at length."*
- Ailsa Craig: *"Our first returns sent from the 'Old Rock' are very full
  in interest"*
- Kyleakin: *"Messrs D. MacCulloch and John Clyne send three well-filled
  schedules."*
The roll can pair names, stations and years (data/keepers.csv) with such
lines where they exist. Note: keepers.csv has no 1887 Scottish rows because
that year's Scottish names are in these paragraphs, not in a list; extract
them from here before the roll is built.

## Look

Aquatint and mezzotint: tone built from grain, the beam as volume, deep
blacks, warm sepia highlights, paper texture. 16:9 at 1080p for the master;
compose so a 4:5 crop works for social. Lens: period optics (soft edges,
slight vignette, halation round the lamp). Type: Old Standard TT (19th-century
scientific print) for cards and quoted counts.

## Sound

Voice first (as the song was first in ~/git/vid): the readings set the
timing. Under it, synthesised in code: wind, sea, the lens clockwork, the
hiss of the lamp, strikes as small dry taps. Music, if any: sparse, low, and
only from movement II, where the voices multiply. Mark judges all sound.

## True / reconstructed (to be kept up as shots are made)

| element | status |
|---|---|
| the words | printed (report, page and scan for each) |
| light rhythms | recorded characters; unstated durations by a stated rule; phases between lights unknown |
| the night's weather at South Bishop | printed (S.E. 4, overcast, misty); 20CRv3 for the others |
| the moon | computed (skyfield): set before dusk, 27-37% lit |
| the birds' look | reconstructed (no picture of that night exists); species from the count |
| the tower and lantern | reconstructed from the station's type; to be checked against a period drawing |
| the pattern in III | measured (notes/TESTS.md K1) |

## Production (after the test shot)

- Kits first: the lantern and beam (volumetric, rhythm-driven), the bird
  particles (flight round a light, strikes), the sea and mist, the chart at
  night (from the sketch), type and cards, the grain and print look.
- Then one agent per movement, a voice session with tsubomi, sound in code,
  dailies, an independent fresh-eyes reviewer, Mark's notes.
- First: one test shot of movement I's lantern, a few seconds, rendered, for
  Mark to judge before anything else is built.
