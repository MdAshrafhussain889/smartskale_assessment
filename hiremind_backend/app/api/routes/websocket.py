"""
WebSocket endpoint for live proctoring stream.
ws://host/ws/proctor/{session_id}?token=<jwt>
"""
import json
import logging
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory connection registry: attempt_id -> list[WebSocket]
_connections: dict[str, list[WebSocket]] = {}


async def broadcast_proctor_event(session_id: str, payload: dict):
    """Broadcast a proctoring payload to live viewers for an attempt."""
    stale = []
    for ws in list(_connections.get(session_id, [])):
        try:
            await ws.send_json(payload)
        except Exception:
            stale.append(ws)

    for ws in stale:
        try:
            _connections.get(session_id, []).remove(ws)
        except ValueError:
            pass


@router.websocket("/ws/proctor/{session_id}")
async def proctor_ws(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """
    Live proctoring WebSocket.
    - Candidates send violation events as JSON messages.
    - Recruiters can connect to the same session_id to monitor in real time.
    """
    # Authenticate
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        role = payload.get("role", "candidate")
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    _connections.setdefault(session_id, []).append(websocket)
    logger.info("WS connect: user=%s role=%s session=%s", user_id, role, session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            # Broadcast to all connections on this session (recruiters see it too)
            for ws in list(_connections.get(session_id, [])):
                if ws is not websocket:
                    try:
                        await ws.send_json({
                            "from": user_id,
                            "role": role,
                            "session_id": session_id,
                            **msg,
                        })
                    except Exception:
                        pass

            # Acknowledge to sender
            await websocket.send_json({"ack": True, "event": msg.get("event_type")})

    except WebSocketDisconnect:
        conns = _connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
        logger.info("WS disconnect: user=%s session=%s", user_id, session_id)
