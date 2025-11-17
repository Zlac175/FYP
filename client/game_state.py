import chess

# Simple class that owns all chess game state and rules
class ChessGame:
    def __init__(self) -> None:
        self.board = chess.Board()
        self.last_move: dict | None = None

    def reset(self) -> None:
        """Reset the game to the initial position."""
        self.board = chess.Board()
        self.last_move = None

    def make_move(self, src: str, dst: str, promotion: str | None = None) -> bool:
        """
        Try to play a move.
        Returns True if it was legal and applied, False otherwise.
        """
        promo_suffix = (promotion or "").strip()[:1]
        uci = f"{src}{dst}{promo_suffix}"

        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False

        if move in self.board.legal_moves:
            self.board.push(move)
            self.last_move = {"from": src, "to": dst}
            return True

        return False

    def state_payload(self) -> dict:
        """Return the current game state as a JSON-friendly dict."""
        return {
            "type": "state",
            "fen": self.board.fen(),
            "lastMove": self.last_move,
            "turn": "white" if self.board.turn else "black",
            "gameOver": self.board.is_game_over(),
        }
