# Sources for the lights (stage 2)

Found by a helper on 27 Oct 2026 (its report is summarised in notes/LIGHTS.md).

Period lists of lights, read from scans:
- Findlay, *A Description and List of the Lighthouses of the World*, 1879
  (19th ed.): Internet Archive `adescriptionand00unkngoog`; leaf n = printed
  page + 12; every British and Irish light with character, latitude and
  longitude (0.1'), height, range, year. Table OCR is poor; read the images.
- Findlay, 1887 (27th ed.): HathiTrust `msu.31293100719271` (page sequence =
  printed page + 16). Blocks scripted access; not to be scraped.
- E. Price Edwards, *Our Seamarks* (1884): Internet Archive
  `edwards-1884-our-seamarks-a-plain-account-of-the-ligh`; appendix "List of
  the Principal Coast Lights of the British Islands. Corrected to March 1884":
  characters and ranges, no positions; clean OCR.

Modern coordinates (queries and results here, run 27 Oct 2026):
- `wd_lighthouses.rq` -> `wikidata_lighthouses_2026-10-27.csv`: Wikidata,
  CC0, 648 lighthouses in the UK, Ireland, Isle of Man and Channel Islands;
  408 with an Admiralty number (a join key). Use for published coordinates.
- `osm_lighthouses.overpassql` -> `osm_lighthouses_2026-10-27.tsv`:
  OpenStreetMap (ODbL: attribution and share-alike if published), 566
  features; a cross-check only.
