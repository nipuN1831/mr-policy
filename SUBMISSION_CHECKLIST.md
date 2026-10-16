# AI Builder Cup 2026 — Submission Checklist
**Deadline: 18 Oct 2026**

---

## BLOCKERS (submission invalid without these)

- [ ] **Deploy to Cloud Run** — get a live public URL
  ```
  gcloud config set project <YOUR_PROJECT_ID>
  gcloud run deploy policy-wind-tunnel --source . --region asia-southeast1 --allow-unauthenticated --set-secrets=GOOGLE_API_KEY=GOOGLE_API_KEY:latest
  ```
- [ ] **Demo video** — 3–4 min, public YouTube or Drive link
  - Record on the Cloud Run URL (Gemini works there, not localhost)
  - Show: landing chat → Gemini answer → redirect → citizen checker → deciding sentence highlighted
- [ ] **Pitch deck PDF** — public link (Google Slides → Download as PDF → Drive link)
- [ ] **README TODOs** — all 6 must be cleared before submission:
  - [ ] `TODO: Cloud Run URL` → paste real URL
  - [ ] `TODO: public video URL` → paste real URL
  - [ ] `TODO: link` (pitch deck) → paste real link
  - [ ] `TODO: names and roles` → add your name + role
  - [ ] `TODO: choose a licence` → add MIT licence (copy from choosealicense.com)
  - [ ] `TODO: ADK not yet wired` → either wire 1 agent or remove the claim

---

## JUDGING CRITERIA

### Technical Merit & Gen AI (40%)
- [x] Gemini 2.5-flash — extractor, chat, live leader lookup
- [x] Dockerfile + cloudbuild.yaml pushed to GitHub
- [ ] ADK — wire at least 1 agent OR remove claim from README
- [x] 450/452 tests passing
- [ ] Fix 2 failing tests (skip link + aria-current on landing page)

### Problem Alignment & Impact (25%)
- [x] Citizen checker — shows exact deciding sentence + source
- [x] Who-handles-my-problem — 23 keywords → specific redirect
- [x] India + Singapore scheme coverage
- [ ] Add 1 real sourced statistic to README (e.g. welfare exclusion error rate)

### Innovation & Creativity (25%)
- [x] One contract powers citizen + officials + software tests
- [x] Z3 boundary-pair generation
- [x] Gemini + keyword hybrid override (`powered_by: gemini+keyword`)
- [x] Smallest-change solver (what would change my answer)

### UX & Design (10%)
- [x] Chat answer inline below hero — no page jump
- [x] Redirect button prefills citizen page via sessionStorage
- [ ] Fix 2 failing accessibility tests (skip link + nav aria-current)

---

## ORDER TO FOLLOW

1. `gcloud deploy` → get live URL → paste into README
2. Fix 2 failing tests (Claude can do this)
3. Clear all 6 README TODOs
4. Record demo video on live URL
5. Pitch deck → export PDF → paste link in README
6. Submit

---

## QUICK COMMANDS

```bash
# Start local server
uv run uvicorn policy_wind_tunnel.service.app:app --reload --port 8000

# Run tests
uv run pytest tests/ -q

# Deploy
gcloud run deploy policy-wind-tunnel --source . --region asia-southeast1 --allow-unauthenticated --set-secrets=GOOGLE_API_KEY=GOOGLE_API_KEY:latest

# Push to GitHub
git add -A && git commit -m "..." && git push origin master
```
