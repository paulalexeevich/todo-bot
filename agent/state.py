from typing import TypedDict

from db.models import DiscoveryResult, Source


class DiscoveryState(TypedDict):
    idea_text: str
    reddit_sources: list[Source]
    hn_sources: list[Source]
    ph_sources: list[Source]
    ih_sources: list[Source]
    discovery: DiscoveryResult | None
