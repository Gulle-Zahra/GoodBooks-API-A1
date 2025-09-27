import requests

BASE = "http://localhost:8000"

def test_health():
    r = requests.get(f"{BASE}/healthz", timeout=5)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_list_books():
    r = requests.get(f"{BASE}/books?page=1&page_size=5", timeout=5)
    assert r.status_code == 200
    j = r.json()
    assert "items" in j and isinstance(j["items"], list)
