"""
Test UUID handling and coercion in models
"""

import uuid
from datetime import datetime
from app.core.models import Finding, ScanResult, ScanRequest, ScanStatus, coerce_uuid


def test_coerce_uuid():
    """Test UUID coercion function"""
    # Test with string UUID
    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    result = coerce_uuid(uuid_str)
    assert isinstance(result, uuid.UUID)
    assert str(result) == uuid_str
    
    # Test with UUID object
    uuid_obj = uuid.uuid4()
    result = coerce_uuid(uuid_obj)
    assert isinstance(result, uuid.UUID)
    assert result == uuid_obj
    
    # Test with invalid string
    try:
        coerce_uuid("invalid-uuid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected
    
    # Test with invalid type
    try:
        coerce_uuid(123)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


def test_finding_uuid_coercion():
    """Test Finding model UUID coercion"""
    scan_id_str = "550e8400-e29b-41d4-a716-446655440000"
    
    finding = Finding(
        scan_id=scan_id_str,  # Pass as string
        crack_id="test_scan",
        service="aws",
        pattern_id="AWS_ACCESS_KEY",
        url="http://example.com/test",
        source_url="http://example.com",
        evidence="AKIAIOSFODNN7EXAMPLE",
        evidence_masked="AKIA***AMPLE",
        first_seen=datetime.now(),
        last_seen=datetime.now()
    )
    
    # Check that scan_id was converted to UUID
    assert isinstance(finding.scan_id, uuid.UUID)
    assert str(finding.scan_id) == scan_id_str
    
    # Check that id was generated as UUID
    assert isinstance(finding.id, uuid.UUID)


def test_scan_result_uuid_coercion():
    """Test ScanResult model UUID coercion"""
    scan_id_str = "550e8400-e29b-41d4-a716-446655440000"
    
    config = ScanRequest(
        targets=["example.com"],
        wordlist="paths.txt"
    )
    
    scan_result = ScanResult(
        id=scan_id_str,  # Pass as string
        crack_id="test_scan",
        status=ScanStatus.QUEUED,
        created_at=datetime.now(),
        targets=["example.com"],
        config=config
    )
    
    # Check that id was converted to UUID
    assert isinstance(scan_result.id, uuid.UUID)
    assert str(scan_result.id) == scan_id_str


def test_database_uuid_compatibility():
    """Test that our models work with database operations"""
    # This would be a real database test, but for now just test the model creation
    scan_id = uuid.uuid4()
    
    finding = Finding(
        scan_id=scan_id,
        crack_id="test_scan", 
        service="sendgrid",
        pattern_id="SENDGRID_API_KEY",
        url="http://example.com/config",
        source_url="http://example.com",
        evidence="SG.test-key-12345",
        evidence_masked="SG.***45",
        first_seen=datetime.now(),
        last_seen=datetime.now()
    )
    
    # Should be able to access .hex property (this was the original error)
    assert hasattr(finding.id, 'hex')
    assert hasattr(finding.scan_id, 'hex')
    
    # Test string conversion for database storage
    assert len(str(finding.id)) == 36  # Standard UUID string length
    assert len(str(finding.scan_id)) == 36


if __name__ == "__main__":
    # Run tests manually for quick validation
    test_coerce_uuid()
    test_finding_uuid_coercion()
    test_scan_result_uuid_coercion()
    test_database_uuid_compatibility()
    print("All UUID tests passed!")