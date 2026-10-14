#!/usr/bin/env python3
"""Derive the web copies of the user-provided GPT image batch (v2-batch-01).

    python3 -I scripts/derive-generated.py --from "<Dropbox>/Everwith_Claude_Frontend_Rebuild_2026-10-13/generated-assets/batch-01"

Optional maintenance step (needs Pillow with WebP). The derived files in
public/generated/batch-01/ are committed, so a normal install never runs this.
What it does, and nothing else:
  1. checks every chosen original against the batch's own SHA256SUMS.json and manifest.json;
  2. writes resized copies (WebP / PNG) to public/generated/batch-01/ — no retouching,
     no colour changes; the only edits are resizing and, for the favicon, making the
     black corners outside the icon's rounded square transparent;
  3. records original + derivative hashes and the generation prompts in
     docs/GENERATED_ASSETS.json (checked by `npm run assets:generated`).
Re-running with a different Pillow/libwebp may produce different bytes; the JSON
then simply records the new hashes.
Rights: user-provided GPT output; commercial use and redistribution are unverified.
"""
import argparse
import hashlib
import json
import os
import sys
from PIL import Image, ImageChops

RIGHTS = '用户经 GPT 生成并提供；商用/再分发权未核实'
BATCH = 'v2-batch-01'
DROPBOX_FOLDER = '/Everwith_Claude_Frontend_Rebuild_2026-10-13/generated-assets/batch-01/'

STAGE = 'LiveStage backdrop behind the Live2D canvas and the static portrait (character page, private chat, table rail, story rail, discover card)'
# slot, chosen variant (None = single image), derivative name, (w, h), format, quality, used in
SPEC = [
    ('story-last-train-cover-tall', 'a', 'story-last-train-cover-tall.webp', (768, 1152), 'webp', 82, 'Discover story card (4:5), story preparation poster (3:4), Recent / continue / play-together thumbnails'),
    ('story-last-train-cover-wide', 'a', 'story-last-train-cover-wide.webp', (1280, 853), 'webp', 82, 'Story detail hero (4:3)'),
    ('story-last-train-scene-waiting-room', None, 'story-last-train-scene-waiting-room.webp', (1280, 853), 'webp', 80, 'Story play scene banner: opening and beat 1'),
    ('story-last-train-scene-corner', None, 'story-last-train-scene-corner.webp', (1280, 853), 'webp', 80, 'Story play scene banner: beat 2'),
    ('story-last-train-scene-duty-room', None, 'story-last-train-scene-duty-room.webp', (1280, 853), 'webp', 80, 'Story play scene banner: beat 3'),
    ('story-last-train-scene-platform-dawn', None, 'story-last-train-scene-platform-dawn.webp', (1280, 853), 'webp', 80, 'Story play scene banner: open mode after the last beat'),
    ('story-promise-rain-cover-tall', 'a', 'story-promise-rain-cover-tall.webp', (768, 1152), 'webp', 82, 'Discover story card (4:5), story preparation poster (3:4), Recent / continue / play-together thumbnails'),
    ('story-promise-rain-cover-wide', 'a', 'story-promise-rain-cover-wide.webp', (1280, 853), 'webp', 82, 'Story detail hero (4:3)'),
    ('story-promise-rain-scene-entrance-rain', None, 'story-promise-rain-scene-entrance-rain.webp', (1280, 853), 'webp', 80, 'Story play scene banner: opening and beat 1'),
    ('story-promise-rain-scene-backstage', None, 'story-promise-rain-scene-backstage.webp', (1280, 853), 'webp', 80, 'Story play scene banner: beat 2'),
    ('story-promise-rain-scene-office', None, 'story-promise-rain-scene-office.webp', (1280, 853), 'webp', 80, 'Story play scene banner: beat 3'),
    ('story-promise-rain-scene-entrance-after-rain', None, 'story-promise-rain-scene-entrance-after-rain.webp', (1280, 853), 'webp', 80, 'Story play scene banner: beat 4'),
    ('backdrop-lena', 'a', 'backdrop-lena.webp', (768, 1152), 'webp', 78, STAGE),
    ('backdrop-arthur', 'a', 'backdrop-arthur.webp', (768, 1152), 'webp', 78, STAGE),
    ('backdrop-marcus', 'a', 'backdrop-marcus.webp', (768, 1152), 'webp', 78, STAGE),
    ('backdrop-nora', 'a', 'backdrop-nora.webp', (768, 1152), 'webp', 78, STAGE),
    ('backdrop-iris', 'a', 'backdrop-iris.webp', (768, 1152), 'webp', 78, STAGE),
    ('backdrop-generic', None, 'backdrop-generic.webp', (768, 1152), 'webp', 78, 'Stage backdrop for characters without their own (user-created work characters)'),
    ('game-royale-cover', 'a', 'game-royale-cover.webp', (768, 1152), 'webp', 82, 'Game poster: Discover game card (1:1), game preparation (3:4), play-together and Recent thumbnails'),
    ('game-splendor-cover', 'a', 'game-splendor-cover.webp', (768, 1152), 'webp', 82, 'Game poster: Discover game card (1:1), game preparation (3:4), play-together and Recent thumbnails'),
    ('game-cabo-cover', 'a', 'game-cabo-cover.webp', (768, 1152), 'webp', 82, 'Game poster: Discover game card (1:1), game preparation (3:4), play-together and Recent thumbnails'),
    ('empty-friends', None, 'empty-friends.webp', (480, 480), 'webp', 86, 'Friends: no friends yet'),
    ('empty-recent', None, 'empty-recent.webp', (480, 480), 'webp', 86, 'Recent: nothing yet / nothing archived'),
    ('empty-create', None, 'empty-create.webp', (480, 480), 'webp', 86, 'Create: no works yet'),
    ('state-not-found', None, 'state-not-found.webp', (480, 480), 'webp', 86, 'Not found (route, character, story, run, game, friend, work)'),
    ('state-load-error', None, 'state-load-error.webp', (480, 480), 'webp', 86, 'Load failure (distinct from “nothing here”)'),
    ('state-signin', None, 'state-signin.webp', (480, 480), 'webp', 86, 'Sign-in needed (friends, chat) and the sign-in dialog'),
    ('create-type-story', None, 'create-type-story.webp', (320, 320), 'webp', 86, 'New work dialog: story type'),
    ('create-type-character', None, 'create-type-character.webp', (320, 320), 'webp', 86, 'New work dialog: character type'),
    *[(f'work-cover-0{i}', None, f'work-cover-0{i}.webp', (600, 900), 'webp', 80, 'Work cover choice: work cards, editor, preview panel') for i in range(1, 7)],
    *[(f'persona-avatar-0{i}', None, f'persona-avatar-0{i}.webp', (256, 256), 'webp', 85, 'Persona avatar choice: account page, navigation, own seat at tables') for i in range(1, 9)],
    ('brand-emblem', 'a', 'brand-emblem.png', (128, 128), 'png', None, 'Navigation brand mark and the first-load screen'),
    ('app-icon', 'a', 'favicon-64.png', (64, 64), 'favicon', None, 'Browser tab icon (corners outside the rounded square made transparent)'),
    ('app-icon', 'a', 'apple-touch-icon.png', (180, 180), 'touch', None, 'Home-screen icon (corners filled with the tile colour)'),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def resize(im, size):
    if im.mode == 'RGBA':  # resample with premultiplied alpha so edges keep their colour
        return im.convert('RGBa').resize(size, Image.Resampling.LANCZOS).convert('RGBA')
    return im.convert('RGB').resize(size, Image.Resampling.LANCZOS)


def corner_alpha(im):
    """Icon tile spans the full canvas; only the four corners outside its rounded square
    are pure black. Alpha there follows brightness; elsewhere stays opaque."""
    rgb = im.convert('RGB')
    w, h = rgb.size
    zone = max(8, round(w * 0.14))
    r, g, b = rgb.split()
    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)  # tile edge is dark brown (max channel ≈ 34), corners are 0
    lum = brightest.point(lambda v: 255 if v >= 28 else round(v * 255 / 28))
    alpha = Image.new('L', (w, h), 255)
    for box in [(0, 0, zone, zone), (w - zone, 0, w, zone), (0, h - zone, zone, h), (w - zone, h - zone, w, h)]:
        alpha.paste(lum.crop(box), box)
    out = rgb.copy()
    out.putalpha(alpha)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='src', required=True, help='folder with the batch PNGs, manifest.json and SHA256SUMS.json')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--out', default=os.path.join(root, 'public', 'generated', 'batch-01'))
    ap.add_argument('--doc', default=os.path.join(root, 'docs', 'GENERATED_ASSETS.json'))
    args = ap.parse_args()

    sums = json.load(open(os.path.join(args.src, 'SHA256SUMS.json'), encoding='utf-8'))
    manifest = json.load(open(os.path.join(args.src, 'manifest.json'), encoding='utf-8'))
    records = {r['filename']: r for r in manifest['records']}
    os.makedirs(args.out, exist_ok=True)

    assets, problems = [], []
    for slot, variant, name, size, fmt, quality, used in SPEC:
        original = f'{slot}__{variant}.png' if variant else f'{slot}.png'
        path = os.path.join(args.src, original)
        rec = records.get(original)
        if not os.path.exists(path) or rec is None:
            problems.append(f'missing original {original}')
            continue
        digest = sha256(path)
        if digest != sums.get(original) or digest != rec.get('sha256'):
            problems.append(f'hash mismatch {original}')
            continue
        im = Image.open(path)
        im.load()
        dest = os.path.join(args.out, name)
        if fmt == 'webp':
            out = resize(im, size)
            out.save(dest, 'WEBP', quality=quality, method=6, **({'exact': False} if out.mode == 'RGBA' else {}))
            transform = f'Lanczos resize {im.size[0]}x{im.size[1]} -> {size[0]}x{size[1]}{" (premultiplied alpha)" if out.mode == "RGBA" else ""}; WebP q{quality} method 6'
        elif fmt == 'png':
            out = resize(im, size)
            out.save(dest, 'PNG', optimize=True)
            transform = f'Lanczos resize {im.size[0]}x{im.size[1]} -> {size[0]}x{size[1]} (premultiplied alpha); PNG'
        elif fmt == 'favicon':
            out = resize(corner_alpha(im), size)
            out.save(dest, 'PNG', optimize=True)
            transform = f'black corners outside the rounded square -> transparent; Lanczos resize -> {size[0]}x{size[1]} (premultiplied alpha); PNG'
        else:  # touch icon: opaque square, corners filled with the tile's own edge colour
            tile = Image.new('RGB', im.size, im.convert('RGB').getpixel((2, im.size[1] // 2)))
            tile.paste(corner_alpha(im), (0, 0), corner_alpha(im))
            out = tile.resize(size, Image.Resampling.LANCZOS)
            out.save(dest, 'PNG', optimize=True)
            transform = f'corners outside the rounded square filled with the tile edge colour; Lanczos resize -> {size[0]}x{size[1]}; PNG'
        others = sorted(f for f in records if f.startswith(f'{slot}__') and f != original)
        assets.append({
            'slot': slot, 'chosen_variant': variant, 'used_in': used,
            'original': {'file': original, 'dropbox_path': DROPBOX_FOLDER + original, 'sha256': digest, 'bytes': os.path.getsize(path),
                         'dims': list(im.size), 'mode': im.mode, 'generated_at_utc': rec.get('generated_at_utc'), 'tool': rec.get('tool'),
                         'model': rec.get('model'), 'source': rec.get('source'), 'qa_status': rec.get('qa_status'),
                         'reference_images': rec.get('reference_images') or [], 'prompt': rec.get('prompt'), 'actual_prompt': rec.get('actual_prompt')},
            'derivative': {'path': f'public/generated/batch-01/{name}', 'url': f'/generated/batch-01/{name}', 'sha256': sha256(dest),
                           'bytes': os.path.getsize(dest), 'dims': list(out.size), 'mode': out.mode, 'transform': transform},
            'unused_candidates': others,
        })
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        sys.exit(1)
    doc = {
        'schema': 'everwith-generated-assets-v1', 'batch': BATCH, 'rights': RIGHTS,
        'note': 'User-provided GPT output. Not part of the original handoff package; commercial use and redistribution are unverified. Only resized here (see transform).',
        'source': {'dropbox_folder': DROPBOX_FOLDER, 'manifest_sha256': sha256(os.path.join(args.src, 'manifest.json')),
                   'sha256sums_sha256': sha256(os.path.join(args.src, 'SHA256SUMS.json')), 'slots': manifest.get('requested_slots'), 'images': manifest.get('requested_images')},
        'derived_with': {'pillow': Image.__version__},
        'assets': assets,
    }
    with open(args.doc, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    total = sum(a['derivative']['bytes'] for a in assets)
    print(json.dumps({'derivatives': len(assets), 'bytes': total, 'out': os.path.relpath(args.out, root)}))


if __name__ == '__main__':
    main()
