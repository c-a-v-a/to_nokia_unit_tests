import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from epc.api import get_repo
from epc.db import EPCRepository
from epc.traffic import TrafficGeneratorManager
from epc.models import UEState, BearerConfig, ThroughputStats


@pytest.fixture
def mock_repo():
    return MagicMock(spec=EPCRepository)


@pytest.fixture
def mock_tm():
    return MagicMock(spec=TrafficGeneratorManager)


@pytest.fixture
def client(mock_repo, mock_tm):
    app.dependency_overrides[get_repo] = lambda: mock_repo
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_repo, None)


# --- UE ATTACH / DETACH TESTS ---

def test_attach_ue_returns_200_on_success(client, mock_repo):
    mock_repo.attach_ue.return_value = None
    response = client.post("/ues", json={"ue_id": 1})
    assert response.status_code == 200
    assert response.json() == {"status": "attached", "ue_id": 1}
    mock_repo.attach_ue.assert_called_once_with(1)


def test_attach_ue_returns_400_on_repository_error(client, mock_repo):
    mock_repo.attach_ue.side_effect = ValueError("UE already attached")
    response = client.post("/ues", json={"ue_id": 1})
    assert response.status_code == 400
    assert "UE already attached" in response.json()["detail"]
    mock_repo.attach_ue.assert_called_once_with(1)


def test_detach_ue_returns_200_on_success(client, mock_repo):
    mock_repo.detach_ue.return_value = None
    response = client.delete("/ues/1")
    assert response.status_code == 200
    assert response.json() == {"status": "detached", "ue_id": 1}
    mock_repo.detach_ue.assert_called_once_with(1)


def test_detach_ue_returns_400_on_not_found(client, mock_repo):
    mock_repo.detach_ue.side_effect = ValueError("UE not found")
    response = client.delete("/ues/1")
    assert response.status_code == 400
    assert "UE not found" in response.json()["detail"]
    mock_repo.detach_ue.assert_called_once_with(1)


# --- BEARER MANAGEMENT TESTS ---

def test_add_bearer_returns_200_on_success(client, mock_repo):
    mock_repo.add_bearer.return_value = None
    response = client.post("/ues/1/bearers", json={"bearer_id": 2})
    assert response.status_code == 200
    assert response.json() == {"status": "bearer_added", "ue_id": 1, "bearer_id": 2}
    mock_repo.add_bearer.assert_called_once_with(1, 2)


def test_add_bearer_returns_400_on_duplicate(client, mock_repo):
    mock_repo.add_bearer.side_effect = ValueError("Bearer already exists")
    response = client.post("/ues/1/bearers", json={"bearer_id": 2})
    assert response.status_code == 400
    assert "Bearer already exists" in response.json()["detail"]
    mock_repo.add_bearer.assert_called_once_with(1, 2)


def test_delete_bearer_stops_traffic_if_running(client, mock_repo, mock_tm):
    state = UEState(ue_id=1)
    state.bearers[2] = BearerConfig(bearer_id=2)
    mock_repo.get_ue.return_value = state
    mock_tm.is_running.return_value = True
    
    response = client.delete("/ues/1/bearers/2")
    assert response.status_code == 200
    assert response.json() == {"status": "bearer_deleted", "ue_id": 1, "bearer_id": 2}
    
    mock_tm.is_running.assert_called_once_with(1, 2)
    mock_tm.stop.assert_called_once_with(1, 2)
    mock_repo.delete_bearer.assert_called_once_with(1, 2)


def test_delete_bearer_returns_400_if_bearer_not_found(client, mock_repo):
    state = UEState(ue_id=1)
    mock_repo.get_ue.return_value = state
    
    response = client.delete("/ues/1/bearers/2")
    assert response.status_code == 400
    assert "Bearer not found" in response.json()["detail"]


# --- TRAFFIC CONTROL TESTS ---

def test_start_traffic_returns_200_on_success(client, mock_repo, mock_tm):
    state = UEState(ue_id=1)
    state.bearers[2] = BearerConfig(bearer_id=2)
    mock_repo.get_ue.return_value = state
    mock_repo.update_bearer.return_value = None
    mock_repo.update_stats.return_value = None
    mock_tm.start.return_value = None
    
    response = client.post("/ues/1/bearers/2/traffic", json={"protocol": "tcp", "Mbps": 2.5})
    assert response.status_code == 200
    assert response.json() == {
        "status": "traffic_started",
        "ue_id": 1,
        "bearer_id": 2,
        "target_bps": 2500000,
    }
    
    mock_repo.update_bearer.assert_called_once()
    mock_repo.update_stats.assert_called_once()
    mock_tm.start.assert_called_once()


def test_start_traffic_returns_400_if_bearer_not_found(client, mock_repo):
    state = UEState(ue_id=1)
    mock_repo.get_ue.return_value = state
    
    response = client.post("/ues/1/bearers/2/traffic", json={"protocol": "tcp", "Mbps": 2.5})
    assert response.status_code == 400
    assert "Bearer not found" in response.json()["detail"]


def test_start_traffic_returns_400_if_already_running(client, mock_repo, mock_tm):
    state = UEState(ue_id=1)
    state.bearers[2] = BearerConfig(bearer_id=2)
    mock_repo.get_ue.return_value = state
    mock_repo.update_bearer.return_value = None
    mock_repo.update_stats.return_value = None
    mock_tm.start.side_effect = ValueError("Traffic already running")
    
    response = client.post("/ues/1/bearers/2/traffic", json={"protocol": "tcp", "Mbps": 2.5})
    assert response.status_code == 400
    assert "Traffic already running" in response.json()["detail"]


def test_stop_traffic_returns_200_on_success(client, mock_repo, mock_tm):
    state = UEState(ue_id=1)
    state.bearers[2] = BearerConfig(bearer_id=2, protocol="tcp", target_bps=1000000, active=True)
    mock_repo.get_ue.return_value = state
    mock_repo.update_bearer.return_value = None
    mock_tm.stop.return_value = None
    
    response = client.delete("/ues/1/bearers/2/traffic")
    assert response.status_code == 200
    assert response.json() == {"status": "traffic_stopped", "ue_id": 1, "bearer_id": 2}
    
    mock_tm.stop.assert_called_once_with(1, 2)
    mock_repo.update_bearer.assert_called_once()


def test_stop_traffic_deactivates_bearer(client, mock_repo, mock_tm):
    state = UEState(ue_id=1)
    state.bearers[2] = BearerConfig(bearer_id=2, protocol="tcp", target_bps=1000000, active=True)
    mock_repo.get_ue.return_value = state
    mock_repo.update_bearer.return_value = None
    
    response = client.delete("/ues/1/bearers/2/traffic")
    assert response.status_code == 200
    
    called_bearer = mock_repo.update_bearer.call_args[0][1]
    assert called_bearer.active is False


def test_get_traffic_stats_returns_0_when_no_stats(client, mock_repo):
    state = UEState(ue_id=1)
    mock_repo.get_ue.return_value = state
    
    response = client.get("/ues/1/bearers/2/traffic")
    assert response.status_code == 200
    assert response.json() == {
        "ue_id": 1,
        "bearer_id": 2,
        "protocol": None,
        "target_bps": None,
        "tx_bps": 0,
        "rx_bps": 0,
        "duration": 0.0,
    }


# --- STATISTICS & GLOBAL MANAGEMENT TESTS ---

def test_get_ues_stats_without_ue_id_returns_all(client, mock_repo, mock_tm):
    mock_repo.list_ues.return_value = [1, 2]
    
    state1 = UEState(ue_id=1)
    state1.stats[9] = ThroughputStats(
        bearer_id=9, ue_id=1, bytes_tx=1000, bytes_rx=1000, start_ts=100, last_update_ts=200
    )
    
    state2 = UEState(ue_id=2)
    state2.stats[9] = ThroughputStats(
        bearer_id=9, ue_id=2, bytes_tx=2000, bytes_rx=2000, start_ts=100, last_update_ts=200
    )
    
    def mock_get_ue(ue_id):
        if ue_id == 1:
            return state1
        if ue_id == 2:
            return state2
        raise ValueError("UE not found")
        
    mock_repo.get_ue.side_effect = mock_get_ue
    mock_tm.is_running.return_value = False
    
    response = client.get("/ues/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "all"
    assert data["ue_count"] == 2
    assert data["bearer_count"] == 2
    assert data["total_tx_bps"] == 240
    assert data["total_rx_bps"] == 240


def test_get_ues_stats_with_ue_id_filters(client, mock_repo, mock_tm):
    mock_repo.ue_exists.return_value = True
    
    state = UEState(ue_id=1)
    state.stats[9] = ThroughputStats(
        bearer_id=9, ue_id=1, bytes_tx=1000, bytes_rx=1000, start_ts=100, last_update_ts=200
    )
    mock_repo.get_ue.return_value = state
    mock_tm.is_running.return_value = False
    
    response = client.get("/ues/stats?ue_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "ue:1"
    assert data["ue_count"] == 1
    assert data["bearer_count"] == 1
    assert data["total_tx_bps"] == 80


def test_get_ues_stats_with_include_details(client, mock_repo, mock_tm):
    mock_repo.list_ues.return_value = [1]
    state = UEState(ue_id=1)
    state.stats[9] = ThroughputStats(
        bearer_id=9, ue_id=1, bytes_tx=1000, bytes_rx=1000, start_ts=100, last_update_ts=200
    )
    mock_repo.get_ue.return_value = state
    mock_tm.is_running.return_value = False
    
    response = client.get("/ues/stats?include_details=true")
    assert response.status_code == 200
    data = response.json()
    assert data["details"] == {"1": {"9": 80}}


def test_get_ues_stats_with_nonexistent_ue_returns_400(client, mock_repo):
    mock_repo.ue_exists.return_value = False
    
    response = client.get("/ues/stats?ue_id=99")
    assert response.status_code == 400
    assert "UE not found" in response.json()["detail"]


def test_reset_stops_all_traffic_and_clears_data(client, mock_repo, mock_tm):
    mock_tm.stop_all.return_value = None
    mock_repo.reset_all.return_value = None
    
    response = client.post("/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}
    
    mock_tm.stop_all.assert_called_once()
    mock_repo.reset_all.assert_called_once()


# --- ADDITIONAL COMPLEMENTARY TESTS ---

def test_get_ue_state_success(client, mock_repo):
    state = UEState(ue_id=1)
    state.bearers[9] = BearerConfig(bearer_id=9)
    mock_repo.get_ue.return_value = state
    
    response = client.get("/ues/1")
    assert response.status_code == 200
    data = response.json()
    assert data["ue_id"] == 1
    assert "9" in data["bearers"]


def test_get_ue_state_returns_400_on_not_found(client, mock_repo):
    mock_repo.get_ue.side_effect = ValueError("UE not found")
    
    response = client.get("/ues/1")
    assert response.status_code == 400
    assert "UE not found" in response.json()["detail"]


def test_list_ues_returns_all(client, mock_repo):
    mock_repo.list_ues.return_value = [1, 2, 3]
    
    response = client.get("/ues")
    assert response.status_code == 200
    assert response.json() == {"ues": [1, 2, 3]}
