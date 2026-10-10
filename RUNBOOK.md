# Weekly run: QEG explainer reels

Two fact-checked explainer Reels a week for Qarya (QEG), posted **Tuesday and Friday at 18:00 Malaysia time**
on Instagram, Facebook and TikTok. Solomon approved these to publish **without** the Monday approval
(Drive "QEG Brand Brain" → "11 — Explainer reels (rules & topic bank)"). Work through it without asking questions.

## 0. Set up (fresh session)

```bash
cd <this repo>
bash kit/setup.sh          # ~800 MB of models from GitHub releases, once per session
git config user.name "Claude (QEG explainers)"; git config user.email "qaryaeducationgroup@gmail.com"
```

## 1. Read the rules

- Drive folder "QEG Brand Brain" (id 1L9_99BPfNcCu5NnKzCNTa9moZNl4jEVm): read "11 — Explainer reels (rules & topic bank)"
  in full and Appendix A of "10 — Autopilot manual". File 11 wins for explainers; all red lines still apply.
- `topics/bank.json` is the live topic list (status: ready / made / scheduled / posted / hold).

## 2. Find the slots

- Target: the next **two free** Tuesday/Friday 18:00 slots (Asia/Kuala_Lumpur), starting at least 24 h from now and
  looking up to 14 days ahead. Explainers start from Tuesday 20 Oct 2026; never use an earlier slot.
- Metricool brand 7143593: `getBrandSettings`, then `getScheduledPosts` for each candidate date (extendedRange true).
  A slot is taken if any Reel (explainer or filmed) is already at 18:00 that day: skip it, don't move other posts.
- If a `made` episode in `topics/bank.json` has never been scheduled, schedule it into the first free slot before making new ones.
- If no slot is free, make nothing new; say so in the report.

## 3. Pick and verify topics

- Choose `ready` topics; alternate kinds (psychology / history & origins / how operations work); don't repeat a theme two posts in a row.
- Open at least 2 of the listed sources per topic (WebFetch) and confirm every claim you will narrate.
  Say only the topic's `safe` claims, never its `avoid` items. Legends are told as legends.
- If sources disagree or a page is gone, find a replacement reputable source or pick another topic.
- New topics may be added to the bank only after the same 2-source check.

## 4. Write the episode

`episodes/<NNN-slug>/` (number = highest existing + 1):
- `spec.json`: see `SCENES.md`; model it on `episodes/002-peak-end/spec.json`.
  Hook in the first line (a surprising claim or question), 12–16 lines, 38–52 s, 4–5 scenes + end card,
  the last content line says what it means for hospitality. British spelling. No questions to the viewer that need a reply.
- `caption.md`: hook line · 2–3 short sentences · `Sources: …` (short names) · the one CTA
  `Curious about a career in hospitality? WhatsApp us at 019-862 6704.` · 5–8 hashtags incl. #Hospitality101 #HospitalityLiteracy #QaryaHospitality.
- `sources.md`: each narrated claim → its sources (title, publisher, URL).

## 5. Build and check

```bash
python3 kit/make.py episodes/<id>/spec.json voice      # TTS + word timings (~2 min)
python3 kit/make.py episodes/<id>/spec.json preview    # -> build/preview.jpg
```
**Look at `build/preview.jpg`** (Read it). Fix: empty frames longer than ~1.5 s, overlaps, text too close to captions
(y > 1330), icons that don't read, wrong timing. Re-run `preview` (or `still <t>`) until it's right. Then:
```bash
python3 kit/make.py episodes/<id>/spec.json mix
python3 kit/make.py episodes/<id>/spec.json video --jobs 2     # ~10 min
python3 kit/make.py episodes/<id>/spec.json deliver
python3 kit/make.py episodes/<id>/spec.json check              # must print CHECK PASSED
```
If `check` fails on ASR, rewrite the line the voice mangles (spell it phonetically in the voice text only) and rebuild from `voice`.

## 6. Publish the media

```bash
python3 kit/publish.py episodes/<id>/out/Qarya_<Title>.mp4 episodes/<id>/out/Qarya_<Title>_cover.jpg
```
It prints the public URLs (raw.githubusercontent.com, branch `media`). This session can't open those URLs itself;
confirm the files exist with `gh api repos/<owner>/<repo>/contents/<file>?ref=media`.

## 7. Schedule

`createScheduledPost` (brand 7143593, timezone Asia/Kuala_Lumpur), one call per video:
- date: the slot, 18:00; `autoPublish: true`; `draft: false`
- providers: instagram + facebook + tiktok
- `instagramData: {type: "REEL", showReelOnFeed: true, isAiGenerated: true}`
- `facebookData: {type: "REEL"}`
- `tiktokData: {privacyOption: "PUBLIC_TO_EVERYONE", isAigc: true}`
- media: the mp4 URL; `videoThumbnailUrl`: the cover URL
- text: `caption.md`

Then `getScheduledPosts` for that date and confirm the post is there. If Metricool rejects the media URL,
try once more; if it still fails, stop and report it (don't fall back to drafts silently).

## 8. Record and report

- `topics/bank.json`: set the topic's `status` to `scheduled`, add `"episode"` and `"slot"`. Commit to `main` with the episode folder
  (spec, caption, sources — build/ and out/ are ignored) and push.
- Send Solomon one message: Done (titles, slots, one-line summary each) · Needs you (anything) · Coming up (next 2 topics).
  Attach both videos with SendUserFile.
- Never: post anything that fails the fact standard or `check`, use real people or AI-generated people, name partners,
  mention QEG prices, or promise jobs/salaries.
