# Brand Post Recipe

An AI recipe that turns an Instagram brand into **three finished, ready-to-publish posts**:
media files, captions, format, goal and rationale for each post.

Demo brand: [Zmajska pivovara](https://zmajskapivovara.hr/) (Croatian craft brewery).
Post copy and the web UI are in Croatian; code and docs are in English.

> Work in progress. Full documentation (decisions, QA, limits, examples) is coming.

## How it works

The recipe runs in six separate phases. Each phase saves its result as JSON in `runs/<run_id>/`,
so a run can be stopped, inspected, edited and resumed from any phase.

| Phase | What happens | AI |
|---|---|---|
| `brief` | Validates inputs, reads past captions, fetches the brand website | - |
| `analysis` | Tone of voice, colors, photo style, products; verified facts vs. assumptions | Claude |
| `plan` | Three posts (single image / carousel): goal, concept, rationale, slide texts, scene prompts, captions | Claude |
| `create` | AI generates background scenes only; the real product photo, logo and headline are composited on top (Pillow), so labels are never distorted | Gemini |
| `review` | Visual and copy QA per slide; failed slides are regenerated with a fix, best attempt is kept | Claude |
| `deliver` | Final images, captions with hashtags, summary with cost, ZIP | - |

## Stack

- **Core:** Python 3.14, Anthropic SDK (structured outputs via Pydantic), Google GenAI SDK, Pillow
- **API:** FastAPI (runs phases in the background, edit the plan, serve files)
- **UI:** Vue 3, Vite, Tailwind CSS
- **Everything runs in Docker**; tests use fake AI clients, so they cost nothing

## Running

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY and GEMINI_API_KEY
docker compose build api
docker compose up -d          # API on :8001 (docs at /docs), UI on http://localhost:5175
```

Command line:

```bash
docker compose run --rm cli new inputs/zmajska/brief.yaml --stop-after plan
docker compose run --rm cli resume <run_id>
docker compose run --rm cli resume <run_id> --from plan --note "More humor"
docker compose run --rm cli status <run_id>
```

Tests:

```bash
docker compose --profile test run --rm pytest
docker compose run --rm --no-deps frontend npm test
```

Safety limits (`.env`): max generated images per run, max review retries, parallel image workers.

## Demo materials

Logo and product photos belong to Zmajska pivovara and are included only to make the demo runnable.
Screenshots and captions of the brand's Instagram posts are not published in this repository;
the recipe works without them (they are optional context for the analysis).
