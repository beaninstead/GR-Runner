# Future Run (GR Runner)

Mobile-first pygame game, playable on the web via [pygbag](https://pygame-web.github.io).

## Play (Vercel)

- Live URL: https://future-run.vercel.app/
- Vercel project: `future-run` (`prj_axo4mB9dgzqZLtyixsEzVAWWHav5`)
- **Root Directory must be:** `web_app/build/web`
  (Framework Preset: Other / static files. Do not deploy from the repo root.)

Hard-refresh after deploys (`Cmd+Shift+R` / clear site data) so `index.html` is not cached.

## Local desktop

```bash
pip install -r requirements.txt
python main.py
```

## Web build folder

Static site files live in `web_app/build/web/`:

- `index.html` — pygbag loader
- `web_app.tar.gz` — game assets (~3MB)
- `vercel.json` — MIME / cache headers for the archive

`web_app/requirements.txt` is intentionally empty so cold loads do **not** fetch a ~12MB numpy wheel from the pygame-web CDN.
