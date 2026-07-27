# Poker Hand Range Estimator

Educational poker analysis tool that estimates an opponent's range as a probability
distribution over the 169 canonical starting hand classes, updates it via Bayes as
actions are observed, and **grades itself at showdown** so you can tell whether it is
any good.

## How good is it?

The unit is **bits of skill**: `-log2(1/169)` (7.40 bits, the cost of a uniform guess)
minus the model's own `-log2 P(true class)`. Positive means better than guessing.

Against a scripted opponent over 200 hands (`python -m scripts.benchmark --hands 200 --compare`):

| | mean skill at showdown | flop | turn | river |
|---|---|---|---|---|
| board-blind engine (before) | **+0.36 bits** | +0.29 | +0.36 | +0.36 |
| board-relative engine (now) | **+1.24 bits** | +0.86 | +1.04 | +1.24 |

That number is measured against a *scripted* opponent, so it says the engine recovers a
known generating policy — a necessary condition for being useful on real hands, not a
sufficient one. The dashboard reports skill over your own real showdowns, separately,
and says plainly when it is at or below zero.

The flagship regression, on a `K♠7♦2♣` flop facing a 90%-pot bet:

| | 77 (a flopped set) | AQo (complete air) |
|---|---|---|
| before | 0.508% | 1.853% |
| now | **1.072%** | 0.343% |

## Architecture

- `frontend/`: React, TypeScript, Vite, Tailwind CSS, Zustand, Recharts dashboard
- `backend/`: FastAPI REST API, request/response schemas, opponent statistics
- `engine/`: board evaluator, action policy, Bayesian range inference, scoring, strategy
- `models/`: PyTorch model definition for a future neural likelihood
- `database/`: SQLite repository for profiles, sessions, imports, and scored predictions
- `training/`: dataset collection and training pipeline
- `tests/`: unit, calibration, and API tests
- `scripts/benchmark.py`: measures skill in bits, before and after a change

### The three pieces that matter

**`engine/evaluator.py` — board-relative strength.** For a given board it enumerates
every live two-card combo, evaluates each with a 7-card rank-histogram evaluator, and
ranks them. A hand class's strength is the mean percentile of its surviving combos, so
`77` on `K72` is a set (99.6th percentile) and `AQo` is air. Card removal is exact:
`AA` on an `A♠A♥K♦` board has one live combo, not six, and a class with zero live combos
holds probability exactly 0 forever. Results are memoized per `(board, dead cards)`.

**`engine/likelihood.py` — a normalized action policy.** `π(action | hand, board,
profile, context)` is a softmax over per-action utility logits, summing to exactly 1.0
over the *legal* action set (you cannot check facing a bet; you cannot three-bet without
a raise in front). Where a real observed statistic exists for a spot — VPIP, PFR, 3bet,
cbet — two scalar tilts are solved by bisection so that aggregating the policy over the
whole range reproduces that opponent's measured frequency. Poker logic decides *which*
hands take an action; the observed stat decides *how often*. Spots with no measured
statistic are left uncalibrated rather than pretending to a frequency nothing observed.

**`engine/scoring.py` — the loop that closes.** `POST /showdown` scores the range as of
*every street*, persists each score to a `predictions` table, updates the opponent's
measured bluff frequency from what they actually tabled, and appends training rows to
`training/data/showdowns.jsonl` in the shape `training/dataset.py` has always expected.
`GET /calibration` returns running mean skill overall, per street, and over the last 20.

## Run Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

The runtime requirements intentionally exclude PyTorch so the FastAPI app installs
cleanly on Python 3.14 without compiling native extensions. The evaluator is pure Python
and adds no dependencies. Install the ML/training stack separately when you need it:

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

```powershell
npm run dev
```

Starts FastAPI at `http://127.0.0.1:8000` and Vite at `http://127.0.0.1:5173`.

## Tests and benchmark

```powershell
python -m pytest tests -q
python -m scripts.benchmark --hands 200 --compare
```

The calibration invariant in `tests/test_policy_calibration.py` is the test that keeps
the policy honest: for four opponent profiles across four board textures, the
range-aggregated action frequencies must match the profile's stats within five points.
`tests/test_board_blindness.py` replaces the preflop ranking with a landmine and runs the
whole postflop stack, so no postflop path can start consulting it again.

## API

- `POST /hand/start` — new hand; applies card removal for known hero cards
- `POST /action` — observe an action; an opponent fold ends the hand (later actions 409)
- `POST /showdown` — score the prediction per street, persist it, emit training data
- `GET /calibration` — running measured skill in bits
- `GET /range/{hand_id}` and `GET /range/{hand_id}/snapshot/{sequence}`
- `GET /player/{player_id}` — profile plus the sample size behind every stat
- `GET /history`, `POST /import`

## Inference Contract

```python
update_range(current_distribution, action, board_state, player_profile, previous_dead)
```

The engine depends on a `LikelihoodModel` protocol with two methods:
`action_probabilities` (a distribution over legal actions for one hand class) and
`calibrate` (solve the tilts against the prior). `PolicyLikelihood` is the default.
`NeuralLikelihood` is the plug-in point for a model trained on the collected dataset —
it is deliberately still unimplemented, because a network trained on a few dozen
self-collected showdowns would be worse than the heuristic and would obscure whether
the policy is working.

## Using the dashboard

The screen is split: a persistent left rail for entering the hand, and a reading region
that never scrolls away from it. On a 1440×900 laptop the heatmap and the recommended
action are both visible while you type.

- **The pot is derived, never typed.** It follows from the actions logged so far. There
  is an explicit override for reconstructing a hand from partway through.
- **Only legal actions are offered.** The API returns the legal set per street from the
  same `legal_actions()` the policy uses, so you cannot log a check facing a bet. When a
  street's betting has closed, the controls say so instead of offering a stale list.
- **One card picker** for hero, board, and showdown cards. A card already used in the
  hand cannot be picked twice, and unrecognised input is rejected visibly rather than
  dropped.
- **Keyboard**: `1`–`5` pick the legal actions, `Enter` applies, `→` advances the street,
  `←` steps back through the timeline, `?` lists the shortcuts.

## What the numbers on screen mean

- **Measured skill** — bits better than a uniform guess, over showdowns you recorded. If
  it is at or below zero the dashboard says so.
- **Confidence** on a recommendation — derived from measured skill on comparable spots.
  With no showdowns scored it reads *"model certainty (unvalidated)"* and sits at 50%.
- **Sample size** under each opponent stat — the denominator that rate was measured over.
  Rates are Beta-Binomial shrunk toward population priors, so `n=2` stays near the prior.
- **Expected value** — every candidate line is priced in big blinds against the modeled
  range, with fold equity taken from the same policy. The recommendation is the maximum.

When the backend is unreachable the dashboard shows a disconnected panel and **no
heatmap**. It never renders invented numbers styled as a real prediction.
