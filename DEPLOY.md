# Deploying Pakka

Pakka is one FastAPI app (`app/main.py`) that serves the landing page, both demos and the API. It needs no database server and no API keys: everything runs offline by default.

| | Render | Vercel |
|---|---|---|
| How it runs | Always-on Docker container | Serverless function |
| Config file | `render.yaml` + `Dockerfile` | `vercel.json` + `.vercelignore` + `.python-version` |
| Demo state (journeys, merchant days) | Kept while the server runs | Kept per function instance; can reset when Vercel starts a new instance |
| Safety evals | Run during every build; a broken rule fails the deploy | Not run (GitHub Actions still runs them on every push) |
| Free-plan catch | Sleeps after ~15 min idle; the first visit takes ~1 min to wake | Uploads larger than 4.5 MB are rejected (use the sample files or a smaller photo) |
| **Best for** | **The live demo** | A quick shareable link |

---

## Render (recommended for the live demo)

1. Sign in at https://dashboard.render.com with GitHub.
2. Click **New → Blueprint** and pick the `Pakka` repository.
3. Render reads `render.yaml` and shows one web service, **pakka**. When it asks for `SARVAM_API_KEY`, paste a key for the Sarvam voice, or leave it empty to use the browser's voice.
4. Click **Apply**. The first build takes a few minutes: it installs packages, runs the safety evals, then starts the server.
5. Open the URL Render gives you (like `https://pakka-xxxx.onrender.com`). Check `/health`, `/demo` and `/merchant`.

Every push to `main` redeploys automatically.

**Before a demo:** open the URL a minute early to wake the free instance.

---

## Vercel

1. Sign in at https://vercel.com with GitHub.
2. Click **Add New → Project** and import the `Pakka` repository.
3. Leave the defaults. Vercel detects FastAPI from `app/main.py` and installs `requirements.txt` on Python 3.12 (from `.python-version`).
4. Optional: under **Environment Variables**, add `SARVAM_API_KEY`.
5. Click **Deploy**, then open the URL (like `https://pakka.vercel.app`).

Or from a terminal, with the Vercel CLI (48.1.8 or later):

```bash
npm i -g vercel
vercel          # preview deployment
vercel --prod   # production
```

`.vercelignore` keeps `.env`, tests and screenshots out of the upload.

**Limits to know:** each visit may land on a different function instance, and demo state lives in memory. If a demo screen suddenly starts over, press **Restart** or **Reset**. For a live presentation, use Render.

---

## Environment variables

| Name | Needed? | What it does |
|---|---|---|
| `SARVAM_API_KEY` | No | Sarvam Bulbul voice for "Listen" and the Soundbox. Without it, the browser's voice is used |
| `PAKKA_LLM_PROVIDER` | No | `sarvam`, `gemini` or `anthropic` to let an AI help read shop owners' replies. **Leave unset for demos**: the offline reader is the tested, fail-safe default |
| `PAKKA_LLM_API_KEY` / `PAKKA_LLM_MODEL` | Only with a provider | Key and model for Gemini or Anthropic |
| `PAKKA_DB` | No | SQLite file path. Default is in memory. On Vercel, only `/tmp` is writable |

Never commit keys. Set them in the platform's dashboard.

---

## Run it anywhere else with Docker

```bash
docker build -t pakka .
docker run -p 8000:8000 pakka            # http://localhost:8000
docker run -e PORT=10000 -p 10000:10000 pakka   # hosts that assign a port
```
