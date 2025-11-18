from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from pathlib import Path
from typing import Dict, Set, Any
import random

from client.game_state import ChessGame

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
Room = Dict[str, Any]
rooms: Dict[str, Room] = {}


def new_room() -> Room:
    return {
        "game": ChessGame(),
        "clients": set(),              # all sockets in this game
        "player_colors": {},           # websocket -> "white" / "black"
        "seats": {"white": None, "black": None},  # colour -> websocket
        "host_color": None,            # chosen by host
        "guest_color": None,
    }


def get_room(game_id: str) -> Room:
    room = rooms.get(game_id)
    if room is None:
        room = new_room()
        rooms[game_id] = room
    return room


async def broadcast(room: Room) -> None:
    clients: Set[WebSocket] = room["clients"]
    if not clients:
        return

    payload = room["game"].state_payload()
    msg = json.dumps(payload)
    await asyncio.gather(
        *[ws.send_text(msg) for ws in list(clients)],
        return_exceptions=True,
    )


def assign_host(room: Room, websocket: WebSocket, preferred_color: str | None) -> str:
    """Assign host colour and return it."""
    # Decide colours
    if preferred_color == "white":
        host_color = "white"
    elif preferred_color == "black":
        host_color = "black"
    elif preferred_color == "random":
        host_color = random.choice(["white", "black"])
    else:
        host_color = "white"

    guest_color = "black" if host_color == "white" else "white"

    room["host_color"] = host_color
    room["guest_color"] = guest_color

    room["seats"][host_color] = websocket
    room["player_colors"][websocket] = host_color
    # guest seat will be filled when guest joins

    return host_color


def assign_guest(room: Room, websocket: WebSocket) -> str:
    """Assign guest to remaining colour and return it."""
    host_color = room.get("host_color") or "white"
    guest_color = room.get("guest_color") or ("black" if host_color == "white" else "white")

    room["guest_color"] = guest_color
    room["seats"][guest_color] = websocket
    room["player_colors"][websocket] = guest_color
    return guest_color


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

            if msg_type == "join":
                role = msg.get("role")
                preferred = msg.get("preferredColor")
                if role == "host":
                    colour = assign_host(room, websocket, preferred)
                elif role == "guest":
                    colour = assign_guest(room, websocket)
                else:
                    # Unknown role: treat as spectator
                    colour = None

                ack = {
                    "type": "joined",
                    "youAre": colour,
                    "gameId": game_id,
                }
                await websocket.send_text(json.dumps(ack))
                # Optionally broadcast current state again
                await websocket.send_text(json.dumps(game.state_payload()))
                continue

            if msg_type == "reset":
                game.reset()
                await broadcast(room)
                continue

            if msg_type == "move":
                from_sq = msg.get("from")
                to_sq = msg.get("to")
                promo = msg.get("promotion")

                if not (from_sq and to_sq):
                    await websocket.send_text(json.dumps(game.state_payload()))
                    continue

                # Enforce colours only once someone has joined with a colour
                enforce_colors = bool(room.get("player_colors"))
                if enforce_colors:
                    player_color = room["player_colors"].get(websocket)
                    turn_color = "white" if game.board.turn else "black"

                    if player_color is None or player_color != turn_color:
                        # Not your turn or spectator: no-op, send current state
                        await websocket.send_text(json.dumps(game.state_payload()))
                        continue

                moved = game.make_move(from_sq, to_sq, promo)
                if moved:
                    await broadcast(room)
                else:
                    await websocket.send_text(json.dumps(game.state_payload()))
                continue

            # Unknown message type: send current state back
            await websocket.send_text(json.dumps(game.state_payload()))

    except WebSocketDisconnect:
        clients.discard(websocket)
        # Clean up colour assignments
        player_colors = room["player_colors"]
        if websocket in player_colors:
            colour = player_colors.pop(websocket)
            seats = room["seats"]
            if seats.get(colour) is websocket:
                seats[colour] = None
