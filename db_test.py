import pytest
from epc.db import EPCRepository
from epc.models import BearerConfig, ThroughputStats, UEState


@pytest.fixture
def test_repo(tmp_path):
    """
    Fixture that creates a new, isolated EPCRepository instance 
    in a temporary directory for each test to ensure a clean database state.
    """
    db_file = tmp_path / "test_epc.db"
    return EPCRepository(db_path=str(db_file))


# --- ATTACH / DETACH / EXISTS TESTS ---

def test_attach_ue_success(test_repo: EPCRepository):
    """Adds a UE and verifies that the default bearer 9 is automatically created."""
    test_repo.attach_ue(ue_id=1)
    
    assert test_repo.ue_exists(ue_id=1) is True
    ue_state = test_repo.get_ue(ue_id=1)
    assert 9 in ue_state.bearers
    assert ue_state.bearers[9].bearer_id == 9


def test_attach_ue_duplicate_raises_error(test_repo: EPCRepository):
    """Attempting to attach the same UE for the second time must raise a ValueError."""
    test_repo.attach_ue(ue_id=5)
    
    with pytest.raises(ValueError, match="UE already attached"):
        test_repo.attach_ue(ue_id=5)


def test_detach_ue_success(test_repo: EPCRepository):
    """Successfully removes (deregisters) an existing UE from the database."""
    test_repo.attach_ue(ue_id=10)
    assert test_repo.ue_exists(ue_id=10) is True
    
    test_repo.detach_ue(ue_id=10)
    assert test_repo.ue_exists(ue_id=10) is False


def test_detach_nonexistent_ue_raises_error(test_repo: EPCRepository):
    """Attempting to detach a non-existent UE must raise a ValueError."""
    with pytest.raises(ValueError, match="UE not found"):
        test_repo.detach_ue(ue_id=99)


def test_ue_exists(test_repo: EPCRepository):
    """Precisely verifies the behavior of the ue_exists method."""
    assert test_repo.ue_exists(ue_id=20) is False
    
    test_repo.attach_ue(ue_id=20)
    assert test_repo.ue_exists(ue_id=20) is True


# --- GET / LIST TESTS ---

def test_get_ue_returns_correct_state(test_repo: EPCRepository):
    """Retrieves the full state of a saved UE and validates its structure."""
    test_repo.attach_ue(ue_id=7)
    
    ue_state = test_repo.get_ue(ue_id=7)
    assert ue_state.ue_id == 7
    assert isinstance(ue_state.bearers, dict)
    assert isinstance(ue_state.stats, dict)


def test_get_nonexistent_ue_raises_error(test_repo: EPCRepository):
    """Attempting to fetch data for a non-existent UE raises a ValueError."""
    with pytest.raises(ValueError, match="UE not found"):
        test_repo.get_ue(ue_id=99)


def test_list_ues(test_repo: EPCRepository):
    """Returns a sorted list of IDs for all registered UEs (verifies ORDER BY clause)."""
    assert list(test_repo.list_ues()) == []
    
    test_repo.attach_ue(ue_id=3)
    test_repo.attach_ue(ue_id=1)
    test_repo.attach_ue(ue_id=2)
    
    # The method returns a generator, so we cast to a list and verify the sorting order
    assert list(test_repo.list_ues()) == [1, 2, 3]


# --- BEARER MANAGEMENT TESTS ---

def test_add_bearer_success(test_repo: EPCRepository):
    """Adds a new custom bearer to an existing UE."""
    test_repo.attach_ue(ue_id=1)
    test_repo.add_bearer(ue_id=1, bearer_id=5)
    
    ue_state = test_repo.get_ue(ue_id=1)
    assert 5 in ue_state.bearers
    assert ue_state.bearers[5].bearer_id == 5


def test_add_bearer_duplicate_raises_error(test_repo: EPCRepository):
    """Attempting to add a bearer with an already existing ID raises an error."""
    test_repo.attach_ue(ue_id=1)
    test_repo.add_bearer(ue_id=1, bearer_id=4)
    
    with pytest.raises(ValueError, match="Bearer already exists"):
        test_repo.add_bearer(ue_id=1, bearer_id=4)


def test_add_bearer_to_nonexistent_ue_raises_error(test_repo: EPCRepository):
    """Attempting to add a bearer to a UE that does not exist in the DB raises an error."""
    with pytest.raises(ValueError, match="UE not found"):
        test_repo.add_bearer(ue_id=99, bearer_id=2)


def test_delete_bearer_success(test_repo: EPCRepository):
    """Successfully deletes an existing custom bearer."""
    test_repo.attach_ue(ue_id=1)
    test_repo.add_bearer(ue_id=1, bearer_id=3)
    
    test_repo.delete_bearer(ue_id=1, bearer_id=3)
    ue_state = test_repo.get_ue(ue_id=1)
    assert 3 not in ue_state.bearers


def test_delete_bearer_9_forbidden(test_repo: EPCRepository):
    """Business rule: The default bearer 9 is protected and cannot be removed."""
    test_repo.attach_ue(ue_id=1)
    
    with pytest.raises(ValueError, match="Cannot remove default bearer"):
        test_repo.delete_bearer(ue_id=1, bearer_id=9)


def test_delete_nonexistent_bearer_raises_error(test_repo: EPCRepository):
    """Attempting to remove a bearer that does not exist raises a ValueError."""
    test_repo.attach_ue(ue_id=1)
    
    with pytest.raises(ValueError, match="Bearer not found"):
        test_repo.delete_bearer(ue_id=1, bearer_id=2)


def test_update_bearer_success(test_repo: EPCRepository):
    """Updates the configuration parameters of a bearer (protocol, target_bps, active)."""
    test_repo.attach_ue(ue_id=1)
    
    # Create a modified configuration for bearer 9
    updated_bearer = BearerConfig(bearer_id=9, protocol="tcp", target_bps=1500000, active=True)
    test_repo.update_bearer(ue_id=1, bearer=updated_bearer)
    
    ue_state = test_repo.get_ue(ue_id=1)
    assert ue_state.bearers[9].protocol == "tcp"
    assert ue_state.bearers[9].target_bps == 1500000
    assert ue_state.bearers[9].active is True


# --- STATISTICS AND RESET TESTS ---

def test_update_stats_success(test_repo: EPCRepository):
    """Updates the ThroughputStats object assigned to a specific bearer."""
    test_repo.attach_ue(ue_id=1)
    
    new_stats = ThroughputStats(
        bearer_id=9,
        ue_id=1,
        bytes_tx=5000,
        bytes_rx=12000,
        protocol="udp",
        target_bps=500000
    )
    test_repo.update_stats(ue_id=1, stats=new_stats)
    
    ue_state = test_repo.get_ue(ue_id=1)
    assert 9 in ue_state.stats
    assert ue_state.stats[9].bytes_tx == 5000
    assert ue_state.stats[9].bytes_rx == 12000
    assert ue_state.stats[9].protocol == "udp"


def test_reset_all(test_repo: EPCRepository):
    """Removes absolutely all UEs and their states from the database."""
    test_repo.attach_ue(ue_id=1)
    test_repo.attach_ue(ue_id=2)
    assert len(list(test_repo.list_ues())) == 2
    
    test_repo.reset_all()
    assert len(list(test_repo.list_ues())) == 0


def test_save_ue_direct(test_repo: EPCRepository):
    """Tests the direct saving and deserialization of UEState objects (internal repo mechanism)."""
    state = UEState(ue_id=50)
    state.bearers[2] = BearerConfig(bearer_id=2, protocol="udp", active=False)
    
    test_repo.save_ue(state)
    assert test_repo.ue_exists(50) is True
    
    fetched = test_repo.get_ue(50)
    assert 2 in fetched.bearers
    assert fetched.bearers[2].protocol == "udp"