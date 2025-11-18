from js import document, WebSocket
from pyodide.ffi import create_proxy
import chess
import json as _json
import random
import string

# ---- DOM elements ----
BOARD = document.getElementById("board")
WS_STATUS = document.getElementById("ws-status")
TURN = document.getElementById("turn")
FEN = document.getElementById("fen")
GAMEOVER = document.getElementById("gameover")
GID = document.getElementById("gid")
YOU_ARE = document.getElementById("you-are")

HOST_COLOR = document.getElementById("host-color")
HOST_BTN = document.getElementById("host-btn")
JOIN_CODE = document.getElementById("join-code")
JOIN_BTN = document.getElementById("join-btn")

# ---- Config ----
SCHEME = "wss" if document.location.protocol == "https:" else "ws"
ORIGIN = str(document.location.origin)
BASE_WS = ORIGIN.replace("http://", "ws://").replace("https://", "wss://")

# ---- Local UI state ----
GAME_ID = None         # assigned when host/join
orientation = "white"  # "black" flips the view
selected = None
legal_targets = set()
last_move = None
board_model = chess.Board()  # local mirror; server is authoritative
my_color = None              # "white" or "black"
ws = None                    # WebSocket, created on join

# ---- Helpers ----
files = ["a", "b", "c", "d", "e", "f", "g", "h"]
ranks = [1, 2, 3, 4, 5, 6, 7, 8]


def set_status(text: str) -> None:
    WS_STATUS.innerText = text


def generate_game_id(length: int = 6) -> str:
    # Short, friendly code; avoid ambiguous chars
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(random.choice(alphabet) for _ in range(length))


def is_my_turn() -> bool:
    if my_color is None:
        return True  # allow moves before colours are assigned (fallback)
    if board_model.turn and my_color == "white":
        return True
    if (not board_model.turn) and my_color == "black":
        return True
    return False


def square_belongs_to_me(sq: str) -> bool:
    if my_color is None:
        return True
    try:
        piece = board_model.piece_at(chess.parse_square(sq))
    except Exception:
        return False
    if not piece:
        return False
    if my_color == "white" and piece.color:
        return True
    if my_color == "black" and not piece.color:
        return True
    return False


def render_board() -> None:
    oriented_files = files if orientation == "white" else list(reversed(files))
    oriented_ranks = list(reversed(ranks)) if orientation == "white" else ranks

    while BOARD.firstChild:
        BOARD.removeChild(BOARD.firstChild)

    for r_idx, r in enumerate(oriented_ranks):
        for f_idx, f in enumerate(oriented_files):
            sq = f"{f}{r}"
            piece = board_model.piece_at(chess.parse_square(sq))

            btn = document.createElement("button")
            btn.classList.add("sq")
            btn.classList.add("light" if (f_idx + r_idx) % 2 == 0 else "dark")
            btn.setAttribute("data-sq", sq)

            if last_move and (sq == last_move.get("from") or sq == last_move.get("to")):
                btn.classList.add("last")
            if selected == sq:
                btn.classList.add("selected")
            if sq in legal_targets:
                btn.classList.add("target")

            if piece:
                glyphs = {
                    chess.PAWN: {True: "♙", False: "♟"},
                    chess.ROOK: {True: "♖", False: "♜"},
                    chess.KNIGHT: {True: "♘", False: "♞"},
                    chess.BISHOP: {True: "♗", False: "♝"},
                    chess.QUEEN: {True: "♕", False: "♛"},
                    chess.KING: {True: "♔", False: "♚"},
                }
                btn.innerText = glyphs.get(piece.piece_type, {}).get(piece.color, "")

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
    moves = set()
    try:
        src = chess.parse_square(square_str)
        for mv in board_model.legal_moves:
            if mv.from_square == src:
                moves.add(chess.square_name(mv.to_square))
    except Exception:
        pass
    return moves


def handle_click(sq: str) -> None:
    global selected, legal_targets
    if ws is None:
        return

    if not is_my_turn():
        # Optional: could flash a message instead
        return

    if selected is None:
        if not square_belongs_to_me(sq):
            return
        selected = sq
        legal_targets = legal_moves_from(sq)
        render_board()
        return

    if selected == sq:
        selected = None
        legal_targets = set()
        render_board()
        return

    promotion = None
    try:
        src = chess.parse_square(selected)
        dst = chess.parse_square(sq)
        piece = board_model.piece_at(src)
        if piece and piece.piece_type == chess.PAWN:
            rank = chess.square_rank(dst)
            if (piece.color and rank == 7) or ((not piece.color) and rank == 0):
                promotion = "q"
    except Exception:
        pass

    ws.send(
        _json.dumps(
            {
                "type": "move",
                "gameId": GAME_ID,
                "from": selected,
                "to": sq,
                "promotion": promotion,
            }
        )
    )
    selected = None
    legal_targets = set()


# ---- WebSocket wiring ----
def attach_ws_handlers() -> None:
    def _onopen(evt):
        set_status("connected")

    def _onclose(evt):
        set_status("disconnected")

    def _onerror(evt):
        set_status("error")

    def _onmessage(evt):
        global board_model, last_move, selected, legal_targets, my_color, orientation

        try:
            msg = _json.loads(evt.data)
        except Exception:
            set_status("message error")
            return

        msg_type = msg.get("type")

        if msg_type == "joined":
            my_color = msg.get("youAre")
            YOU_ARE.innerText = my_color or "—"
            if my_color in ("white", "black"):
                orientation = my_color
                render_board()
            return

        if msg_type == "state" and msg.get("fen"):
            board_model = chess.Board()
            board_model.set_fen(msg["fen"])
            last_move = msg.get("lastMove")
            TURN.innerText = msg.get("turn", "—")
            FEN.innerText = msg["fen"]

            if msg.get("gameOver"):
                GAMEOVER.style.display = "block"
                GAMEOVER.innerText = "Game over"
            else:
                GAMEOVER.style.display = "none"

            selected = None
            legal_targets = set()
            render_board()
            return

    global ws
    ws.onopen = create_proxy(_onopen)
    ws.onclose = create_proxy(_onclose)
    ws.onerror = create_proxy(_onerror)
    ws.onmessage = create_proxy(_onmessage)


def connect_ws(game_id: str, role: str, preferred_color: str | None) -> None:
    """Create WS, send join message, and update UI."""
    global ws, GAME_ID, my_color, orientation

    # Close previous WS if any
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass

    GAME_ID = game_id
    GID.innerText = GAME_ID
    my_color = None
    YOU_ARE.innerText = "—"

    url = f"{BASE_WS}/ws/game/{GAME_ID}"
    ws = WebSocket.new(url)
    attach_ws_handlers()

    # Small join message once connection is open; use a timer to be safe
    def send_join():
        if ws is None:
            return
        msg = {
            "type": "join",
            "gameId": GAME_ID,
            "role": role,
            "preferredColor": preferred_color,
        }
        ws.send(_json.dumps(msg))

    # Schedule join after a short delay so socket is ready
    from js import setTimeout
    setTimeout(create_proxy(lambda *_: send_join()), 50)


# ---- Buttons ----
def on_flip(_):
    global orientation
    orientation = "black" if orientation == "white" else "white"
    render_board()


def on_new(_):
    if ws is None or GAME_ID is None:
        return
    ws.send(_json.dumps({"type": "reset", "gameId": GAME_ID}))


def on_host(_):
    color_choice = HOST_COLOR.value  # "white", "black", "random"
    game_id = generate_game_id()
    set_status("connecting (host)...")
    connect_ws(game_id, role="host", preferred_color=color_choice)


def on_join(_):
    code = (JOIN_CODE.value or "").strip()
    if not code:
        return
    set_status("connecting (guest)...")
    connect_ws(code, role="guest", preferred_color=None)


document.getElementById("flip").addEventListener("click", create_proxy(on_flip))
document.getElementById("new").addEventListener("click", create_proxy(on_new))
HOST_BTN.addEventListener("click", create_proxy(on_host))
JOIN_BTN.addEventListener("click", create_proxy(on_join))

# ---- Initial render ----
render_board()
set_status("idle (host or join a game)")
