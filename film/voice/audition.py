"""Voice auditions for Round the Lantern: each role's audition line in 4 library voices (ElevenLabs eleven_v4, default settings).
python3 -I audition.py [--only ROLE_OR_VOICE ...] -> audition/<id>_<voice>_a.mp3 (+ .json character timestamps), auditions.html.
The key is read by tsubomi's helper (~/git/kel/film/voice11/el.py) and never printed. Prints credits used."""
import base64, html, json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(Path.home() / 'git/kel/film/voice11')); import el
OUT = HERE / 'audition'; OUT.mkdir(exist_ok=True)
MODEL = 'eleven_v4'
ONLY = sys.argv[sys.argv.index('--only') + 1:] if '--only' in sys.argv else []

LINES = {  # the `spoken` column of LINES.md
 'sb1': ('South Bishop', 'Welsh (Pembrokeshire), older man', 'Hundreds of birds of all sorts, flying around the lantern, from eleven P.M. to two-thirty A.M.'),
 'md1': ('the Maidens', 'Ulster (Antrim)', 'Striking, nine P.M. to one A.M.; about one hundred killed.'),
 'ed1': ('the Eddystone', 'West Country (Devon or Cornwall)', 'Eighty-two killed.'),
 'cg1': ('Coningbeg light-ship', 'Irish (Wexford)', 'Several about light, six P.M. to midnight; many killed striking, dropped into the sea.'),
 'cr1': ('Chickens Rock', 'Scots', 'Thrushes, Blackbirds, Larks, Starlings, and Chaffinches; numbers killed, from three A.M. till morning.'),
 'tk1': ('the Tuskar', 'Irish (Wexford), not the Coningbeg voice', 'Numbers striking at midnight; fifteen killed.'),
}
VOICES = {  # role -> (voice_id, short name, the library's own description, shortened)
 'sb1': [('004KTmksPwLFhbYi3ENc', 'zak', 'Zak: casual, Welsh native'),
         ('aKQdyEogZx5VoND0oujS', 'chris', 'Chris: natural Welsh accent, calm, grounded'),
         ('EmvLmNNZPnr2cOTaYrUc', 'rhys', 'Rhys Horler: Welsh actor'),
         ('sBU90Bu4NCleWDoNkGog', 'daniel', 'Daniel: mild Welsh accent')],
 'md1': [('n8EXn5l1hu3ASWq9KpAm', 'mark', 'Mark: soft Belfast accent, older'),
         ('Jot7IsvC9VkWPLPjLDKw', 'jimmy', 'Jimmy: Ulster Scots accent, middle-aged'),
         ('pg3548ZPhXWRcQhk1uvM', 'andrew', 'Andrew: Northern Irish'),
         ('7uDxvtPDB7zMehaRUyXh', 'john', 'John: warm Northern Irish')],
 'ed1': [('33aGKIlf0SKhTTaSWPVO', 'steve', 'Steve: West Country accent'),
         ('4Vl3K2x290GidNvuaLm7', 'matthew', 'Matthew Schmitz: older, thick West Country, rhotic (listed as a pirate)'),
         ('0c8J1N1i3sIcgiJsow0W', 'james', 'James: 50, West Country, slight accent'),
         ('U4Y0Z2HmYcQYMkJB8hrg', 'tom', 'Tom: rough West Country, weather-beaten (listed as a pirate)')],
 'cg1': [('73JgZZFYmivaO9TzZpzc', 'richie', 'Richie: Dublin, 40s'),
         ('2fe8mwpfJcqvj9RGBsC1', 'keanan', 'Keanan: Irish, conversational'),
         ('8SNzJpKT62Cqqqe8Injx', 'michael', 'Michael: soft Irish, gentle lilt'),
         ('1BfrkuYXmEwp8AWqSLWk', 'declan', 'Declan: old Irish (listed for horror)')],
 'cr1': [('U5UjeJMsOvyhYhXfZdvZ', 'adam', 'Adam: deep, gravelly, seasoned Scots, older'),
         ('csXxiUN2BUFflsCaDxPM', 'chris', 'Chris: casual Scots'),
         ('IJpdpIDF9zP8GMGKf42c', 'raymond', 'Raymond: middle-aged Scots, conversational'),
         ('y6p0SvBlfEe2MH4XN7BP', 'hugh', 'Hugh: middle-aged Scots')],
 'tk1': [('qwaVDEGNsBllYcZO1ZOJ', 'patrick', 'Patrick: warm, clear Irish'),
         ('9TYDukkUVpJPDSIuv3ir', 'darren', 'Darren: calm, deep Irish'),
         ('2WvAXMgrakBkapSmnlv7', 'flynn', 'Flynn: neutral Irish, well paced'),
         ('Xq2dbIWNPChFB77imiDe', 'gideon', 'Gideon: sea-worn Irish (listed as a pirate)')],
}

if __name__ == '__main__':
    before = el.call('GET', '/v1/user/subscription')[0]['character_count']
    sections = []
    for role, (station, accent, text) in LINES.items():
        rows = []
        for k, (vid, name, why) in enumerate(VOICES[role], 1):
            mp3 = OUT / f'{role}_{name}_a.mp3'
            if not mp3.exists() and (not ONLY or role in ONLY or name in ONLY):
                r, h = el.call('POST', f'/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128', {'text': text, 'model_id': MODEL})
                if 'audio_base64' not in r: print(role, name, r); continue
                mp3.write_bytes(base64.b64decode(r['audio_base64']))
                mp3.with_suffix('.json').write_text(json.dumps({'text': text, 'voice_id': vid, 'model': MODEL, 'alignment': r.get('alignment')}))
            if mp3.exists():
                rows.append(f'<li><span class=n>{k}</span><audio controls preload=none src="audition/{mp3.name}"></audio><details><summary>{name}</summary>{html.escape(why)}</details></li>')
        sections.append(f'<section><h2><code>{role}</code> {html.escape(station)}</h2><p class=meta>{html.escape(accent)}</p><p class=line>{html.escape(text)}</p><ol>{"".join(rows)}</ol></section>')

    (HERE / 'auditions.html').write_text(f'''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Keeper voices</title>
    <style>:root{{--bg:#f6f4ef;--fg:#1d1d1f;--mute:#6b6760;--rule:#d9d4c8}}@media (prefers-color-scheme:dark){{:root{{--bg:#141516;--fg:#e9e6df;--mute:#9a958b;--rule:#33332f}}}}
    body{{background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,serif;margin:0 auto;padding:24px 16px 60px;max-width:760px}}
    h1{{font-weight:normal;margin:0 0 4px}}h2{{font-weight:normal;font-size:20px;margin:0}}.meta,summary,.intro{{color:var(--mute);font:14px/1.5 system-ui,sans-serif}}
    section{{border-top:1px solid var(--rule);padding:18px 0}}.line{{font-style:italic;margin:6px 0 10px}}ol{{list-style:none;padding:0;margin:0}}
    li{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:6px 0}}.n{{font:600 14px system-ui;width:1.2em}}audio{{width:min(320px,70vw)}}details{{font:14px system-ui;color:var(--mute)}}</style>
    <h1>Keeper voices</h1><p class=intro>Round the Lantern: one audition line per keeper, four library voices each (ElevenLabs {MODEL}, default settings, first take, no retakes).
    Names and the library's own descriptions are folded away so you can listen first. Pick one per role, or say "none" and what's wrong.</p>
    {"".join(sections)}''')
    after = el.call('GET', '/v1/user/subscription')[0]['character_count']
    print('credits used this run:', after - before, '| total used:', after)
