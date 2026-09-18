# GridWise — BUP CSE Fest 2026 Preliminary

A submission-ready FastAPI service for the **Smart Campus Energy Optimization Challenge — LLM-Assisted Operator Directive Interpretation**.

## Architecture

`request -> LLM interpreter -> deterministic guardrails -> LP optimizer -> final replay validator -> JSON response`

The LLM is used only to convert natural-language `operator_notes` into the supported structured directives. Deterministic code validates the LLM output before it is allowed to affect the mathematical optimizer.

## Required endpoints

- `GET /health`
- `POST /optimize-energy`

`GET /health` returns:

```json
{"status":"ok"}
```

## Supported directives

- `solar_reduction`
- `minimum_battery_reserve`
- `no_charge_window`
- `no_discharge_window`
- `max_grid_window`
- `no_op`

## Technology

- Python 3.12
- FastAPI
- OpenAI Responses API structured output for operator-note interpretation
- Pydantic validation
- SciPy HiGHS linear-programming optimizer
- Pytest
- Docker

## Local quickstart (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a valid API key:

```env
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-5.6-luna
```

Start the API:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Check readiness:

```powershell
curl http://127.0.0.1:8000/health
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Local quickstart (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Tests that do not call the LLM

The unit tests use the organizer's public ground-truth directive interpretations to verify the optimizer, energy accounting, public optimal costs, request validation, and health endpoint.

```bash
python -m pytest -q
```

## Run all 10 official public cases end-to-end

First start the server with a working LLM API key. In another terminal:

```bash
python public_sample_test.py --base-url http://127.0.0.1:8000
```

This script sends every official `case.input` to `/optimize-energy`, compares the machine-checkable directive semantics, and verifies public optimal cost/grid totals within the organizer tolerance. It makes real LLM calls.

## Example request

Use the complete inputs from `public_sample_cases.json`. The shape is:

```json
{
  "scenario_id": "GRID-101",
  "operator_notes": [
    "Solar output will drop to about 20% from 1 PM to 3 PM."
  ],
  "hours": [
    {"hour": 0, "demand_kwh": 180, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
  ],
  "battery": {
    "capacity_kwh": 500,
    "initial_energy_kwh": 200,
    "minimum_energy_kwh": 50,
    "max_charge_kwh_per_hour": 100,
    "max_discharge_kwh_per_hour": 100
  }
}
```

The real request must contain all 24 unique hours `0..23`.

## Response fields

A successful response contains:

```text
scenario_id
directive_interpretation
hourly_plan
total_grid_kwh
total_cost_bdt
peak_grid_kwh
plan_summary
```

Each hourly plan entry contains:

```text
hour
grid_kwh
solar_used_kwh
battery_action
battery_kwh
battery_energy_after_kwh
```

## Optimization model

For each hour `h`, the optimizer uses a signed battery delta:

- positive delta = charge
- negative delta = discharge

Energy balance is enforced as:

```text
grid[h] + solar_used[h] = demand[h] + battery_delta[h]
```

This is equivalent to:

```text
grid + solar + battery_discharge = demand + battery_charge
```

The optimizer also enforces:

- battery capacity and active minimum reserve
- hourly charge/discharge rate limits
- effective solar after solar-reduction directives
- no-charge / no-discharge windows
- maximum-grid windows
- non-negative grid import
- end-of-day battery neutrality

Objective:

```text
minimize SUM(grid_kwh[h] * tariff_bdt_per_kwh[h])
```

## Deterministic guardrails

LLM output is rejected unless it satisfies all required machine-checkable conditions, including:

- one entry per operator note in `note_index` order
- only supported directive types
- `no_op` => `applies=false` and `structured_adjustment=null`
- all other directives => `applies=true`
- unique ascending hours in `0..23`
- solar factor in `[0,1]`
- reserve does not exceed battery capacity
- non-negative grid cap
- exact adjustment shape for each directive type

The final schedule is independently replayed before it is returned.

## Error handling

- Structurally invalid requests: HTTP `400`
- Controlled LLM/optimizer/final-validation failures: HTTP `500`
- API keys, raw prompts containing secrets, and stack traces are not returned to clients

## Docker

Build:

```bash
docker build -t gridwise:latest .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY="your_real_key_here" \
  -e OPENAI_MODEL="gpt-5.6-luna" \
  gridwise:latest
```

Windows PowerShell:

```powershell
docker run --rm -p 8000:8000 `
  -e OPENAI_API_KEY="your_real_key_here" `
  -e OPENAI_MODEL="gpt-5.6-luna" `
  gridwise:latest
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

### Docker registry fallback

Tag and push to your registry after testing:

```bash
docker tag gridwise:latest YOUR_DOCKERHUB_USERNAME/gridwise:bup-cse-fest-2026
docker push YOUR_DOCKERHUB_USERNAME/gridwise:bup-cse-fest-2026
```

Put the final pullable image reference in your hackathon submission form/README before the deadline if required by the organizer workflow.

## Deployment

Deploy the same repository on any platform that exposes a public HTTP URL. Configure these environment variables in the platform dashboard:

```text
OPENAI_API_KEY
OPENAI_MODEL=gpt-5.6-luna
```

Start command:

```text
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

After deployment, test from outside your development machine:

```text
GET  https://YOUR_PUBLIC_URL/health
POST https://YOUR_PUBLIC_URL/optimize-energy
```

No login, VPN, manual approval, or private-network access should be required for the judge.

## Security

**Do not commit `.env` or any API key.** `.env` is already listed in `.gitignore`.

Before pushing:

```bash
git status
git grep -n "sk-" || true
```

## Suggested Git workflow

```bash
git init
git add .
git commit -m "GridWise preliminary submission"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Follow the organizer's repository timing/visibility rules for the event.

## Files

```text
.
├── main.py
├── gridwise_app/
│   ├── models.py
│   ├── llm_interpreter.py
│   ├── guardrails.py
│   ├── optimizer.py
│   ├── validator.py
│   └── service.py
├── tests/
│   ├── test_api_basics.py
│   └── test_optimizer_public_cases.py
├── public_sample_cases.json
├── public_sample_test.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Known operational requirement

The end-to-end endpoint depends on the configured hosted LLM being available, within quota, and fast enough during evaluation. The optimizer and validator are deterministic; only operator-note interpretation uses the hosted model.
