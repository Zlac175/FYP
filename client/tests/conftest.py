from fastapi.testclient import TestClient
from client.server import app


def get_test_client() -> TestClient:
    return TestClient(app)


def client():
    return TestClient(app)
