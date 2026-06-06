# Tiny Stories Korean Webtoon Generated Cover Fallbacks

Generated on 2026-06-06 with built-in Image Generation. These are internal
fallback covers for generated stories when no story-specific cover URL exists.
All accepted assets are 1672 x 941 JPGs, Korean webtoon / manhwa direction,
dark red-black-gold palette, no readable text, no logo, no baked UI.
Current accepted generated cover pool: 20 covers.

## Accepted Assets

| Theme key | File | Intended routing keywords |
| --- | --- | --- |
| `generated_entertainment_backstage_disappearance` | `/webtoons/covers/generated/cover-entertainment-backstage-disappearance-v1.jpg` | entertainment, idol, singer, backstage, disappearance, awards, livestream, fans |
| `generated_entertainment_backstage_disappearance_v2` | `/webtoons/covers/generated/cover-entertainment-backstage-disappearance-v2.jpg` | entertainment, backstage, disappearance, awards night, empty spotlight, anxious silhouettes |
| `generated_entertainment_press_hallway_v1` | `/webtoons/covers/generated/cover-entertainment-press-hallway-v1.jpg` | entertainment, press, hallway, camera flash, celebrity, scandal, red carpet, media |
| `generated_office_boardroom_betrayal` | `/webtoons/covers/generated/cover-office-boardroom-betrayal-v1.jpg` | office, company, boardroom, merger, investor, cofounder, contract, betrayal |
| `generated_office_boardroom_betrayal_v2` | `/webtoons/covers/generated/cover-office-boardroom-betrayal-v2.jpg` | office, company, boardroom, betrayal, executives, night city, sealed folder |
| `generated_office_contract_deadline_v1` | `/webtoons/covers/generated/cover-office-contract-deadline-v1.jpg` | office, contract, deadline, executives, rain window, negotiation, pressure |
| `generated_campus_rain_secret` | `/webtoons/covers/generated/cover-campus-rain-secret-v1.jpg` | campus, college, school, student, gate, rain, umbrella, secret meeting |
| `generated_campus_rain_secret_v2` | `/webtoons/covers/generated/cover-campus-rain-secret-v2.jpg` | campus, school, rain, umbrella, archive gate, secret, night |
| `generated_campus_auditorium_confession_v1` | `/webtoons/covers/generated/cover-campus-auditorium-confession-v1.jpg` | campus, school, auditorium, confession, stage, spotlight, student audience |
| `generated_sci_fi_mars_colony_stage` | `/webtoons/covers/generated/cover-sci-fi-mars-colony-stage-v1.jpg` | mars, colony, dome, oxygen, space, sci-fi, science fiction, talent show |
| `generated_fantasy_artifact_auction` | `/webtoons/covers/generated/cover-fantasy-artifact-auction-v1.jpg` | fantasy, artifact, relic, jade, auction, masked, faction, secret object |
| `generated_wedding_aisle_betrayal` | `/webtoons/covers/generated/cover-wedding-aisle-betrayal-v1.jpg` | wedding, bride, groom, aisle, chapel, betrayal, marriage |
| `generated_wedding_aisle_betrayal_v2` | `/webtoons/covers/generated/cover-wedding-aisle-betrayal-v2.jpg` | wedding, aisle, betrayal, dropped bouquet, chapel, candlelight |
| `generated_wedding_banquet_reveal_v1` | `/webtoons/covers/generated/cover-wedding-banquet-reveal-v1.jpg` | wedding, banquet, reveal, champagne, guests, luxury hall, shocked silhouettes |
| `generated_family_banquet_inheritance` | `/webtoons/covers/generated/cover-family-banquet-inheritance-v1.jpg` | family, banquet, inheritance, will, estate, heir, wealth |
| `generated_family_banquet_inheritance_v2` | `/webtoons/covers/generated/cover-family-banquet-inheritance-v2.jpg` | family, banquet, inheritance, long table, mansion, sealed will, wealthy family |
| `generated_family_will_reading_v1` | `/webtoons/covers/generated/cover-family-will-reading-v1.jpg` | family, will reading, lawyer, inheritance, storm window, estate, heirs |
| `generated_rooftop_gala_confrontation` | `/webtoons/covers/generated/cover-rooftop-gala-confrontation-v1.jpg` | gala, rooftop, champagne, confrontation, celebrity, wealthy, red carpet |
| `generated_hospital_secret_deadline` | `/webtoons/covers/generated/cover-hospital-secret-deadline-v1.jpg` | hospital, doctor, medical, emergency, deadline, secret, injury |
| `generated_urban_alley_witness` | `/webtoons/covers/generated/cover-urban-alley-witness-v1.jpg` | urban, alley, witness, envelope, pursuer, mystery, disappearance, rain |

## Rejected Candidate

- Source PNG: `/Users/lishehao/.codex/generated_images/019e8ae5-e892-7cb3-8bf8-7ae040729868/ig_09cfd0d3b82f3dac016a249c0f932c8199bca1ba751f8a19d2.png`
- Reason: visually strong CCTV/evidence room, but it includes monitor UI and evidence-board pseudo-text. Do not wire as default player-facing fallback.
- Source PNG: `/Users/lishehao/.codex/generated_images/019e8ae5-e892-7cb3-8bf8-7ae040729868/ig_02b76ae2e9e56342016a24ac4963d8819aa3179a30314890dc.png`
- Reason: visually strong office boardroom candidate, but the contract/table surface had document-layout pseudo-text risk. Replaced by `/webtoons/covers/generated/cover-office-boardroom-betrayal-v2.jpg`.

## Recommended Fallback Rule

1. If the backend/template exposes a generated cover URL, use it first.
2. If that URL is absent or fails to load, route by explicit `cover_theme` /
   `cover_key` when available.
3. If no explicit cover key exists, infer a generated cover key from template
   title, seed, Brief profile, cast roles, and world/setting keywords.
4. If no generated key matches, fall back to the existing shell resolver in
   `frontend2/src/shared/lib/webtoon-assets.ts`.
5. Never show a blank cover.

## Art Direction Notes

- Use covers as story/world surfaces only. Do not use them as UI chrome.
- Keep overlays in product UI dark charcoal with gold/red hard dividers.
- Avoid overfitting protagonist identity; covers should represent world,
  pressure, place, or first-scene promise.
- Reject future generated covers with readable text, logos, watermarks,
  fake app UI, subtitles, speech bubbles, or obvious IP-specific characters.
