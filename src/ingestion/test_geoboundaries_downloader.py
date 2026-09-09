from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from requests import HTTPError

from ingestion.geoboundaries_downloader import GeoBoundariesDownloader


class GeoBoundariesDownloaderTests(SimpleTestCase):
    ### Verify that the downloader configures retries for transient HTTP failures.
    def test_configures_transient_http_retries(self):
        downloader = GeoBoundariesDownloader()

        adapter = downloader.session.get_adapter(
            "https://example.invalid/"
        )

        retry = adapter.max_retries

        self.assertEqual(
            retry.total,
            downloader.MAX_RETRIES,
        )

        self.assertEqual(
            retry.connect,
            downloader.MAX_RETRIES,
        )

        self.assertEqual(
            retry.read,
            downloader.MAX_RETRIES,
        )

        self.assertEqual(
            retry.status,
            downloader.MAX_RETRIES,
        )

        self.assertEqual(
            retry.backoff_factor,
            downloader.RETRY_BACKOFF_FACTOR,
        )

        self.assertEqual(
            set(retry.status_forcelist),
            downloader.TRANSIENT_STATUS_CODES,
        )

        self.assertEqual(
            set(retry.allowed_methods),
            {"GET"},
        )

    ### Verify that a successful HTTP response is returned unchanged.
    @patch("ingestion.geoboundaries_downloader.requests.Session.get")
    def test_returns_successful_response(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None

        mock_get.return_value = response

        downloader = GeoBoundariesDownloader()

        result = downloader._get(
            "https://example.invalid/test"
        )

        self.assertIs(
            result,
            response,
        )

        mock_get.assert_called_once()

    ### Verify that permanent HTTP failures are propagated to the caller.
    @patch("ingestion.geoboundaries_downloader.requests.Session.get")
    def test_propagates_permanent_http_failure(self, mock_get):
        response = Mock()
        response.status_code = 404
        response.raise_for_status.side_effect = HTTPError(
            "404 Client Error"
        )

        mock_get.return_value = response

        downloader = GeoBoundariesDownloader()

        with self.assertRaises(HTTPError):
            downloader._get(
                "https://example.invalid/test"
            )

        mock_get.assert_called_once()