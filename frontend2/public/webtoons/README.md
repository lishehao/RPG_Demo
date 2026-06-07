# Webtoon Asset Library

This directory holds the active Korean webtoon visual assets.

## Ownership

- Art owns image generation, visual QA, asset manifests, and asset expansion.
- R&D owns resolver logic and wiring accepted asset paths into the product.
- Design owns where assets appear and how card/cover matching reads to users.

R&D should not generate new image assets in this folder during logic work.

## Directory Map

- `ui/`
  - Page backgrounds, logo, default avatars, auth/loading/create images.
  - `ui/generated/create-agent-room-bg-v1.png` and `ui/generated/story-butler-avatar-v1.png` are the current Create Agent Chat assets.
- `covers/generated/`
  - Art-provided fallback cover pool for generated stories.
  - `ASSET_MANIFEST.md` records accepted keys and paths.
- `shells/`
  - Broader internal cover fallback shells and variants.
- `segments/`
  - Play-scene background images by story phase.
- `avatars/`
  - Cast portrait pool.
- `advisors/`
  - Advisor portraits; separate from cast to avoid identity collision.
- `oracle/`
  - Oracle/advisor vignette asset.
- `endings/`
  - Ending/coda artwork.
- `splashes/`
  - Victory/compromised/game-over splash assets.
- `peaks/`
  - Close-up images used for peak narration moments.
- `empty/`
  - Empty-state artwork.

## Cover Resolver Rules

Implemented in `frontend2/src/shared/lib/webtoon-assets.ts`.

1. Trust and use backend/provider `cover_image_url` when present.
2. Otherwise infer an internal generated cover theme from title, summary, seed, cast, and story metadata.
3. Use generated cover pools for high-frequency themes before shell variants.
4. Use shell/hash fallback when no generated theme matches.
5. For list surfaces, use same-screen assignment to avoid duplicate fallback URLs in the first visible cards whenever enough candidates exist.

This is a display-level no-overlap guarantee for fallback/internal covers. It is not a claim that every database story has a globally unique cover forever.

## Adding Assets

When Art adds images:

1. Put files under the appropriate subfolder.
2. Update or add an asset manifest when the folder has one.
3. R&D wires paths into `webtoon-assets.ts`.
4. Update `tests/test_generated_cover_contract.py` for new keys/pools/order.
5. Run `npm --prefix frontend2 run check`, `npm --prefix frontend2 run build`, and relevant cover tests.
