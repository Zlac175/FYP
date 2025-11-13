from js import document, WebSocket
from pyodide.ffi import create_proxy
import chess
import json as _json

# ---- DOM elements ----
BOARD = document.getElementById("board")
WS_STATUS = document.getElementById("ws-status")
TURN = document.getElementById("turn")
FEN = document.getElementById("fen")
GAMEOVER = document.getElementById("gameover")
GID = document.getElementById("gid")

# ---- Config ----
# Automatically use ws:// or wss:// based on page protocol
SCHEME = "wss" if document.location.protocol == "https:" else "ws"
ORIGIN = str(document.location.origin)              
BASE_WS = ORIGIN.replace("http://", "ws://").replace("https://", "wss://")
GAME_ID = "demo"  # change this to make different rooms
GID.innerText = GAME_ID

# ---- Local UI state ----
orientation = "white"  # "black" flips the view
selected = None
legal_targets = set()
last_move = None
board_model = chess.Board()  # server is authoritative

# ---- Helpers ----
files = ['a','b','c','d','e','f','g','h']
ranks = [1,2,3,4,5,6,7,8]

def set_status(text: str):
    WS_STATUS.innerText = text


def render_board():
    """Draw the board based on the current FEN and orientation."""
    oriented_files = files if orientation == "white" else list(reversed(files))
    oriented_ranks = list(reversed(ranks)) if orientation == "white" else ranks

    # Clear current board
    while BOARD.firstChild:
        BOARD.removeChild(BOARD.firstChild)

    # Draw all 64 squares
    for r_idx, r in enumerate(oriented_ranks):
        for f_idx, f in enumerate(oriented_files):
            sq = f"{f}{r}"
            piece = board_model.piece_at(chess.parse_square(sq))

            btn = document.createElement("button")
            btn.classList.add("sq")
            btn.classList.add("light" if (f_idx + r_idx) % 2 == 0 else "dark")
            btn.setAttribute("data-sq", sq)

            # Highlight last move and selected squares
            if last_move and (sq == last_move.get('from') or sq == last_move.get('to')):
                btn.classList.add("last")
            if selected == sq:
                btn.classList.add("selected")
            if sq in legal_targets:
                btn.classList.add("target")

            # Draw Unicode chess pieces
            if piece:
                glyphs = {
                    chess.PAWN:  {True: '♙', False: '♟'},
                    chess.ROOK:  {True: '♖', False: '♜'},
                    chess.KNIGHT:{True: '♘', False: '♞'},
                    chess.BISHOP:{True: '♗', False: '♝'},
                    chess.QUEEN: {True: '♕', False: '♛'},
                    chess.KING:  {True: '♔', False: '♚'},
                }
                btn.innerText = glyphs.get(piece.piece_type, {}).get(piece.color, '')

            # Coordinate labels
            if r_idx == 7:
                lab = document.createElement("span")
                lab.classList.add("coord", "file")
                lab.innerText = f
                btn.appendChild(lab)
            if f_idx == 0:
                lab = document.createElement("span")
                lab.classList.add("coord", "rank")
                lab.innerText = str(r)
                btn.appendChild(lab)

            def on_click(ev, sq=sq):
                handle_click(sq)

            btn.addEventListener("click", create_proxy(on_click))
            BOARD.appendChild(btn)


def legal_moves_from(square_str: str):
    """Return all legal target squares for a selected piece."""
    moves = set()
    try:
        src = chess.parse_square(square_str)
        for mv in board_model.legal_moves:
            if mv.from_square == src:
                moves.add(chess.square_name(mv.to_square))
    except Exception:
        pass
    return moves


def handle_click(sq: str):
    """Handle clicking on a square (select or attempt a move)."""
    global selected, legal_targets
    if selected is None:
        # Select a piece
        try:
            piece = board_model.piece_at(chess.parse_square(sq))
        except Exception:
            piece = None
        if not piece:
            return
        selected = sq
        legal_targets = legal_moves_from(sq)
        render_board()
        return

    # Re-click same square to deselect
    if selected == sq:
        selected = None
        legal_targets = set()
        render_board()
        return

    # Try to move selected -> sq
    promotion = None
    try:
        src = chess.parse_square(selected)
        dst = chess.parse_square(sq)
        piece = board_model.piece_at(src)
        if piece and piece.piece_type == chess.PAWN:
            rank = chess.square_rank(dst)
            if (piece.color and rank == 7) or ((not piece.color) and rank == 0):
                promotion = "q"  # always promote to queen
    except Exception:
        pass

    ws.send(_json.dumps({
        "type": "move",
        "gameId": GAME_ID,
        "from": selected,
        "to": sq,
        "promotion": promotion
    }))
    selected = None
    legal_targets = set()


# ---- WebSocket connection ----
ws = WebSocket.new(f"{BASE_WS}/ws/game/{GAME_ID}")

def _onopen(evt):
    set_status("connected")

def _onclose(evt):
    set_status("disconnected")

def _onerror(evt):
    set_status("error")

def _onmessage(evt):
    """Handle state updates from the server."""
    global board_model, last_move, selected, legal_targets
    try:
        msg = _json.loads(evt.data)
        if msg.get("type") == "state" and msg.get("fen"):
            board_model = chess.Board()
            board_model.set_fen(msg["fen"])
            last_move = msg.get("lastMove")
            TURN.innerText = msg.get("turn", "—")
            FEN.innerText = msg["fen"]

            # Game over panel
            if msg.get("gameOver"):
                GAMEOVER.style.display = "block"
                GAMEOVER.innerText = "Game over"
            else:
                GAMEOVER.style.display = "none"

            selected = None
            legal_targets = set()
            render_board()
    except Exception:
        set_status("message error")

ws.onopen = create_proxy(_onopen)
ws.onclose = create_proxy(_onclose)
ws.onerror = create_proxy(_onerror)
ws.onmessage = create_proxy(_onmessage)


# ---- Buttons ----
def on_flip(_):
    global orientation
    orientation = "black" if orientation == "white" else "white"
    render_board()

def on_new(_):
    ws.send(_json.dumps({"type": "reset", "gameId": GAME_ID}))

document.getElementById("flip").addEventListener("click", create_proxy(on_flip))
document.getElementById("new").addEventListener("click", create_proxy(on_new))

# ---- Initial render ----
render_board()
