from __future__ import annotations

from sqlmodel import Session, desc, func, select

from app.storage.models import Story, StoryVersion


def create_story(db: Session, *, title: str, pack_json: dict) -> Story:
    story = Story(title=title, draft_pack_json=pack_json)
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def get_story(db: Session, story_id: str) -> Story | None:
    return db.get(Story, story_id)


def get_story_version(db: Session, story_id: str, version: int) -> StoryVersion | None:
    stmt = select(StoryVersion).where(StoryVersion.story_id == story_id, StoryVersion.version == version)
    return db.exec(stmt).first()


def get_latest_story_version(db: Session, story_id: str) -> StoryVersion | None:
    stmt = (
        select(StoryVersion)
        .where(StoryVersion.story_id == story_id)
        .order_by(desc(StoryVersion.version))
        .limit(1)
    )
    return db.exec(stmt).first()


def publish_story_version(db: Session, story: Story) -> StoryVersion:
    next_version_stmt = select(func.coalesce(func.max(StoryVersion.version), 0)).where(StoryVersion.story_id == story.id)
    max_version = db.exec(next_version_stmt).one()
    next_version = int(max_version) + 1

    version = StoryVersion(story_id=story.id, version=next_version, status="published", pack_json=story.draft_pack_json)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
