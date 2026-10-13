# Getting started

## Explore the hosted demo

The GitHub Pages build is a static bundle backed by `frontend/public/data/bundle.json`. It does not need the Python API. Use it to inspect the precomputed decision, DNA, forensic sweep, and Replay Lab workflow.

## Run the backend

The backend requires Python 3.13 or newer and uses the dependencies in `backend/requirements.txt`.

```bash
python -m pip install -r backend/requirements.txt
uvicorn app.api.main:app --app-dir backend --reload
```

The API exposes `/health`, decision detail routes, counterfactual replay, forensic sweep, incident views, and decision DNA routes. The frontend can be pointed at the API through its live API configuration.

## Run the frontend

```bash
cd frontend
bun install
bun run dev
```

The frontend supports both the static bundle path and the live backend path. Run `bun run parity` when changing the TypeScript static engine or the bundle-generation contract.
