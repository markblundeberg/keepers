You are helping turn a Victorian bird-migration report back into data. In 1879–1887 a British Association committee sent printed schedules to lighthouses (L.H.) and light-vessels (L.V.) around Britain and Ireland, and the keepers recorded the birds they saw, with time, wind and weather. A few land observers contributed notes too. The committee printed their returns in annual reports. This is the {year} report, {section_name}.

Below are segments of the report. Each segment is one station's entry for one date; the station and date are already known, so don't extract them. Your job: list the bird observations in each segment, and its weather.

THE MOST IMPORTANT RULE: every string you return (except `note`) must be copied exactly from that segment's text: same spelling, capitals, punctuation, underscores and odd typography, even where the printer made a slip. Never correct, expand, modernise or summarise. Use null when something isn't stated. We check every string against the source by machine.

For each segment return `seg` (its id), the weather, and `obs`, a list of observations.

Weather (usually a bracket near the end, e.g. "(S.E., 3; O. M.)"; the report says force runs 0–12 and the letters are Beaufort's: B blue sky, C detached clouds, D drizzle, F fog, G gloomy, H hail, L lightning, M misty, O overcast, P passing showers, Q squally, R rain, S snow, T thunder, U ugly/threatening, V unusual visibility, W dew):
- `wind`: the wind direction as printed ("S.E.", "W. by S.", "Light and variable"), or null.
- `force`: the force as printed ("3", "fresh breeze", "gale", "light"), or null.
- `weather`: the weather letters or words as printed ("O. M.", "B. C. M.", "snow", "haze"), or null.
If a segment has more than one weather bracket, take the one that goes with the main (usually night or lantern) observation and mention the other in a `note` of any observation.

Observations: one per bird kind per behaviour. "Larks round lantern all night; eight killed" is two observations of Larks: one round_lantern, one dead with count "eight". "Thrushes, Blackbirds, and Starlings" is three observations.
When a total is printed with a breakdown ("Forty-four birds killed, viz., twenty-five Starlings, four Redwings, eleven Larks"), give each item of the breakdown, and also the total as its own observation (species "birds", count "Forty-four") with `total` true. Totals and parts don't always add up in the print; copy both as printed.
If a segment reports birds on another date ("Abundant on April 10th", "Also on 25th"), include that too: as its own observation with the date words in `other_dates`, or in `other_dates` of the observation it repeats.
- `quote`: the shortest stretch of the segment that holds everything this observation says (bird, count, time, direction, behaviour). It must contain every other string you give for this observation. Quotes may overlap.
- `species`: the bird name as printed ("Titlarks", "Golden-crested Wren", "Grey Crows", "small birds", "birds", "_Ruticilla titys_"). If no bird is named for an event ("Large flocks also passing over"), null.
- `count`: the number or quantity words as printed ("eight", "200", "a few", "several", "large flocks", "thousands of", "great number of", "one", "a"), or null if not stated.
- `count_shared`: true if one count covers several kinds together ("thousands of birds--Thrushes, Blackbirds, Starlings"); then copy that count onto each.
- `total`: true only for a total that other observations in this segment break down (see above); else false.
- `behaviour`, one of:
  - `passing`: flying past, over or along, migrating, with or without a direction.
  - `round_lantern`: flying round, about or at the lantern or light, in its rays.
  - `round_station`: flying round or about the ship, vessel, rock, island or lighthouse, not said to be the lantern or light ("flying round the ship at 3.30 A.M.").
  - `struck`: striking or hitting the lantern or glass (not stated killed).
  - `dead`: killed, or found dead (the count is the number dead).
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

A segment with no birds at all may have an empty `obs`. Return every segment, in order.

Example. Segment:
[1887-ENE-0001] _Dudgeon_ L.V., Titlarks at night; five killed. (S.E., 3.)
Gives: {{"seg": "1887-ENE-0001", "wind": "S.E.", "force": "3", "weather": null, "obs": [
 {{"quote": "Titlarks at night", "species": "Titlarks", "count": null, "count_shared": false, "total": false, "behaviour": "seen", "at_light": false, "time": "at night", "direction": null, "other_dates": null, "specimen": null, "note": null}},
 {{"quote": "Titlarks at night; five killed", "species": "Titlarks", "count": "five", "count_shared": false, "total": false, "behaviour": "dead", "at_light": false, "time": "at night", "direction": null, "other_dates": null, "specimen": null, "note": null}}]}}

The segments:

{segments}
