# Source quirks

Places where the sources disagree with themselves or with the print, found
while building the data. Each is checked against the scans when it matters,
and the data keep the printed reading (the quote) either way.

| Report | Where | What | Status |
|---|---|---|---|
| 1887 | p. 47, Kentish Knock L.V., Oct. 26 | Gutenberg "L.V. Crows" and "(W.S.W, 2.)"; the print has "L.V., Crows" and "(W.S.W., 2.)" | checked on scan n60 |
| 1887 | West Coast diary, April 27th | Gutenberg markup slip "April 27th.-_-Holyhead Breakwater_" (underscore inside the dash); the segmenter handles it | parser |
| 1887 | West Coast station list | the text says returns came from "the thirty-four stations marked with an asterisk", but 39 are marked in the Gutenberg text | to check on the scan |
| 1887 | East Coast diary, segments ENE-0239, ENE-0984; West ENW-0316 | wind "K" in the Gutenberg text (no such compass point) | the print has N., E. and E.: Gutenberg slips, in errata (one checked by eye) |
| 1887 | East Coast diary, ENE-0613 | wind "W. by E., 7, 8": not a compass point | printed so (scan helper): the printer's own slip; wind left unresolved |
| 1887 | East summary | "hundreds of Flycatchers, from midnight to 4 P.M." at the Swin L.V., April 29: probably 4 A.M. | to check the diary entry and scan |
| 1887 | HTML page 120 | page marker sits before a continued table; not anchored in the text, so records there are attributed to p. 119 | known |
| 1887 | West Coast diary, ENW-0492 (Portland Low L.H.) | the print has the wind "N.E.N.", no standard point; Gutenberg regularised it to "N.N.E." | read twice on the scan by helpers; in errata |
| 1879 | station list, Chanonry Point | "Chanonry Point, Elgin; white and red sectors, revolving every minute" repeats the next line (Covesea Skerries) word for word, county and all; Chanonry is in Ross-shire, and Findlay 1879 has "One bright fixed light". The IA OCR has the same line, so it is the print's slip, not Gutenberg's | use Findlay |
| 1887 | East Coast station list | "Leman and Ower L.H." for the light-vessel (the master list has "43. Leman and Ower L.V.") | Gutenberg text; not checked on the scan; grouped as the light-vessel |
| 1887 | master list, no. 102 | "Rhinns of May" for the Rhinns of Islay (same number in the West list) | Gutenberg text; not checked on the scan |
| 1881, 1882 | East of Scotland lists, no. 4 | "North Uist" for North Unst (Shetland) | Gutenberg text; not checked on the scan; grouped by number |
| 1881 | West of Scotland list | "Bona" (no. 89) for Rona; "Conan Ferry" (no. 97) for Corran Ferry | Gutenberg text; grouped by number and neighbours |
| 1884, 1885 | West of England lists | Breaksea printed "L.H."; it is a light-vessel in every other list and in Findlay | grouped as the light-vessel |
| 1883 | Irish list | Tuskar printed "Lt.-ship"; it is a lighthouse | read off the scan twice; grouped as the lighthouse |
| 1880 | East of England list, Goodwin | Gutenberg has "86 seconds dark" where 1879 prints "36 seconds darkness" and Findlay "obscured for 36 secs." | the print has 36 (scan n32, p. 27; IA OCR agrees): a Gutenberg slip, in errata |
| 1882, 1885 | East of England lists | the list has 37 (1882) and 36 (1885) rows against sentences counting 38 and 45 stations | the print's counts; see data/stations/lists/reviewed.json |
| Findlay | 1879 and 1887 editions | positions of the same unmoved tower differ between editions by up to 7.7 km (Fladda 1879); 1887 is usually the closer to a modern survey | standing lighthouses take Wikidata positions |
| Findlay | 1887, North Carr | the light-vessel is still "proposed" (year 1887) while the reports list the station from 1885 | drawn without a light before 1887 |
| 1879-1881 | Gutenberg texts | "3" read as "8" by the transcribers: 1.80, 7.80 and 11.80 for 1.30, 7.30 and 11.30 p.m./a.m. (no time has 80 minutes), "86 seconds dark" for 36; "_Tardus_" for the italic _Turdus_ five times | all read on the scans; in errata. A slip that makes a possible time ("1.38" for "1.33") is caught only by comparing with the OCR (T6), run on 1887 alone |
| 1880, 1887 | times | the print writes a one-digit minute: "9.5 a.m." is 9.05, "2.9 A.M." 2.09, "12.5 A.M." 0.05 (the IA OCR reads the same) | parsed so (tools/normalize.py) |
