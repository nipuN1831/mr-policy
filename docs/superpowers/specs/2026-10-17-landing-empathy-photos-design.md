# Landing Page: Empathy Photography Enhancement

**Date:** 2026-10-17
**Status:** Approved for implementation

---

## Goal

Add real documentary-style photography to the landing page to signal "this is a social initiative that helps real people navigate bureaucracy" — not a developer tool.

First impression in 3 seconds: *"Real people struggle with this — I can help."*

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Hero layout | Full-bleed background photo, dark overlay, centred text | Maximum impact, cinematic, works with any screen size |
| Hero overlay | ~50% dark (`rgba(8,22,14,0.52)`) uniform | Keeps text readable at all contrast levels |
| Hero photo subject | Single person mid-struggle with a government document | Direct connection to the cause — the moment before this tool helps |
| Topic card photos | Photo band at top of each card, dark-tinted, icon bottom-left | Magazine-style, each card tells its own story |
| Photo source | Unsplash CC0, real documentary-style | Authentic, no consent issues, free |
| Photo style rule | Candid, not posed. No smiling at camera. Subject mid-action | Authentic feel — UNICEF/Pratham pattern |

---

## Hero Section

**Photo:** One Unsplash image of a person (ideally a woman) holding or reading an official government document — ration card, form, notice. Looking focused or confused. Not staged.

**Search terms:**
- `"Indian woman reading government document"`
- `"India ration card paperwork"`
- `"India government form fill"`

**Chosen image:** To be picked from Unsplash before implementation. Store as `/static/img/hero-bg.jpg` (optimised, max 300KB, 1600px wide).

**Overlay:** `rgba(8, 22, 14, 0.52)` — dark green-black, matches brand palette.

**Text layout:** Centred. Existing hero text, subtitle, ask-box, country selector stay exactly as-is. No structural changes to HTML flow.

**CSS change in `landing.html` `<style>` block:**
```css
.hero {
  background-image: url('/static/img/hero-bg.jpg');
  background-size: cover;
  background-position: center top;
  position: relative;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(8, 22, 14, 0.52);
  z-index: 0;
}
.hero-inner {
  position: relative;
  z-index: 1;
}
```

---

## Topic Cards

4 cards, each gets a contextual photo band (height: 96px) at the top, above the existing title + description.

**Photo mapping:**

| Card | Subject | Search term |
|---|---|---|
| Know Your Rights | Person at ration shop or reading a notice | `"Indian village woman documents"` |
| Benefits & Schemes | Woman holding welfare documents | `"India woman welfare scheme document"` |
| Know Your Leaders | Village panchayat / community meeting | `"India panchayat meeting rural"` |
| Navigate Government | Person at government counter | `"India government office counter"` |

**Files:** `/static/img/card-rights.jpg`, `card-benefits.jpg`, `card-leaders.jpg`, `card-govt.jpg` — all max 100KB, 600px wide.

**Card HTML change (each `.topic-card`):**
```html
<div class="topic-card">
  <div class="topic-card-photo" style="background-image:url('/static/img/card-rights.jpg')"></div>
  <!-- existing accent bar, title, desc unchanged -->
</div>
```

**CSS:**
```css
.topic-card-photo {
  height: 96px;
  background-size: cover;
  background-position: center;
  border-radius: 12px 12px 0 0;
  filter: brightness(0.7) saturate(0.85);
  margin: -16px -16px 12px;  /* bleed to card edges */
}
```

---

## Image Hosting

Images stored as static files in `/static/img/`. Served by FastAPI's `StaticFiles` mount — no CDN needed for competition demo.

Add `/static/img/` to `.gitignore` if images are large — or commit compressed versions if under 1MB total.

---

## What Does NOT Change

- All text content, translations, i18n system
- Section structure, spacing, colours
- Mobile layout (hero stacks correctly, card photo band stays)
- `app.css` (no changes)
- All other pages (citizen, officials, about)
- Test suite — no new routes, no logic changes → 452 tests stay green

---

## Risks

| Risk | Mitigation |
|---|---|
| Hero text unreadable on light photo areas | Overlay opacity 0.52 tested in mockup — sufficient. Increase to 0.62 if needed. |
| Hero photo file too large → slow load | Compress to ≤300KB, serve with `Cache-Control: max-age=31536000` |
| Unsplash photo not ideal | User picks from search results before implementation step |
| Card photo bleeds outside card border-radius | `overflow:hidden` on `.topic-card` already present |

---

## Implementation Steps (for writing-plans)

1. User picks + downloads 5 photos from Unsplash (1 hero + 4 cards)
2. Compress: hero → 1600px wide ≤300KB, cards → 600px wide ≤100KB each
3. Add `/static/img/` directory, place files
4. Update `landing.html` CSS: hero `background-image` + `::before` overlay + `.hero-inner` z-index
5. Add `.topic-card-photo` div to each of 4 cards in HTML
6. Add `.topic-card-photo` CSS rule
7. Run `uv run pytest` → verify 452 tests still pass
8. Start dev server → visual check hero + cards on desktop + mobile
