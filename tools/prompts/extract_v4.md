You are helping turn a Victorian bird-migration report back into data. In 1879-1887 a British Association committee sent printed schedules to lighthouses (L.H.) and light-vessels (L.V., "Lt.-ship", "lightship") around Britain and Ireland, and the keepers recorded the birds they saw, with time, wind and weather. Land observers contributed notes too. The committee printed the returns in annual reports. This is the {year} report.

Below are chunks of the report, each with its place in the report (coast, section heading, layout) and a CONTEXT: the text just before the chunk. The layouts:
- diary: entries by date, each station's entry opening with its name ("October 21st.--_Coquet_ L.H., One Woodcock, 10.30 A.M., shot.").
- station: entries by station ("_North Maidens._--October 21st, striking, 9 P.M. to 1 A.M."), often letters or extracts from the keepers.
- species: entries by bird ("Gannet, _Sula bassana_.--At Spurn L.V., Oct. 1st to 16th, many to S."), or by family in running prose ("Turdidae.--In spring, migration at Sumburgh Head (April 3rd) ..."), naming stations and dates as they go.
- prose and table: running remarks or tabulated records.
Your job: list the bird observations in each chunk, each with its station, date and weather where the text gives them.

THE MOST IMPORTANT RULE: every string you return (except `note` and `date_iso`) must be copied exactly from the text: same spelling, capitals, punctuation, underscores and odd typography, even where the printer made a slip or the text is garbled. Never correct, expand, modernise or summarise. Use null when something isn't stated. We check every string against the source by machine.
Observations come only from the CHUNK. The CONTEXT is there so you know which species, station, date or season the chunk continues: you may copy `species`, `station` or `date` from the context when the chunk itself doesn't give them for an observation, and then you must list those field names in `from_context`. Everything else, and the `quote`, comes from the chunk.

For each chunk return `chunk` (its id) and `obs`, a list of observations. Each observation:
- `station`: the words naming one lighthouse, light-vessel or place where it was observed, as printed. When one sentence covers several stations ("at Pentland Skerries and Isle of May"; "Stations VII., VIII., XIV., and XXVII."), give one observation per station, each with that station's words. Some reports cite stations by their number on the committee's map, in Roman numerals ("XXVII.", "XIV. (Pentland Skerries)"): copy those as printed. ("_Dudgeon_ L.V.", "Spurn L.V.", "Farn L.H.", "Great Yarmouth", "N. Unst", "the Fastnet"), from the chunk or, if the chunk continues a station's entry, from the context; null if none is given.
- `date`: the date words as printed for this observation ("Oct. 16th", "25th", "October 21st", "April 3rd to 5th", "Jan. 5th, 1884", "night of 18th"), from the chunk or the context; null if none.
- `date_iso`: your reading of that date as YYYY-MM-DD (YYYY-MM-DD/YYYY-MM-DD for a range; YYYY-MM if only a month is given), taking the month and year from the date words or the text before them. The report covers the spring and autumn of {year}; a January or February after an autumn's entries usually belongs to {next_year} unless the text says otherwise; a printed year overrides. Null if no date is given.
- `wind`, `force`, `weather`: as printed where the text gives them for this observation (often a bracket at the end of the station's entry, outside the quote: "(S.E., 3; O. M.)"; force runs 0-12; weather letters are Beaufort's: B blue sky, C detached clouds, D drizzle, F fog, G gloomy, H hail, L lightning, M misty, O overcast, P passing showers, Q squally, R rain, S snow, T thunder, U ugly/threatening, V unusual visibility, W dew; or words: "wind S.E., light", "foggy"), else null. Take them from the chunk only.
- `from_context`: the fields you copied from the CONTEXT (e.g. ["species", "date"]), else [].

Observations: one per bird kind per behaviour. "Larks round lantern all night; eight killed" is two observations of Larks: one round_lantern, one dead with count "eight". "Thrushes, Blackbirds, and Starlings" is three observations.
When a total is printed with a breakdown ("Forty-four birds killed, viz., twenty-five Starlings, four Redwings, eleven Larks"), give each item of the breakdown, and also the total as its own observation (species "birds", count "Forty-four") with `total` true. Totals and parts don't always add up in the print; copy both as printed.
If a chunk reports birds on another date ("Abundant on April 10th", "Also on 25th"), include that too: as its own observation with the date words in `other_dates`, or in `other_dates` of the observation it repeats.
- `quote`: the shortest stretch of the chunk that holds what this observation says (count, behaviour, time, direction, weather, and the bird's name where it is given there). It must contain every other string you give except `species`, `station`, `date`, `wind`, `force` and `weather`, which may stand elsewhere in the chunk (a heading, an earlier sentence, the weather bracket closing the entry) or, if listed in `from_context`, in the context. Quotes may overlap. A clause that continues another ("about fifty Larks during night; eight killed") shares its bird, time and direction: start the quote where they are, as in the first example below.
- `species`: the bird name as printed ("Titlarks", "Golden-crested Wren", "Grey Crows", "small birds", "birds", "_Ruticilla titys_"). If no bird is named for an event ("Large flocks also passing over"), null.
- `count`: the number or quantity words as printed ("eight", "200", "a few", "several", "large flocks", "thousands of", "great number of", "one", "a"), or null if not stated.
- `count_shared`: true if one count covers several kinds together ("thousands of birds--Thrushes, Blackbirds, Starlings"); then copy that count onto each.
- `total`: true only for a total that other observations in this chunk break down (see above); else false.
- `behaviour`, one of:
  - `passing`: flying past, over or along, migrating, with or without a direction.
  - `round_lantern`: flying round, about or at the lantern or light, in its rays.
  - `round_station`: flying round or about the ship, vessel, rock, island or lighthouse, not said to be the lantern or light ("flying round the ship at 3.30 A.M."). Not birds feeding or fishing nearby ("Terns fishing round island" is `seen`).
  - `lost_over`: fell or were lost over the gallery or overboard, fate not stated ("many lost over", "struck heavily, but was lost over"). Not `dead` unless the text says killed or dead.
  - `struck`: striking or hitting the lantern or glass (not stated killed).
  - `dead`: killed, or found dead, as the text states (the count is the number dead).
  - `caught`: caught or captured, alive or not stated.
  - `shot`: shot.
  - `settled`: alighting or resting on the vessel, deck, rigging, rock, island, gallery or lighthouse ("on board", "about deck", "resting on windows", "remained about the lighthouse").
  - `heard`: heard but not seen.
  - `seen`: present or seen, nothing more specific stated.
  - `same_as`: the entry only says it was the same as another day ("the same as on 5th", "see under yesterday").
  Pick the most specific that the text states. Don't infer: "Titlarks at night" alone is `seen`.
- `at_light`: true if the text connects these birds to the lantern or light (round it, striking it, killed or caught at it, in its rays), else false.
- `time`: the time of day as printed ("4 A.M.", "8 P.M. to midnight", "from 10 P.M. till 4 A.M.", "all night", "at night", "during day", "morning"), or null.
- `direction`: the words giving the flight direction as printed ("to W.", "E. to S.W.", "S.E. to N.W.", "passing S.", "going E.", "crossing E.", "flying W.", "westerly", "to the Essex Shore"), or null. A compass point after a verb of motion is a direction: "Puffins passing S. all day" has direction "passing S.". A bracket right after a bird name can be a direction: "a few Larks (E. to W.)". Never the wind, and never a position ("to S.E. of island" is where, not whither).
- `other_dates`: words saying the observation also covers other dates, or for `same_as` the date referred to ("Also on 25th", "and to 26th inclusive", "also night of 18th", "on 5th", "yesterday"), or null.
- `specimen`: words saying a wing, leg or bird was sent or the identification verified ("wing sent", "*"), or null.
- `note`: your own words, under 15 words, only if something is unclear or unusual; else null.

A chunk with no bird observations (commentary, thanks, lists of names) has an empty `obs`. Summaries and remarks count: if a chunk says "On the night of Oct. 21st Larks struck in great numbers at the Spurn", that is an observation. Return every chunk, in order.

Example 1. Chunk (diary layout; context: "January 7th.--_Outer Dowsing_ L.V., Fieldfares and two Starlings on board."):
[1887-00003] _Dudgeon_ L.V., Titlarks at night; five killed. (S.E., 3.)
Gives: {{"chunk": "1887-00003", "obs": [
 {{"quote": "Titlarks at night", "station": "_Dudgeon_ L.V.", "date": "January 7th", "date_iso": "1887-01-07", "wind": "S.E.", "force": "3", "weather": null, "from_context": ["date"], "species": "Titlarks", "count": null, "count_shared": false, "total": false, "behaviour": "seen", "at_light": false, "time": "at night", "direction": null, "other_dates": null, "specimen": null, "note": null}},
 {{"quote": "Titlarks at night; five killed", "station": "_Dudgeon_ L.V.", "date": "January 7th", "date_iso": "1887-01-07", "wind": "S.E.", "force": "3", "weather": null, "from_context": ["date"], "species": "Titlarks", "count": "five", "count_shared": false, "total": false, "behaviour": "dead", "at_light": false, "time": "at night", "direction": null, "other_dates": null, "specimen": null, "note": null}}]}}
The killed birds are the Titlarks seen at night, so the second quote starts at "Titlarks" and carries the time.

Example 2. Chunk (species layout; context: "Sky Lark, _Alauda arvensis_.--Autumn: Spurn L.V., Oct. 1st to 16th, many to W."):
[1885-00012] At Cockle L.V., Oct. 16th, several; 25th, fifteen to W. (S.E., 3.)
Gives: {{"chunk": "1885-00012", "obs": [
 {{"quote": "At Cockle L.V., Oct. 16th, several", "station": "Cockle L.V.", "date": "Oct. 16th", "date_iso": "1885-10-16", "wind": null, "force": null, "weather": null, "from_context": ["species"], "species": "Sky Lark", "count": "several", "count_shared": false, "total": false, "behaviour": "seen", "at_light": false, "time": null, "direction": null, "other_dates": null, "specimen": null, "note": null}},
 {{"quote": "25th, fifteen to W. (S.E., 3.)", "station": "Cockle L.V.", "date": "25th", "date_iso": "1885-10-25", "wind": "S.E.", "force": "3", "weather": null, "from_context": ["species"], "species": "Sky Lark", "count": "fifteen", "count_shared": false, "total": false, "behaviour": "passing", "at_light": false, "time": null, "direction": "to W.", "other_dates": null, "specimen": null, "note": null}}]}}
Here the station of the second observation is copied from the chunk ("Cockle L.V." appears in it), so it isn't listed in from_context.

The chunks:

{chunks}
