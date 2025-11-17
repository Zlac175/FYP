from fastapi.testclient import TestClient
from client.server import app


def test_index_route_serves_html():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text.lower()
    assert "<html" in text
    assert "chess poc" in text or "chess" in text


def test_client_py_route_serves_python():
    client = TestClient(app)
    resp = client.get("/client.py")
    assert resp.status_code == 200
    # Should at least look like Python source
    assert "def " in resp.text or "import " in resp.text


def test_pyscript_toml_route_serves_toml():
    client = TestClient(app)
    resp = client.get("/pyscript.toml")
    assert resp.status_code == 200
    assert "name =" in resp.text
