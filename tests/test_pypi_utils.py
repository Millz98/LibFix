import pytest
from unittest.mock import patch, MagicMock
import requests
from src.core.pypi_utils import get_package_info_from_pypi
from src.core.cache import get_cache


class TestPyPIUtils:
    def setup_method(self):
        get_cache().clear()

    def test_successful_fetch(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {'info': {'version': '2.28.0'}}
        mock_response.raise_for_status = MagicMock()

        with patch('requests.get', return_value=mock_response):
            result = get_package_info_from_pypi("requests")
            assert result is not None
            assert result['info']['version'] == '2.28.0'

    def test_package_not_found(self):
        with patch('requests.get', side_effect=requests.exceptions.HTTPError("404 Not Found")):
            result = get_package_info_from_pypi("nonexistent-package-xyz")
            assert result is None

    def test_network_error(self):
        with patch('requests.get', side_effect=requests.exceptions.RequestException("Network error")):
            result = get_package_info_from_pypi("requests")
            assert result is None

    def test_cache_hit(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {'info': {'version': '2.28.0'}}
        mock_response.raise_for_status = MagicMock()

        with patch('requests.get', return_value=mock_response) as mock_get:
            result1 = get_package_info_from_pypi("requests")
            result2 = get_package_info_from_pypi("requests")
            assert result1 == result2
            assert mock_get.call_count == 1

    def test_no_cache(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {'info': {'version': '2.28.0'}}
        mock_response.raise_for_status = MagicMock()

        with patch('requests.get', return_value=mock_response) as mock_get:
            get_package_info_from_pypi("requests", use_cache=False)
            get_package_info_from_pypi("requests", use_cache=False)
            assert mock_get.call_count == 2
