# PolicySim (vendored subset)

- Source: https://github.com/opencausality/PolicySim, commit 3d3d3d4
- Licence: `pyproject.toml` declares `license = "MIT"` and README says "MIT licensed". No LICENSE file present in the repository; no copyright holder named. A request to add one is planned.
- Copied: `exceptions.py`, `data/schema.py`, `causal/builder.py`, `causal/validator.py`, `simulation/engine.py`, `simulation/monte_carlo.py`
- Changes: all `from policysim.` imports rewritten to our package path; logger names changed; `calibrate_from_data` (pandas) removed.
- Not copied: CLI, LLM adapter, visualiser, API server, extraction.
- Used only for the clearly-labelled "Exploratory impact model" in Policy Wind Tunnel. Its numbers are model assumptions, not predictions.
