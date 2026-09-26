"""Export a fixed committed run for ML using only the public consumer API.

The destination is created only after every stream is verified complete.
No evaluator truth, credentials, or source configuration are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def get_json(base_url: str, path: str, token: str) -> dict[str, Any]:
    """Read one authenticated public API response.

    Parameters
    ----------
    base_url, path : str
        Service URL and relative public endpoint.
    token : str
        Consumer token held in memory only.

    Returns
    -------
    dict
        Decoded response, or an exception for failed HTTP requests.
    """
    request = Request(base_url.rstrip("/") + path, headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def export_run(base_url: str, run_id: str, output: Path, token: str) -> dict[str, Any]:
    """Write a complete public dataset at one captured committed watermark.

    Parameters
    ----------
    base_url, run_id : str
        Service URL and execution identity.
    output : Path
        New output directory; existing destinations are never overwritten.
    token : str
        Consumer credential; never persisted or printed.

    Returns
    -------
    dict
        Dataset manifest including stream bounds and a telemetry SHA-256.

    Raises
    ------
    ValueError
        A stream has gaps, expired history, inconsistent identity or catalog.
    FileExistsError
        The output path is already present.

    Notes
    -----
    Later commits cannot extend this export. Frames retain their original
    identity, timestamps, quality and values, ordered by satellite and sequence.
    Failure leaves no partial dataset under the requested destination name.
    """
    if output.exists():
        raise FileExistsError(output)
    report = get_json(base_url, f"/v1/runs/{quote(run_id, safe='')}/telemetry-report", token)
    if report["run_id"] != run_id or report["from_sequence"] != 0:
        raise ValueError("Unexpected run or sequence boundary in report")
    if any(not stream["complete_window"] for stream in report["streams"]):
        raise ValueError("Cannot export an incomplete retained stream")
    watermark = report["through_sequence"]
    versions = sorted({stream["catalog_version"] for stream in report["streams"]})
    catalogs = {
        version: get_json(base_url, "/v1/catalog?" + urlencode({"version": version}), token)
        for version in versions
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix=".metis-export-", dir=output.parent) as directory:
        staging = Path(directory) / "dataset"
        staging.mkdir()
        with (staging / "telemetry.jsonl").open("wb") as destination:
            for stream in report["streams"]:
                expected = 0
                cursor = None
                while expected <= watermark:
                    query: dict[str, str | int] = {"stream_id": stream["stream_id"], "limit": 500}
                    if cursor is not None:
                        query["after"] = cursor
                    page = get_json(base_url, "/v1/telemetry?" + urlencode(query), token)
                    if not page["items"]:
                        raise ValueError("Stream ended before the captured watermark")
                    for frame in page["items"]:
                        if frame["sequence"] > watermark:
                            break
                        if frame["sequence"] != expected or any(
                            frame[key] != stream[key]
                            for key in ("source_id", "stream_id", "satellite_id", "catalog_version")
                        ):
                            raise ValueError(
                                "Stream identity, catalog or sequence changed during export"
                            )
                        if (
                            frame["source_kind"] != "synthetic"
                            or frame["time_domain"] != "simulation_utc"
                        ):
                            raise ValueError("Unexpected source provenance")
                        encoded = (
                            json.dumps(frame, separators=(",", ":"), allow_nan=False) + "\n"
                        ).encode()
                        destination.write(encoded)
                        digest.update(encoded)
                        expected += 1
                        count += 1
                    new_cursor = page["next_cursor"]
                    if expected <= watermark and new_cursor == cursor:
                        raise ValueError("Telemetry cursor did not advance")
                    cursor = new_cursor
                if expected != stream["frame_count"]:
                    raise ValueError("Report coverage changed during export")
        manifest = {
            "schema_version": "dataset.v1",
            "run_id": run_id,
            "source_kind": "synthetic",
            "time_domain": "simulation_utc",
            "through_sequence": watermark,
            "frame_count": count,
            "telemetry_sha256": digest.hexdigest(),
            "telemetry_file": "telemetry.jsonl",
            "report_file": "report.json",
            "catalogs_file": "catalogs.json",
            "contains_evaluator_truth": False,
            "grouping": "Keep entire related executions together for ML splits; use separately authorized evaluator manifests to identify matched configurations.",
        }
        for filename, value in (
            ("report.json", report),
            ("catalogs.json", catalogs),
            ("dataset.json", manifest),
        ):
            (staging / filename).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if output.exists():
            raise FileExistsError(output)
        staging.rename(output)
    return manifest


def main() -> None:
    """Export one run using the consumer token supplied through the environment.

    Notes
    -----
    ``METIS_CONSUMER_TOKEN`` is required; credentials are not command arguments.
    """
    parser = argparse.ArgumentParser(description="Export committed Metis telemetry for ML")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_run(args.url, args.run, args.output, os.environ["METIS_CONSUMER_TOKEN"])
    print(
        f"Exported {manifest['frame_count']} frames through tick {manifest['through_sequence']} to {args.output}"
    )


if __name__ == "__main__":
    main()
