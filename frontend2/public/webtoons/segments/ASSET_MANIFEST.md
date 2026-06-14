# Tiny Stories Korean Webtoon Segment Scenes

Generated during the 2026-06-06 Play segment scene expansion with built-in
Image Generation. These are internal in-story scene fallbacks for Play turn
segments, not story covers and not UI chrome.

Existing segment pool before this pass: 21 JPGs.
Accepted additions in this pass: 15 JPGs.
Accepted clearer backdrop additions in the clarity/parallax pass: 15 JPGs.
Current segment pool after this pass: 51 JPGs.

All accepted additions are 1672 x 941 JPGs, Korean webtoon / manhwa direction,
dark red-black-gold palette, cinematic 16:9 crop, no readable text, no logos,
no subtitles, no watermarks, no baked app UI.

## Accepted Assets

| Phase | Theme | File | Intended routing keywords |
| --- | --- | --- | --- |
| opening | backstage / entertainment | `/webtoons/segments/opening_backstage_control_room.jpg` | backstage, control room, awards, livestream, show opening, producer, spotlight |
| pressure | backstage / entertainment | `/webtoons/segments/pressure_backstage_press_crush.jpg` | backstage, press, camera flashes, celebrity, scandal, hallway, public pressure |
| reveal | backstage / entertainment | `/webtoons/segments/reveal_backstage_empty_spotlight.jpg` | empty spotlight, missing singer, backstage, stage, microphone, reveal |
| opening | office / boardroom | `/webtoons/segments/opening_office_night_merger.jpg` | office, boardroom, merger, night city, executives, conference room |
| pressure | office / boardroom | `/webtoons/segments/pressure_office_contract_table.jpg` | office, contract, blank folder, deadline, executives, rain window, negotiation |
| reversal | office / boardroom | `/webtoons/segments/reversal_office_elevator_secret.jpg` | office, elevator, secret, reversal, two silhouettes, tower, gold rim light |
| opening | campus | `/webtoons/segments/opening_campus_auditorium_night.jpg` | campus, auditorium, stage, night, confession, spotlight, students |
| pressure | campus | `/webtoons/segments/pressure_campus_archive_lock.jpg` | campus, archive, locked gate, rain, security light, students, secret |
| reveal | campus | `/webtoons/segments/reveal_campus_phone_reflection.jpg` | campus, phone reflection, rain, reveal, black glass, umbrella, witness |
| opening | wedding | `/webtoons/segments/opening_wedding_banquet_hall.jpg` | wedding, banquet hall, candles, luxury tables, aisle, opening tension |
| pressure | wedding | `/webtoons/segments/pressure_wedding_family_table.jpg` | wedding, family table, divided guests, banquet, pressure, dark luxury |
| reversal | wedding | `/webtoons/segments/reversal_wedding_dropped_note.jpg` | wedding, dropped note, aisle, bouquet shadow, reversal, candlelight |
| opening | family / inheritance | `/webtoons/segments/opening_family_will_reading.jpg` | family, will reading, mansion study, sealed will, inheritance, silhouettes |
| pressure | family / inheritance | `/webtoons/segments/pressure_family_banquet_standoff.jpg` | family, banquet, standoff, long table, inheritance, hostile silhouettes |
| terminal | family / inheritance | `/webtoons/segments/terminal_family_empty_mansion.jpg` | family, mansion, aftermath, empty banquet room, chandelier, terminal |

## Clearer Backdrop Variants

These `_clear_v2` assets are intended to be preferred when the Play stage needs
better first-beat readability. They keep dark Korean webtoon edges for UI
overlays, but use a brighter focal light and clearer scene architecture so the
player can read place, pressure, and phase at a glance.

| Phase | Theme | File | Intended routing keywords |
| --- | --- | --- | --- |
| opening | backstage / entertainment | `/webtoons/segments/opening_backstage_control_room_clear_v2.jpg` | backstage, control room, stage light, awards, livestream, opening, clear plate |
| pressure | backstage / entertainment | `/webtoons/segments/pressure_backstage_press_crush_clear_v2.jpg` | backstage, press crush, camera flash, crowded hallway, scandal pressure |
| reveal | backstage / entertainment | `/webtoons/segments/reveal_backstage_empty_spotlight_clear_v2.jpg` | empty spotlight, missing singer, stage, red curtain, reveal, clear plate |
| opening | office / boardroom | `/webtoons/segments/opening_office_night_merger_clear_v2.jpg` | office, boardroom, merger, night city, conference room, opening |
| pressure | office / boardroom | `/webtoons/segments/pressure_office_contract_table_clear_v2.jpg` | office, contract table, blank folders, executives, rain window, pressure |
| reversal | office / boardroom | `/webtoons/segments/reversal_office_elevator_secret_clear_v2.jpg` | office, elevator, secret, reversal, silhouettes, gold light |
| opening | campus | `/webtoons/segments/opening_campus_auditorium_night_clear_v2.jpg` | campus, auditorium, stage, night, gold spotlight, opening |
| pressure | campus | `/webtoons/segments/pressure_campus_archive_lock_clear_v2.jpg` | campus, archive, locked gate, rain, security light, pressure |
| reveal | campus | `/webtoons/segments/reveal_campus_phone_reflection_clear_v2.jpg` | campus, phone reflection, rain, black glass, reveal, no interface |
| opening | wedding | `/webtoons/segments/opening_wedding_banquet_hall_clear_v2.jpg` | wedding, banquet hall, candles, luxury tables, visible aisle, opening |
| pressure | wedding | `/webtoons/segments/pressure_wedding_family_table_clear_v2.jpg` | wedding, family table, divided guests, long table, pressure |
| reversal | wedding | `/webtoons/segments/reversal_wedding_dropped_note_clear_v2.jpg` | wedding, blank folded note, aisle, bouquet shadow, reversal |
| opening | family / inheritance | `/webtoons/segments/opening_family_will_reading_clear_v2.jpg` | family, will reading, mansion study, blank sealed folder, opening |
| pressure | family / inheritance | `/webtoons/segments/pressure_family_banquet_standoff_clear_v2.jpg` | family, banquet, standoff, inheritance, long table, pressure |
| terminal | family / inheritance | `/webtoons/segments/terminal_family_empty_mansion_clear_v2.jpg` | family, empty mansion, aftermath, chandelier, terminal |

## Rejected Candidates

- Source PNG: `/Users/lishehao/.codex/generated_images/019e8ae5-e892-7cb3-8bf8-7ae040729868/ig_02b76ae2e9e56342016a24ded1047c819a84443e2b98f08211.png`
- Reason: strong backstage control-room mood, but monitor/control surfaces created diegetic UI-screen risk. Replaced by `/webtoons/segments/opening_backstage_control_room.jpg`.

- Source PNG: `/Users/lishehao/.codex/generated_images/019e8ae5-e892-7cb3-8bf8-7ae040729868/ig_02b76ae2e9e56342016a24e068ec28819aa9c9f08d4d17f584.png`
- Reason: elevator reversal candidate included small wall signage / pseudo-text risk. Replaced by `/webtoons/segments/reversal_office_elevator_secret.jpg`.

- Source PNG: `/Users/lishehao/.codex/generated_images/019e8ae5-e892-7cb3-8bf8-7ae040729868/ig_02b76ae2e9e56342016a24e1436b20819a9f36331b92d8d8ff.png`
- Reason: campus archive candidate included notice-board / signage pseudo-text risk. Replaced by `/webtoons/segments/pressure_campus_archive_lock.jpg`.

## Handoff Notes

- R&D owns adding these slugs to segment phase/category matching. Do not infer
  resolver behavior from file presence alone.
- Prefer phase first, theme second: e.g. `pressure + wedding` should prefer
  `pressure_wedding_family_table`, while `reveal + campus` should prefer
  `reveal_campus_phone_reflection`.
- Covers should still represent story/world identity. Segment scenes should
  represent the current beat, pressure, object, or location during play.
- Avoid using these scene assets as UI backgrounds outside Play unless the route
  is intentionally showing an in-story process beat.
- Reject future segment images with readable text, logos, watermarks, subtitles,
  speech bubbles, fake app UI, or obvious IP-specific characters.

## Clear Backdrop QA Notes

- The clear variants passed visual inspection for readable text, logos, fake UI,
  subtitles, speech bubbles, and watermarks.
- Use clear variants first for opening/first-beat backgrounds where UI overlays
  could otherwise make the scene read as black fog.
- Keep product overlays dark but not opaque enough to erase the focal light.
  Suggested art target: center/right focal plate remains readable at normal play
  opacity, with safe dark edges for title/turn/context UI.
- Contact sheet for the clear variants:
  `/tmp/tiny-stories-clear-play-backdrops-contact-sheet.jpg`.
