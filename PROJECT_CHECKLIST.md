# Final submission checklist

Before Git push / submission:

- [ ] `python -m pytest -q` passes.
- [ ] `.env` exists locally but is NOT tracked by Git.
- [ ] `OPENAI_API_KEY` is valid and has quota/billing configured.
- [ ] `python -m uvicorn main:app --host 0.0.0.0 --port 8000` starts cleanly.
- [ ] `GET /health` returns exactly `{"status":"ok"}`.
- [ ] `python public_sample_test.py` passes the official public cases (or failures are investigated before submission).
- [ ] Docker image builds and `/health` works from the container.
- [ ] Public endpoint is reachable from outside your local network.
- [ ] Repository contains no API key, token, `.env`, password, or secret.
- [ ] README has the final model/provider, run commands, public endpoint, and Docker image reference where appropriate.
- [ ] Repository visibility/timing follows the official event rulebook.
- [ ] 3-minute technical video prepared if required for the submission package/tie-break workflow.
