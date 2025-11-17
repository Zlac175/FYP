from fastapi.testclient import TestClient
from client.server import app


def test_ws_initial_state():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/test-game-1") as ws:
        initial = ws.receive_json()
        # Basic shape checks
        assert initial["type"] == "state"
        assert "fen" in initial
        assert initial["gameOver"] in (True, False)
        assert initial["turn"] in ("white", "black")


def test_ws_legal_move_updates_state():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/test-game-2") as ws:
        initial = ws.receive_json()

        # e2e4 should be legal as first move
        ws.send_json({
            "type": "move",
            "gameId": "test-game-2",
            "from": "e2",
            "to": "e4",
            "promotion": None,
        })

        updated = ws.receive_json()
        assert updated["type"] == "state"
        # Board FEN should change after a legal move
        assert updated["fen"] != initial["fen"]
        assert updated["lastMove"] == {"from": "e2", "to": "e4"}


def test_ws_illegal_move_does_not_change_state():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/test-game-3") as ws:
        initial = ws.receive_json()

        # e2e5 is illegal from the starting position
        ws.send_json({
            "type": "move",
            "gameId": "test-game-3",
            "from": "e2",
            "to": "e5",
            "promotion": None,
        })

        # Server should send back current state (unchanged FEN)
        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["fen"] == initial["fen"]


def test_ws_reset_resets_board():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/test-game-4") as ws:
        initial = ws.receive_json()

        # Make a legal move first
        ws.send_json({
            "type": "move",
            "gameId": "test-game-4",
            "from": "e2",
            "to": "e4",
            "promotion": None,
        })
        moved_state = ws.receive_json()
        assert moved_state["fen"] != initial["fen"]

        # Now reset
        ws.send_json({
            "type": "reset",
            "gameId": "test-game-4",
        })
        reset_state = ws.receive_json()

        # After reset, FEN should be back to starting position
        assert reset_state["fen"].startswith("rnbqkbnr")
        assert reset_state["turn"] == "white"
