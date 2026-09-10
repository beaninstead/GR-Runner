# Future Run (GR Runner)

Mobile-first pygame game, playable on the web via [pygbag](https://pygame-web.github.io).

## Play (Vercel)

- Live URL: https://future-run.vercel.app/
- Vercel project: `future-run` (`prj_axo4mB9dgzqZLtyixsEzVAWWHav5`)
- **Root Directory must be:** `web_app/build/web`
  (Framework Preset: Other / static files. Do not deploy from the repo root.)

Hard-refresh after deploys (`Cmd+Shift+R` / clear site data) so `index.html` is not cached.

## itch.io HTML5

Upload **`future-run-itch.zip`** (or rebuild it from `web_app/build/web` with only):

- `index.html`
- `favicon.png`
- `web_app.apk`  ← required on `*.itch.zone` (do **not** upload only `web_app.tar.gz`)

Embed settings:

- Kind: **HTML**
- Enable **This file will be played in the browser**
- Viewport: **540×960** (portrait) preferred, or **1080×1920**. The game letterboxes itself, but a portrait embed size avoids large side bars.
- **Do not** stretch the embed to a landscape size (e.g. 960×540 / 16:9) — older builds looked horizontally stretched; current builds pillarbox instead.
- **Do not** enable Frame Options → **SharedArrayBuffer** — pygbag loads `pygame-web.github.io` CDN assets that lack `Cross-Origin-Resource-Policy`, so COEP/`require-corp` blocks the runtime and leaves a stuck “Downloading…” screen.

Vercel/GitHub Pages keep using `web_app.tar.gz`; itch uses `web_app.apk`.

## Local desktop

```bash
pip install -r requirements.txt
python main.py
```

## Web build folder

Static site files live in `web_app/build/web/`:

- `index.html` — pygbag loader
- `web_app.tar.gz` — game assets for Vercel (~13MB)
- `web_app.apk` — same assets as a zip, for itch.io
- `vercel.json` — MIME / cache headers for the archive

`web_app/requirements.txt` is intentionally empty so cold loads do **not** fetch a ~12MB numpy wheel from the pygame-web CDN.
