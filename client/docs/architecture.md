# System Architecture

## 1. Overview

This project implements a real-time chess system built entirely in Python.

- **Backend:** FastAPI application providing HTTP routes and a WebSocket endpoint.
- **Frontend:** HTML page using PyScript to run Python (`client.py`) directly in the browser.
- **Game Rules:** Implemented using the `python-chess` library.
- **Network Model:** WebSockets are used for real-time state updates.
- **Concurrency Model:** Multiple games and clients run concurrently in a single FastAPI server using Python’s `asyncio`.

---

## 2. High-Level Architecture Diagram (Textual)

### Components

- **Frontend**
  - `templates/index.html`
  - `client.py`
  - `pyscript.toml`

- **Backend**
  - `server.py`
  - WebSocket handler
  - Room manager (dictionary of game states)
  - Rule enforcement via `python-chess`

### System Flow

1. Browser loads `index.html`.
2. PyScript loads and executes `client.py` in the browser.
3. Client opens WebSocket connection to `/ws/game/{game_id}`.
4. Server loads or creates that game room.
5. Client sends moves / reset commands.
6. Server validates moves and broadcasts state to all clients in the room.

---

## 3. Backend Architecture (`client/server.py`)

The backend is a FastAPI server responsible for:

- Serving the frontend files.
- Managing game rooms.
- Enforcing chess rules.
- Running multiple WebSocket connections concurrently.

### 3.1. Room Registry

The server tracks all active games in a global dictionary:

```
rooms: dict[str, dict] = {}
```

Each room has this structure:

```
{
  "board": chess.Board(),       # python-chess board instance
  "clients": set(),             # set of active WebSocket connections
  "lastMove": {...} or None     # metadata for last move
}
```

### 3.2. State Payload Format

The server encodes game state into a JSON-friendly format:

```
{
  "type": "state",
  "fen": "<FEN-string>",
  "lastMove": { "from": "...", "to": "..." },
  "turn": "white" or "black",
  "gameOver": true or false
}
```

The client reconstructs the chessboard from this information.

---

## 4. WebSocket Flow

### Connection Lifecycle

1. **Accept Connection**
   - Server accepts WebSocket.
   - Finds or creates a room for `{game_id}`.
   - Adds the client WebSocket to the room.

2. **Send Initial State**
   - Server sends the current FEN + metadata.

3. **Message Loop**
   - Server waits for JSON messages:
     - `"move"` → attempt to play a move  
     - `"reset"` → reset the board

4. **Move Handling**
   - Server validates the move via `python-chess`.
   - If legal:
     - Server updates the board.
     - Updates `lastMove`.
     - Broadcasts state to all clients.
   - If illegal:
     - Server re-sends current state to the sender only.

5. **Disconnect**
   - When a client disconnects, its WebSocket is removed from the room.

---

## 5. Concurrency Model

The system uses Python’s `asyncio` event-driven model:

- All WebSocket connections run as **asynchronous tasks**.
- Each task yields during network waits, allowing others to run.
- Multiple games run concurrently because each game lives in its own isolated dictionary entry.
- FastAPI + Uvicorn handle the event loop and scheduling.

### Thread Safety

- The server currently runs in a **single process**, single event loop.
- All accesses to `rooms` occur from the same thread.
- No locks are needed at this stage.

### Future Extensions

- Add multiprocessing for stronger isolation.
- Use Redis/Postgres for persistent game state.
- Create a dedicated game manager worker process.

---

## 6. Frontend Architecture

### 6.1. HTML Interface (`templates/index.html`)

This file:

- Defines the page layout.
- Contains the chessboard container.
- Includes buttons (flip board, new game).
- Shows status elements (turn, FEN, WebSocket status).
- Loads PyScript and `client.py`.

### 6.2. PyScript Client Logic (`client/client.py`)

The client performs:

- Rendering of all 64 squares.
- Highlighting selected piece, legal moves and last move.
- Tracking board orientation (flip).
- Sending `"move"` and `"reset"` messages to the server.
- Updating the board from server messages.

### WebSocket Message Examples

**Client → Server (move):**
```
{
  "type": "move",
  "gameId": "demo",
  "from": "e2",
  "to": "e4",
  "promotion": "q"
}
```

**Client → Server (reset):**
```
{ "type": "reset", "gameId": "demo" }
```

**Server → Client (state):**
```
{
  "type": "state",
  "fen": "...",
  "lastMove": { "from": "...", "to": "..." },
  "turn": "white",
  "gameOver": false
}
```

---

## 7. Future Extensions

This architecture provides a strong base for later expansion:

- Multiple different game types.
- Room creation UI.
- Spectator mode.
- Persistent storage for game state/history.
- Structured logging and central error handling.
- Load balancing across multiple worker processes.
- A standalone Game Manager service.

---
