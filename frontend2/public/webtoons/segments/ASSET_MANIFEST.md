# Tiny Stories Korean Webtoon Segment Scenes

Generated during the 2026-06-06 Play segment scene expansion with built-in
Image Generation. These are internal in-story scene fallbacks for Play turn
segments, not story covers and not UI chrome.

Existing segment pool before this pass: 21 JPGs.
Accepted additions in this pass: 15 JPGs.
Current segment pool after this pass: 36 JPGs.

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
