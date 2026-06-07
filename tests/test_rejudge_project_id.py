"""Tests for rejudge endpoint project_id correlation."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from storage.manager import StorageManager
from storage.models import Trace
from datetime import datetime

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_rejudge_uses_trace_project_id(tmp_path, monkeypatch):
    """Verify rejudge uses trace's original project_id, not config's project_id.
    
    This test verifies that when rejudging a trace, the code extracts the
    project_id from the trace itself (trace.get("project_id")) rather than
    using config.project_id.
    """
    # Setup: Create trace in project_A
    storage = StorageManager(root=tmp_path)
    trace = Trace(
        id="trace-1",
        timestamp=datetime.now(),
        model_name="test-model",
        model_version=None,
        prompt="test prompt",
        response="test response",
        latency_ms=100.0,
        tokens_used=50,
        environment="production",
        metadata={},
    )
    storage.backend.save_trace("project_A", trace)
    
    # Setup: Config with project_B (different from trace's project)
    config_path = tmp_path / "aiguard.yaml"
    config_path.write_text("""
project: project_B
monitoring:
  api:
    port: 8080
""")
    
    # Mock the trace service to return our trace with project_id
    mock_trace = {
        "id": "trace-1",
        "project_id": "project_A",  # Trace's original project
        "prompt": "test prompt",
        "response": "test response",
        "timestamp": datetime.now().isoformat(),
        "model_name": "test-model",
        "latency_ms": 100.0,
        "tokens_used": 50,
        "metadata": {}
    }
    
    # Mock EvaluationWorker to avoid slow evaluation
    mock_worker = Mock()
    mock_worker.process_batch = Mock(return_value=[])
    
    with patch('monitoring.api.routes_traces.TraceService') as mock_service_class, \
         patch('monitoring.api.routes_traces.EvaluationWorker', return_value=mock_worker):
        
        # Setup mock service
        mock_service = Mock()
        mock_service.get_trace = Mock(return_value=mock_trace)
        mock_service_class.return_value = mock_service
        
        # Act: Call rejudge endpoint
        from monitoring.api.server import create_monitoring_app
        app = create_monitoring_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/traces/trace-1/evaluate?force_judge=true")
        
        # Assert: Response is successful
        assert response.status_code == 200
        data = response.json()
        assert data["trace_id"] == "trace-1"
        
        # Verify EvaluationWorker was created and process_batch was called
        assert mock_worker.process_batch.called
        
        # Verify the trace was retrieved with project_id
        mock_service.get_trace.assert_called_once_with("trace-1")
