import pytest
from epc.models import (
    StartTrafficRequest,
    AttachUERequest,
    AddBearerRequest,
    UEState,
    BearerConfig,
)


# ============================================
# StartTrafficRequest - konwersje jednostek
# ============================================

def test_start_traffic_request_mbps_conversion():
    """Mbps → bps"""
    req = StartTrafficRequest(protocol="tcp", Mbps=2.5)
    assert req.target_bps() == 2_500_000


def test_start_traffic_request_kbps_conversion():
    """kbps → bps"""
    req = StartTrafficRequest(protocol="udp", kbps=500)
    assert req.target_bps() == 500_000


def test_start_traffic_request_bps_conversion():
    """bps bez zmian"""
    req = StartTrafficRequest(protocol="tcp", bps=1_000_000)
    assert req.target_bps() == 1_000_000


def test_start_traffic_request_multiple_throughputs_raises_error():
    """Podanie Mbps i kbps naraz -> błąd"""
    with pytest.raises(ValueError, match="Provide exactly one throughput value"):
        StartTrafficRequest(protocol="tcp", Mbps=1, kbps=100)


def test_start_traffic_request_no_throughput_raises_error():
    """Brak przepustowości -> błąd"""
    with pytest.raises(ValueError, match="Provide exactly one throughput value"):
        StartTrafficRequest(protocol="tcp")


def test_start_traffic_request_invalid_protocol_raises_error():
    """Protokół inny niż tcp/udp -> błąd"""
    with pytest.raises(ValueError):
        StartTrafficRequest(protocol="invalid", Mbps=1)


# ============================================
# AttachUERequest - zakres ID
# ============================================

def test_attach_ue_request_invalid_id_range():
    """UE ID poza zakresem 1-100 -> błąd"""
    # ID za niskie
    with pytest.raises(ValueError):
        AttachUERequest(ue_id=0)
    
    # ID za wysokie
    with pytest.raises(ValueError):
        AttachUERequest(ue_id=101)


# ============================================
# AddBearerRequest - zakres ID
# ============================================

def test_add_bearer_request_invalid_id_range():
    """Bearer ID poza zakresem 1-9 -> błąd"""
    # ID za niskie
    with pytest.raises(ValueError):
        AddBearerRequest(bearer_id=0)
    
    # ID za wysokie
    with pytest.raises(ValueError):
        AddBearerRequest(bearer_id=10)


# ============================================
# UEState - domyślne wartości
# ============================================

def test_ue_state_init_defaults():
    """Puste bearers i stats stają się pustymi dictami"""
    state = UEState(ue_id=1)
    assert state.ue_id == 1
    assert state.bearers == {}
    assert state.stats == {}


# ============================================
# BearerConfig - walidacja protokołu
# ============================================

def test_bearer_config_protocol_validation():
    """Tylko tcp, udp lub null są dozwolone"""
    # Dozwolone wartości
    BearerConfig(bearer_id=1, protocol="tcp")
    BearerConfig(bearer_id=1, protocol="udp")
    BearerConfig(bearer_id=1, protocol=None)
    
    # Niedozwolona wartość
    with pytest.raises(ValueError):
        BearerConfig(bearer_id=1, protocol="invalid")