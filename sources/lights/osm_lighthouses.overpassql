[out:csv(::type,::id,::lat,::lon,name,"seamark:light:character","seamark:light:period","seamark:light:reference","ref:wikidata",wikidata;true;"\t")][timeout:90];
(
  area["ISO3166-1"="GB"][admin_level=2];
  area["ISO3166-1"="IE"][admin_level=2];
  area["ISO3166-1"="IM"][admin_level=2];
)->.a;
nwr(area.a)["man_made"="lighthouse"];
out center;
