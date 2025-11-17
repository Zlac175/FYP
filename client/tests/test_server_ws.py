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

def test_two_clients_same_game_see_consistent_state():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/shared-game") as ws1, \
         client.websocket_connect("/ws/game/shared-game") as ws2:

        # Both should receive an initial state
        init1 = ws1.receive_json()
        init2 = ws2.receive_json()

        assert init1["type"] == "state"
        assert init2["type"] == "state"
        assert init1["fen"] == init2["fen"]

        # Client 1 plays a legal move
        ws1.send_json({
            "type": "move",
            "gameId": "shared-game",
            "from": "e2",
            "to": "e4",
            "promotion": None,
        })

        # Both clients should now receive the updated board
        upd1 = ws1.receive_json()
        upd2 = ws2.receive_json()

        assert upd1["type"] == "state"
        assert upd2["type"] == "state"

        # Both see the exact same FEN and last move
        assert upd1["fen"] == upd2["fen"]
        assert upd1["lastMove"] == {"from": "e2", "to": "e4"}
        assert upd2["lastMove"] == {"from": "e2", "to": "e4"}

def test_two_independent_games_do_not_interfere():
    client = TestClient(app)

    with client.websocket_connect("/ws/game/game-a") as ws_a, \
         client.websocket_connect("/ws/game/game-b") as ws_b:

        init_a = ws_a.receive_json()
        init_b = ws_b.receive_json()

        # Same starting FEN, but they are separate games
        assert init_a["fen"] == init_b["fen"]

        # Play a move in game A only
        ws_a.send_json({
            "type": "move",
            "gameId": "game-a",
            "from": "e2",
            "to": "e4",
            "promotion": None,
        })
        upd_a = ws_a.receive_json()

        # Now play a *different* move in game B
        ws_b.send_json({
            "type": "move",
            "gameId": "game-b",
            "from": "d2",
            "to": "d4",
            "promotion": None,
        })
        upd_b = ws_b.receive_json()

        # Each game should have its own FEN; neither overwrote the other
        assert upd_a["fen"] != init_a["fen"]
        assert upd_b["fen"] != init_b["fen"]
        assert upd_a["fen"] != upd_b["fen"]

        # Each game tracks its own lastMove
        assert upd_a["lastMove"] == {"from": "e2", "to": "e4"}
        assert upd_b["lastMove"] == {"from": "d2", "to": "d4"}
