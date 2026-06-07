"""Tests for HTTP ingest timeout configuration."""
import pytest
from sdk.config import load_sdk_config
from sdk.dispatcher import _build_http_ingest_handler
from unittest.mock import patch, MagicMock


def test_default_timeout_is_30_seconds(tmp_path):
    """Verify default timeout is 30 seconds (not 2 seconds)."""
    # Use empty temp directory to avoid loading any existing aiguard.yaml
    config_path = tmp_path / "aiguard.yaml"
    config_path.write_text("# Empty config\n")
    
    config = load_sdk_config(root=tmp_path)
    assert config.ingest_timeout_s == 30.0


def test_timeout_configurable_via_aiguard_yaml(tmp_path):
    """Verify timeout can be overridden in aiguard.yaml."""
    config_path = tmp_path / "aiguard.yaml"
    config_path.write_text("""
monitoring:
  ingest_timeout_s: 60.0
""")
    
    config = load_sdk_config(root=tmp_path)
    assert config.ingest_timeout_s == 60.0


def test_http_ingest_handler_uses_timeout():
    """Verify HTTP ingest handler respects timeout parameter."""
    handler = _build_http_ingest_handler("http://test.com/ingest", timeout_s=45.0)
    
    with patch('sdk.dispatcher.urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        handler({"trace_id": "test"})
        
        # Verify urlopen was called with timeout=45.0
        call_args = mock_urlopen.call_args
        assert call_args[1]['timeout'] == 45.0
