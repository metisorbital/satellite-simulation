"""Minimal producer-neutral telemetry consumer with durable replay offsets.

This example deliberately imports no simulator package. In a real consumer,
the output transaction and acknowledged cursor belong in the same database.
"""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def accept_frame(frame: dict, seen: set[tuple]) -> bool:
    """Validate public identity/provenance and ignore an already processed frame.

    Parameters
    ----------
    frame : dict
        Synthetic or observed ``telemetry.v1`` envelope.
    seen : set of tuple
        Identities committed by this consumer's output transaction.

    Returns
    -------
    bool
        True only for a new measurement. No simulator run ID is required.
    """
    if frame.get("schema_version") != "telemetry.v1":
        raise ValueError("Unsupported telemetry envelope version")
    sequence = frame.get("sequence")
    if type(sequence) is not int or not 0 <= sequence <= 9_007_199_254_740_991:
        raise ValueError("Sequence is outside the interoperable integer range")
    if frame.get("source_kind") not in {"synthetic", "observed"}:
        raise ValueError("Unknown source provenance")
    identity = (frame["source_id"], frame["stream_id"], sequence)
    if identity in seen:
        return False
    seen.add(identity)
    return True


def main() -> None:
    """Read one durable page and atomically save example outputs and their cursor."""
    parser = argparse.ArgumentParser(description="Consume public Metis telemetry")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--stream", required=True)
    parser.add_argument("--state", type=Path, default=Path(".local/consumer.json"))
    args = parser.parse_args()
    token = os.environ["METIS_CONSUMER_TOKEN"]
    state = (
        json.loads(args.state.read_text())
        if args.state.exists()
        else {"stream_id": args.stream, "identities": [], "samples": []}
    )
    if state["stream_id"] != args.stream:
        raise ValueError("Choose a separate state file for each stream")
    query = {"stream_id": args.stream, "limit": 500}
    if state.get("cursor"):
        query["after"] = state["cursor"]
    request = Request(
        args.url + "/v1/telemetry?" + urlencode(query), headers={"Authorization": f"Bearer {token}"}
    )
    with urlopen(request, timeout=10) as response:
        page = json.load(response)
    seen = {tuple(identity) for identity in state["identities"]}
    for frame in page["items"]:
        if accept_frame(frame, seen):
            state["samples"].append(frame)
    state.update(cursor=page["next_cursor"], identities=sorted(seen))
    args.state.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.state.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, allow_nan=False))
    temporary.replace(args.state)
    print(
        f"Committed {len(page['items'])} deliveries; {len(seen)} unique measurements. More: {page['has_more']}"
    )


if __name__ == "__main__":
    main()
