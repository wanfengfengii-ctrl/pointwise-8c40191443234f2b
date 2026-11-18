from catalog.transactions import Archive
from delivery.format import encode_handoff
from delivery.manifest import build_manifest
from review.claims import claim


def export(archive: Archive, ticket_id: int, target_revision: int) -> bytes:
    result = claim(archive, ticket_id, target_revision)
    return encode_handoff(build_manifest(result))
