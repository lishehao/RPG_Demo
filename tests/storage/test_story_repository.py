from sqlmodel import Session

from app.storage.engine import engine
from app.storage.repositories.stories import (
    create_story,
    get_latest_story_version,
    publish_story_version,
)


def test_publish_increments_version() -> None:
    with Session(engine) as db:
        story = create_story(db, title="Draft", pack_json={"foo": "bar"})
        story_id = story.id
        publish_story_version(db, story)
        publish_story_version(db, story)

    with Session(engine) as db:
        latest = get_latest_story_version(db, story_id)

    assert latest is not None
    assert latest.version == 2
