from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _resolve_avatar_samples() -> dict[str, str]:
    script = r"""
import fs from 'node:fs'
import ts from './frontend2/node_modules/typescript/lib/typescript.js'

const source = fs.readFileSync('frontend2/src/shared/lib/webtoon-assets.ts', 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText
const mod = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

const awards = {
  template_id: 'tmpl_awards_livestream_avatar_semantic',
  seed: 'Ten minutes before an awards livestream, an anxious publicist, a producer, a backup dancer, and a sponsor representative discover the singer disappeared backstage.',
  title: 'Awards Livestream Disappearance',
  cast: [
    { character_id: 'publicist', display_name: 'Anxious publicist', role: 'publicist holding the room together', relation_to_protagonist: 'player lens' },
    { character_id: 'producer', display_name: 'Producer', role: 'producer pressing to keep the show live', relation_to_protagonist: 'pressure holder' },
    { character_id: 'backup_dancer', display_name: 'Backup dancer', role: 'backup dancer who saw the singer leave', relation_to_protagonist: 'witness' },
    { character_id: 'sponsor', display_name: 'Sponsor representative', role: 'sponsor representative watching the contract', relation_to_protagonist: 'public fallout pressure' },
  ],
}
const lowSignal = {
  character_id: 'unclear',
  display_name: 'Morgan',
  role: 'someone in the room',
  relation_to_protagonist: 'unclear',
}

const result = Object.fromEntries(awards.cast.map((member) => [
  member.character_id,
  mod.getAvatarForCastMember(awards.template_id, member, awards),
]))
result.low_signal = mod.getAvatarForCastMember(awards.template_id, lowSignal, awards)
const office = {
  template_id: 'tmpl_office_avatar_semantic',
  seed: 'A boardroom contract deadline turns a merger meeting into a power struggle between a lawyer, investor, executive assistant, and founder.',
  title: 'Boardroom Contract Deadline',
  cast: [],
}
result.office_lawyer = mod.getAvatarForCastMember(office.template_id, {
  character_id: 'lawyer',
  display_name: 'Contract lawyer',
  role: 'lawyer reviewing the contract clause',
  relation_to_protagonist: 'legal pressure holder',
}, office)
result.office_investor = mod.getAvatarForCastMember(office.template_id, {
  character_id: 'investor',
  display_name: 'Investor',
  role: 'investor and board member',
  relation_to_protagonist: 'money pressure',
}, office)
const campus = {
  template_id: 'tmpl_campus_avatar_semantic',
  seed: 'A rainy campus auditorium confession pulls a student, classmate, mentor, and archive witness into a secret.',
  title: 'Campus Rain Secret',
  cast: [],
}
result.campus_student = mod.getAvatarForCastMember(campus.template_id, {
  character_id: 'student',
  display_name: 'Archive student',
  role: 'student who found the hidden note',
  relation_to_protagonist: 'campus witness',
}, campus)
const wedding = {
  template_id: 'tmpl_wedding_avatar_semantic',
  seed: 'A wedding banquet reveal forces a bride, groom, and family elder to choose who is protected.',
  title: 'Wedding Banquet Reveal',
  cast: [],
}
result.wedding_bride = mod.getAvatarForCastMember(wedding.template_id, {
  character_id: 'bride',
  display_name: 'Bride',
  role: 'bride at the aisle',
  relation_to_protagonist: 'center of the reveal',
}, wedding)
const family = {
  template_id: 'tmpl_family_avatar_semantic',
  seed: 'A family inheritance will reading turns the mansion against its elder patriarch and heirs.',
  title: 'Family Will Reading',
  cast: [],
}
result.family_elder = mod.getAvatarForCastMember(family.template_id, {
  character_id: 'elder',
  display_name: 'Grandfather',
  role: 'elder patriarch holding the will',
  relation_to_protagonist: 'inheritance pressure',
}, family)
console.log(JSON.stringify(result))
"""
    completed = subprocess.run(
        ["node", "--input-type=module"],
        input=script,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_awards_backstage_roles_use_semantic_avatar_buckets() -> None:
    result = _resolve_avatar_samples()

    assert result["publicist"] in {
        "/webtoons/avatars/female-07.jpg",
        "/webtoons/avatars/female-09.jpg",
    }
    assert result["producer"] == "/webtoons/avatars/male-04.jpg"
    assert result["backup_dancer"] in {
        "/webtoons/avatars/female-08.jpg",
        "/webtoons/avatars/female-10.jpg",
        "/webtoons/avatars/idol-01.jpg",
    }
    assert result["sponsor"] in {
        "/webtoons/avatars/female-01.jpg",
        "/webtoons/avatars/elder-02.jpg",
        "/webtoons/avatars/male-07.jpg",
        "/webtoons/avatars/male-10.jpg",
    }

    # Low-confidence roles should land on a neutral/professional face, not on
    # a period/bridal/student/object image just because a broad hash picked it.
    assert result["low_signal"] in {
        "/webtoons/avatars/female-07.jpg",
        "/webtoons/avatars/female-03.jpg",
        "/webtoons/avatars/female-01.jpg",
        "/webtoons/avatars/male-03.jpg",
        "/webtoons/avatars/lawyer-01.jpg",
        "/webtoons/avatars/male-10.jpg",
    }
    assert result["office_lawyer"] in {
        "/webtoons/avatars/lawyer-01.jpg",
        "/webtoons/avatars/male-03.jpg",
        "/webtoons/avatars/female-03.jpg",
    }
    assert result["office_investor"] in {
        "/webtoons/avatars/female-01.jpg",
        "/webtoons/avatars/male-01.jpg",
        "/webtoons/avatars/male-03.jpg",
        "/webtoons/avatars/male-10.jpg",
    }
    assert result["campus_student"] in {
        "/webtoons/avatars/female-04.jpg",
        "/webtoons/avatars/female-06.jpg",
        "/webtoons/avatars/male-06.jpg",
        "/webtoons/avatars/student-01.jpg",
        "/webtoons/avatars/student-02.jpg",
    }
    assert result["wedding_bride"] == "/webtoons/avatars/bride-01.jpg"
    assert result["family_elder"] in {
        "/webtoons/avatars/elder-01.jpg",
        "/webtoons/avatars/elder-02.jpg",
        "/webtoons/avatars/male-07.jpg",
        "/webtoons/avatars/male-10.jpg",
    }


def test_avatar_annotations_cover_every_avatar_and_fallback_file() -> None:
    script = r"""
import fs from 'node:fs'
import ts from './frontend2/node_modules/typescript/lib/typescript.js'

const source = fs.readFileSync('frontend2/src/shared/lib/webtoon-assets.ts', 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText
const mod = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
console.log(JSON.stringify({
  annotations: mod.AVATAR_ANNOTATIONS,
  fallbacks: mod.AVATAR_FALLBACK_ANNOTATIONS,
}))
"""
    completed = subprocess.run(
        ["node", "--input-type=module"],
        input=script,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(completed.stdout)
    annotations = data["annotations"]
    fallbacks = data["fallbacks"]

    avatar_paths = sorted(
        f"/webtoons/avatars/{path.name}"
        for path in (ROOT / "frontend2/public/webtoons/avatars").glob("*.jpg")
    )
    fallback_paths = sorted(
        f"/webtoons/ui/{path.name}"
        for path in (ROOT / "frontend2/public/webtoons/ui").glob("default-avatar-*.jpg")
    )
    annotated_paths = sorted(item["path"] for item in annotations)
    annotated_fallback_paths = sorted(item["path"] for item in fallbacks)

    assert annotated_paths == avatar_paths
    assert annotated_fallback_paths == fallback_paths
    assert len({item["slug"] for item in annotations}) == len(annotations)
    assert len(annotations) == 29
    assert len(fallbacks) == 2

    for item in [*annotations, *fallbacks]:
        assert item["path"].startswith(("/webtoons/avatars/", "/webtoons/ui/"))
        assert item["genderPresentation"] in {"female", "male", "neutral"}
        assert item["roleTags"]
        assert item["domainTags"]
        assert item["toneTags"]
        assert item["formalityTags"]
        assert isinstance(item["avoidTags"], list)
        assert item["notes"]

    male_08 = next(item for item in annotations if item["slug"] == "male-08")
    assert male_08["genderPresentation"] == "neutral"
    assert {"character", "portrait", "cast-face"}.issubset(set(male_08["avoidTags"]))


def test_avatar_resolver_has_retrieval_style_manifest_and_scoring_seam() -> None:
    source = (ROOT / "frontend2/src/shared/lib/webtoon-assets.ts").read_text()
    play_primitives = (ROOT / "frontend2/src/pages/play/components/play-editorial-primitives.tsx").read_text()
    world_detail = (ROOT / "frontend2/src/pages/world/world-detail-page.tsx").read_text()

    assert "export const AVATAR_ANNOTATIONS" in source
    assert "export const AVATAR_FALLBACK_ANNOTATIONS" in source
    assert "const AVATAR_METADATA" in source
    assert "AvatarQuery" in source
    assert "AVATAR_ROLE_RULES" in source
    assert "AVATAR_CONTEXT_RULES" in source
    assert "rankAvatarCandidates" in source
    assert "avatarSemanticScore" in source
    assert "SEMANTIC_AVATAR_MIN_SCORE" in source
    assert "NEUTRAL_PROFESSIONAL_AVATARS" in source
    assert "role->file hardcoding" in source
    assert "embeddings" in source
    assert "stableAvatarTieValue" in source
    assert "male-08" in source and 'avoidTags: ["character", "portrait", "cast-face"]' in source
    assert "broad male/female" not in source[source.index("export function getAvatarForCastMember"):]
    assert "getAvatarForCastMember(story.template.template_id, member, story.template)" in play_primitives
    assert "getAvatarForCastMember(template.template_id, c, template)" in world_detail
