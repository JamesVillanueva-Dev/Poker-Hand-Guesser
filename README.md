# Poker Hand Range Estimator

Educational real-time poker analysis tool that estimates an opponent's range as a probability distribution over the 169 canonical starting hand classes.

## Architecture

- `frontend/`: React, TypeScript, Vite, Tailwind CSS, Zustand, Recharts dashboard
- `backend/`: FastAPI REST API and request/response schemas
- `engine/`: Bayesian range inference, hand matrix utilities, likelihood interfaces
- `models/`: PyTorch model definitions for future neural likelihood models
- `database/`: SQLite repository for player profiles, sessions, and imports
- `training/`: decoupled dataset and training pipeline
- `tests/`: focused unit and API tests

## Run Backend

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

The runtime requirements intentionally exclude PyTorch so the FastAPI app can install cleanly on Python 3.14 without compiling native extensions. Install the ML/training stack separately when you need it:

```powershell
python -m pip install -r requirements-ml.txt
```

## Run Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Run Everything

After installing the backend and frontend dependencies above, start both services from the project root:

```powershell
npm run dev
```

This starts FastAPI at `http://127.0.0.1:8000` and Vite at `http://127.0.0.1:5173`.

## API

- `POST /hand/start`
- `POST /action`
- `POST /showdown`
- `GET /range/{hand_id}`
- `GET /range/{hand_id}/snapshot/{sequence}`
- `GET /player/{player_id}`
- `GET /history`
- `POST /import`

## Inference Contract

The core update path is:

```python
update_range(current_distribution, action, board_state, player_profile)
```

The engine depends on a `LikelihoodModel` interface. The default implementation is `HeuristicLikelihood`; `NeuralLikelihood` is provided as the plug-in point for a trained PyTorch model.
