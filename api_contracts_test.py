import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/reset")
        yield c
        c.post("/reset")


def test_end_001_reset_and_clean_system_state(client):
    client.post("/ues", json={"ue_id": 1})
    client.post("/ues/1/bearers", json={"bearer_id": 2})
    
    response = client.post("/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}
    
    list_response = client.get("/ues")
    assert list_response.status_code == 200
    assert list_response.json() == {"ues": []}


def test_end_002_register_new_ue_and_assign_default_bearer(client):
    response = client.post("/ues", json={"ue_id": 50})
    assert response.status_code == 200
    assert response.json() == {"status": "attached", "ue_id": 50}
    
    display_response = client.get("/ues/50")
    assert display_response.status_code == 200
    
    data = display_response.json()
    assert data["ue_id"] == 50
    assert "9" in data["bearers"]
    assert data["bearers"]["9"]["bearer_id"] == 9
    assert data["bearers"]["9"]["active"] is False


def test_end_003_reject_out_of_bounds_ue_id(client):
    res_low = client.post("/ues", json={"ue_id": 0})
    assert res_low.status_code == 422
    
    res_high = client.post("/ues", json={"ue_id": 101})
    assert res_high.status_code == 422


def test_end_004_block_duplicate_ue_registration(client):
    client.post("/ues", json={"ue_id": 10})
    
    response = client.post("/ues", json={"ue_id": 10})
    
    assert response.status_code == 400
    assert "already attached" in response.json()["detail"]


def test_end_005_prevent_deletion_of_default_bearer(client):
    client.post("/ues", json={"ue_id": 12})
    
    response = client.delete("/ues/12/bearers/9")
    
    assert response.status_code == 400
    assert "Cannot remove default bearer" in response.json()["detail"]


def test_end_006_verify_static_route_parsing_no_route_collisions(client):
    client.post("/ues", json={"ue_id": 5})
    
    response = client.get("/ues/stats")
    
    assert response.status_code == 200
    assert response.json()["scope"] == "all"
    assert response.json()["ue_count"] == 1


def test_end_007_add_secondary_bearer(client):
    client.post("/ues", json={"ue_id": 7})
    
    response = client.post("/ues/7/bearers", json={"bearer_id": 3})
    assert response.status_code == 200
    assert response.json() == {"status": "bearer_added", "ue_id": 7, "bearer_id": 3}
    
    state = client.get("/ues/7").json()
    assert "3" in state["bearers"]
    assert state["bearers"]["3"]["bearer_id"] == 3


def test_end_008_delete_ue_and_clean_up_resources(client):
    client.post("/ues", json={"ue_id": 25})
    
    response = client.delete("/ues/25")
    assert response.status_code == 200
    assert response.json() == {"status": "detached", "ue_id": 25}
    
    get_response = client.get("/ues/25")
    assert get_response.status_code == 400
    assert "UE not found" in get_response.json()["detail"]