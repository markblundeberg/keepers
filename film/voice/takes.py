"""Final takes for Round the Lantern: 3 takes of each line in the voice Mark picked from auditions.html (28 Oct 2026).
python3 -I takes.py -> takes/<id>_<voice>_<take>.mp3 (+ .json character timestamps), takes.html. Prints credits used."""
import base64, html, json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(Path.home() / 'git/kel/film/voice11')); import el
import importlib.util   # load this folder's audition.py by path: Kel's voice folder (on sys.path for el) has its own audition.py
_spec = importlib.util.spec_from_file_location('keepers_audition', HERE / 'audition.py'); _a = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_a)
A_LINES, VOICES, MODEL = _a.LINES, _a.VOICES, _a.MODEL
OUT = HERE / 'takes'; OUT.mkdir(exist_ok=True)
PICK = {'sb1': 'chris', 'md1': 'mark', 'ed1': 'tom', 'cg1': 'keanan', 'cr1': 'adam', 'tk1': 'flynn'}   # Mark, 28 Oct
VID = {role: next(v for v, n, _ in VOICES[role] if n == name) for role, name in PICK.items()}
LINES = [(r, A_LINES[r][0], PICK[r], VID[r], A_LINES[r][2]) for r in ['sb1']] + [
    ('sb2', 'South Bishop', 'chris', VID['sb1'], 'Several birds seen on the rock at daylight, with broken wings.'),
    ('sb3', 'South Bishop', 'chris', VID['sb1'], 'Two hundred and seventy-two killed.')] + [
    (r, A_LINES[r][0], PICK[r], VID[r], A_LINES[r][2]) for r in ['md1', 'ed1', 'cg1', 'cr1', 'tk1']]
before = el.call('GET', '/v1/user/subscription')[0]['character_count']
rows = []
for lid, station, name, vid, text in LINES:
    cells = []
    for k in (1, 2, 3):
        mp3 = OUT / f'{lid}_{name}_{k}.mp3'
        if not mp3.exists():
            r, h = el.call('POST', f'/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128', {'text': text, 'model_id': MODEL})
            if 'audio_base64' not in r: print(lid, k, r); continue
            mp3.write_bytes(base64.b64decode(r['audio_base64']))
            mp3.with_suffix('.json').write_text(json.dumps({'text': text, 'voice_id': vid, 'model': MODEL, 'alignment': r.get('alignment')}))
        cells.append(f'<li><span class=n>{k}</span><audio controls preload=none src="takes/{mp3.name}"></audio></li>')
    rows.append(f'<section><h2><code>{lid}</code> {html.escape(station)} <span class=meta>· {name}</span></h2><p class=line>{html.escape(text)}</p><ol>{"".join(cells)}</ol></section>')
(HERE / 'takes.html').write_text(f'''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Keeper takes</title>
<style>:root{{--bg:#f6f4ef;--fg:#1d1d1f;--mute:#6b6760;--rule:#d9d4c8}}@media (prefers-color-scheme:dark){{:root{{--bg:#141516;--fg:#e9e6df;--mute:#9a958b;--rule:#33332f}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,serif;margin:0 auto;padding:24px 16px 60px;max-width:760px}}
h1{{font-weight:normal;margin:0 0 4px}}h2{{font-weight:normal;font-size:20px;margin:0}}.meta,.intro{{color:var(--mute);font:14px/1.5 system-ui,sans-serif}}
section{{border-top:1px solid var(--rule);padding:18px 0}}.line{{font-style:italic;margin:6px 0 10px}}ol{{list-style:none;padding:0;margin:0}}
li{{display:flex;align-items:center;gap:10px;margin:6px 0}}.n{{font:600 14px system-ui;width:1.2em}}audio{{width:min(320px,70vw)}}</style>
<h1>Keeper takes</h1><p class=intro>Round the Lantern: three takes of each line in the voice Mark picked (ElevenLabs {MODEL}, default settings). Pick a take per line.</p>
{"".join(rows)}''')
after = el.call('GET', '/v1/user/subscription')[0]['character_count']
print('credits used this run:', after - before, '| total used:', after)
