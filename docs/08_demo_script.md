# MomentOS — 2:45 Demo Video Script

**Recording status:** script prepared; no video has been recorded, uploaded, or published. Use the deployed application only after deployment is authorized and the production verification checklist passes. Do not show a mocked provider response as live AI.

## Story and timing

| Time | On-screen actions | Voiceover |
|---|---|---|
| **00:00–00:15** | Open the public HTTPS app at the landing page. Show the MomentOS title and three celebration types. | “Planning a celebration means coordinating dozens of decisions that affect one another. MomentOS turns those decisions into a plan you can understand, adjust, and trust before you commit.” |
| **00:15–00:40** | Select wedding. Enter “Nagpur Garden Wedding,” 150 guests, ₹6,00,000, and a date. In the description, state the user's own illustrative assumptions: catering at ₹1,000 per guest and a venue capacity of 180. Add a short priority such as “outdoor, elegant, family-friendly.” Start planning. | “I’m planning an outdoor wedding in Nagpur for 150 guests, with a six-lakh-rupee budget. I’ve included my own planning assumptions for catering and venue capacity; these are not live vendor quotes.” |
| **00:40–01:05** | Wait for the Event Architect. Show extracted requirements and the structured blueprint. Review themes, activities, milestones, vendor categories, and the visible budget assumptions. Point out any missing-detail prompts. Save only after reviewing and explicitly confirming. | “GPT-6 Luna interprets the brief and returns a structured concept with useful themes, activities, and planning guidance. I can review the assumptions before saving. The model suggests and explains; the application validates the result, and Python handles the authoritative calculations.” |
| **01:05–01:25** | Open Command Center. Show the saved event, budget health, planning progress, next task, and milestone timeline. Briefly open Budget Studio and show projected allocations. | “The Command Center brings the saved plan together: what the budget is doing, what needs attention, and what comes next. The estimates are editable planning inputs, not verified market prices.” |
| **01:25–02:05** | Open Ripple Engine. Change attendance from 150 to 200 and preview. Show catering delta, new projected spend, affected seating/tasks, and capacity warning if the saved assumption triggers it. Pause on before/after. Do not confirm yet. | “Now the guest list changes by fifty. Ripple Engine recalculates the per-guest catering impact and checks the connected plan: seating, tasks, capacity, and budget. Here, the displayed estimate rises by fifty thousand rupees because the saved catering assumption is one thousand per guest. The venue warning appears because the plan’s stated capacity is 180. This is a preview; nothing has been saved.” |
| **02:05–02:30** | Show the recommended adjustment or risk. Cancel once if time allows and point out that the event remains at 150. Reopen the same preview and explicitly confirm. Show the updated 200 guest value. Open Copilot and ask: “How can I bring this plan back under budget without reducing catering?” Show its contextual response. | “I can cancel and keep the original plan, or review the consequences and confirm. After confirmation, the saved event updates. The Copilot can then discuss trade-offs using this event’s saved context; it does not claim that a suggested saving has happened until a change is actually made.” |
| **02:30–02:45** | Refresh the event page to show persistence. End on the MomentOS mark. | “MomentOS connects generative planning with deterministic checks and explicit user control—so every celebration can move from an idea to a plan with fewer surprises.” |

## Pre-recording checklist

- [ ] Use the deployed app only after the public release checklist is green.
- [ ] Confirm `AI_MODE=live` and `OPENAI_MODEL=gpt-6-luna` in the server configuration without showing secrets.
- [ ] Confirm a small AI usage limit and provider spend cap; do not run repeated rehearsals against the live API.
- [ ] Use a fresh session and a new event; avoid real guest names, contacts, or private notes.
- [ ] Include user-supplied illustrative catering and venue-capacity assumptions in the event brief, then inspect the generated values before recording.
- [ ] Check the deterministic arithmetic shown by the current plan. If the rate or capacity differs from the script's example, update the narration to match the UI or use a verified user-entered assumption.
- [ ] Verify the actual blueprint generation and the explicit save before recording; ensure the UI does not show “Mock provider.”
- [ ] Verify the AI Copilot works in the deployed environment. If not, omit that scene and state the real limitation; do not stage a fake response.
- [ ] Clear desktop notifications, close unrelated tabs, hide address-bar secrets, and use a clean browser profile.
- [ ] Rehearse once with demo mode or a mocked provider, then switch to the authorized live environment only for the final take.

## Recording settings

- Capture at **1920×1080**, 30 fps, with browser zoom at 100% and the app viewport sized to avoid responsive breakpoints changing mid-take.
- Record a clean microphone track; speak at a measured pace, leave short pauses for the charts and Ripple numbers, and reduce background noise.
- Keep cursor movement deliberate. Use a subtle highlight on the guest-count change and the preview/confirm boundary.
- Capture the rendered application, not developer tools, admin consoles, environment variables, secret managers, or API logs.
- If narration is recorded separately, align the edit to the timestamps above. Add captions and check caption accuracy, especially “GPT-6 Luna,” “₹6,00,000,” and “₹50,000.”
- Use readable on-screen captions, sensible audio levels, and no copyrighted music unless you have the rights to publish it.

## Publish checklist (requires separate authorization)

- [ ] Review every frame and audio track for credentials, personal data, browser notifications, and misleading claims.
- [ ] Confirm the demo shows the actual deployed application and the real feature behavior.
- [ ] Upload to YouTube or a permitted Drive location and make the final URL accessible to judges (public or link-accessible as permitted by the competition).
- [ ] Open the link in a signed-out/private browser window and verify playback, captions, and audio.
- [ ] Add the verified public video URL to `docs/08_submission_materials.md` and the competition form.

No video URL is available yet.
