from client.game_state import ChessGame


def test_legal_move_updates_state():
    game = ChessGame()

    # Starting position: e2e4 is legal
    moved = game.make_move("e2", "e4")
    assert moved is True
    assert game.last_move == {"from": "e2", "to": "e4"}

    state = game.state_payload()
    assert state["type"] == "state"
    assert state["turn"] == "black"  # after white moves, black to move
    assert state["gameOver"] is False


def test_illegal_move_is_rejected():
    game = ChessGame()

    # e2e5 is illegal (pawn cannot move 3 squares)
    moved = game.make_move("e2", "e5")
    assert moved is False
    # Board should not have any moves played
    assert len(game.board.move_stack) == 0
    assert game.last_move is None


def test_reset_restores_start_position():
    game = ChessGame()
    game.make_move("e2", "e4")
    assert len(game.board.move_stack) == 1

    game.reset()
    assert len(game.board.move_stack) == 0

    state = game.state_payload()
    # FEN of a starting chess position begins with this piece layout
    assert state["fen"].startswith("rnbqkbnr")
    assert state["turn"] == "white"
