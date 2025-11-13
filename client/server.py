from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import chess
import asyncio
import json
from pathlib import Path

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ---- Game room storage ----
rooms: dict[str, dict] = {}

def room_state_payload(room: dict) -> dict:
    board: chess.Board = room["board"]
    return {
        "type": "state",
        "fen": board.fen(),
        "lastMove": room.get("lastMove"),
        "turn": "white" if board.turn else "black",
        "gameOver": board.is_game_over(),
    }

async def broadcast(room: dict):
    if not room["clients"]:
        return
    msg = json.dumps(room_state_payload(room))
    await asyncio.gather(*[ws.send_text(msg) for ws in list(room["clients"])], return_exceptions=True)

# ---- Serve frontend files ----
@app.get("/")
async def index():
    html = Path("templates/index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/client.py")
async def serve_client_py():
    return FileResponse("client.py")

@app.get("/pyscript.toml")
async def serve_pyscript_toml():
    return FileResponse("pyscript.toml")

# ---- WebSocket endpoint ----
@app.websocket("/ws/game/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str):
    await websocket.accept()
    room = rooms.setdefault(game_id, {"board": chess.Board(), "clients": set(), "lastMove": None})
    room["clients"].add(websocket)
    await websocket.send_text(json.dumps(room_state_payload(room)))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "reset":
                room["board"] = chess.Board()
                room["lastMove"] = None
                await broadcast(room)
                continue

            if msg.get("type") == "move":
                from_sq = msg.get("from")
                to_sq = msg.get("to")
                promo = msg.get("promotion")
                if not (from_sq and to_sq):
                    await websocket.send_text(json.dumps(room_state_payload(room)))
                    continue
                uci = from_sq + to_sq + (promo[0] if promo else "")
                move = chess.Move.from_uci(uci)
                if move in room["board"].legal_moves:
                    room["board"].push(move)
                    room["lastMove"] = {"from": from_sq, "to": to_sq}
                    await broadcast(room)
                else:
                    await websocket.send_text(json.dumps(room_state_payload(room)))
    except WebSocketDisconnect:
        room["clients"].discard(websocket)