# Third-party material

Everything we made here is 0BSD (code) or CC0 (data); see the top-level README. These are the things we didn't make, and their terms.

| what | where | terms |
|---|---|---|
| The *Reports on the Migration of Birds*, 1879–1887 (British Association) | quoted throughout; page scans linked | public domain |
| Project Gutenberg transcriptions of six of the reports | `sources/gutenberg/` | public domain texts, kept unmodified with Project Gutenberg's licence header, as it asks |
| Internet Archive OCR, hOCR and scan data of the nine reports | `sources/ia/` | derived from public-domain scans |
| Findlay, *A Description and List of the Lighthouses of the World* (1879, 1887); Edwards, *Our Seamarks* (1884) | `sources/lights/`, `data/lights/` (our transcriptions) | public domain |
| Old Standard TT typeface (Alexey Kryukov) | `film/engine/fonts/` | SIL Open Font License 1.1: [OFL-1.1-OldStandardTT.txt](OFL-1.1-OldStandardTT.txt) |
| Natural Earth 10 m land, via world-atlas 2.0.2 | `sources/coast/` | public domain |
| Wikidata lighthouse positions | `sources/lights/` | CC0 |
| NOAA/CIRES/DOE 20th Century Reanalysis version 3 (fetched by the tools, not kept here) | used in `data/weather/` | free to use, with this acknowledgement, as NOAA asks: "Support for the NOAA-CIRES-DOE Twentieth Century Reanalysis Project version 3 dataset is provided by the U.S. Department of Energy, Office of Science Biological and Environmental Research, by the National Oceanic and Atmospheric Administration Climate Program Office, and by the NOAA Physical Sciences Laboratory." The project also used resources of the National Energy Research Scientific Computing Center (NERSC), managed by Lawrence Berkeley National Laboratory, and of NOAA's Remotely Deployed High Performance Computing Systems ([psl.noaa.gov/data/20thC_Rean](https://psl.noaa.gov/data/20thC_Rean/)) |
| JPL DE440s ephemeris, gufm1 geomagnetic field model (fetched, not kept) | used by `tools/sky.py`, `tools/declination.py` | public |
| The keepers' voices in the film | `film/voice/takes/` | generated with ElevenLabs under a paid plan |

Not included: Marian Eagle Clarke's painting *Eddystone Lantern, 12 Oct 1901*, the film's visual key; see it in Robert Montgomerie's post [Blinded by the light](https://bou.org.uk/blinded-by-the-light/) (BOU, 2025). And not included: an OpenStreetMap extract of lighthouse positions (ODbL) that the work did not end up using.
