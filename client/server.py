from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from pathlib import Path
from typing import Dict, Set, Any

from client.game_state import ChessGame  # core chess logic

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Paths ----
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"
CLIENT_PY_PATH = BASE_DIR / "client.py"
PYSCRIPT_TOML_PATH = BASE_DIR / "pyscript.toml"

# ---- Game room storage ----
# Each room holds a ChessGame instance plus its connected WebSockets.
Room = Dict[str, Any]
rooms: Dict[str, Room] = {}


def get_room(game_id: str) -> Room:
    """Get or create a room for this game id."""
    room = rooms.get(game_id)
    if room is None:
        room = {"game": ChessGame(), "clients": set()}
        rooms[game_id] = room
    return room


async def broadcast(room: Room) -> None:
    """Send the current game state to all clients in the room."""
    clients: Set[WebSocket] = room["clients"]
    if not clients:
        return

    payload = room["game"].state_payload()
    msg = json.dumps(payload)
    await asyncio.gather(
        *[ws.send_text(msg) for ws in list(clients)],
        return_exceptions=True,
    )


# ---- Serve frontend files ----
@app.get("/")
async def index() -> HTMLResponse:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/client.py")
async def serve_client_py() -> FileResponse:
    return FileResponse(CLIENT_PY_PATH)


@app.get("/pyscript.toml")
async def serve_pyscript_toml() -> FileResponse:
    return FileResponse(PYSCRIPT_TOML_PATH)


# ---- WebSocket endpoint ----
@app.websocket("/ws/game/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str) -> None:
    await websocket.accept()

    room = get_room(game_id)
    clients: Set[WebSocket] = room["clients"]
    game: ChessGame = room["game"]

    clients.add(websocket)

    # Send initial state
    await websocket.send_text(json.dumps(game.state_payload()))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "reset":
                # Reset the game and broadcast fresh state
                game.reset()
                await broadcast(room)
                continue

            if msg_type == "move":
                from_sq = msg.get("from")
                to_sq = msg.get("to")
                promo = msg.get("promotion")

                # Basic input validation
                if not (from_sq and to_sq):
                    await websocket.send_text(json.dumps(game.state_payload()))
                    continue

                moved = game.make_move(from_sq, to_sq, promo)
                if moved:
                    # Legal move, broadcast to all in the room
                    await broadcast(room)
                else:
                    # Illegal move, just send this client the current state
                    await websocket.send_text(json.dumps(game.state_payload()))
                continue

            # Unknown message type: send current state back
            await websocket.send_text(json.dumps(game.state_payload()))

    except WebSocketDisconnect:
        clients.discard(websocket)
