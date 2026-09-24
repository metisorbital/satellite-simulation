"""Bounded presentation stream, separate from durable consumer replay."""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from metis_sim.application.errors import ServiceError
from metis_sim.domain.public import VisualMessage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/v1/runs/{run_id}/visual")
async def visual_socket(websocket: WebSocket, run_id: str) -> None:
    """Stream committed public samples with bounded backpressure and session expiry."""
    context = websocket.app.state
    try:
        principal = context.auth.principal(websocket)
        principal.require({"viewer_control", "operator"}, run_id)
        context.auth.origin(websocket, required=principal.role == "viewer_control")
        await run_in_threadpool(context.repository.status, run_id)
        principal.require({"viewer_control", "operator"}, run_id)
    except ServiceError:
        await websocket.close(code=1008)
        return
    except Exception as error:
        logger.error("visual_failed", extra={"run_id": run_id, "error_type": type(error).__name__})
        await websocket.close(code=1011, reason="Visual stream is unavailable")
        return
    public_slot = principal.public_demo
    if public_slot and not context.public_viewer_slots.acquire(blocking=False):
        await websocket.close(code=1013, reason="Public demo is at capacity")
        return
    last_tick, last_state, last_speed = -1, None, None
    resync_count = 0
    first = True
    lifetime = None if principal.expires_at is None else max(0, principal.expires_at - time.time())
    try:
        await websocket.accept()
        # Expiry must also interrupt slow reads and sends, not only idle loops.
        async with asyncio.timeout(lifetime):
            while True:
                principal.require({"viewer_control", "operator"}, run_id)
                current = await run_in_threadpool(context.reader.snapshot, run_id, None, 41)
                status = current["status"]
                changed_speed = last_speed is not None and last_speed != status["requested_speed"]
                history_count = 2 * status["requested_speed"] + 1
                earliest = status["committed_tick"] - history_count + 1
                history = [frame for frame in current["frames"] if frame["sequence"] >= earliest]
                gap = last_tick >= 0 and status["committed_tick"] - last_tick > history_count
                if not first and (gap or changed_speed):
                    resync_count += 1
                    logger.info(
                        "visual_resync",
                        extra={
                            "run_id": run_id,
                            "tick": status["committed_tick"],
                            "status": status["status"],
                            "resync_count": resync_count,
                        },
                    )
                kind = (
                    "snapshot"
                    if first
                    else "resync_required"
                    if gap or changed_speed
                    else "samples"
                )
                frames = (
                    history
                    if first or gap or changed_speed
                    else [f for f in history if f["sequence"] > last_tick]
                )
                if not frames and not first:
                    kind = "lifecycle" if status["status"] != last_state else "clock"
                streams = sorted({frame["stream_id"] for frame in frames})
                ranges = [
                    {
                        "stream_id": stream,
                        "first": min(f["sequence"] for f in frames if f["stream_id"] == stream),
                        "last": max(f["sequence"] for f in frames if f["stream_id"] == stream),
                    }
                    for stream in streams
                ]
                message = VisualMessage.model_validate_json(
                    json.dumps(
                        dict(
                            visual_schema_version="visual.v1",
                            type=kind,
                            run_id=run_id,
                            sent_at=datetime.now(UTC).isoformat(),
                            status=status,
                            frames=frames,
                            ranges=ranges,
                        )
                    )
                )
                principal.require({"viewer_control", "operator"}, run_id)
                # A blocked send never creates a server-side unbounded delivery queue.
                await asyncio.wait_for(websocket.send_text(message.model_dump_json()), timeout=2)
                first = False
                last_tick, last_state, last_speed = (
                    status["committed_tick"],
                    status["status"],
                    status["requested_speed"],
                )
                await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
    except (ServiceError, TimeoutError):
        await websocket.close(code=1008, reason="Session expired or client must resynchronize")
    except Exception as error:
        logger.error("visual_failed", extra={"run_id": run_id, "error_type": type(error).__name__})
        await websocket.close(code=1011, reason="Visual stream is unavailable")
    finally:
        if public_slot:
            context.public_viewer_slots.release()
