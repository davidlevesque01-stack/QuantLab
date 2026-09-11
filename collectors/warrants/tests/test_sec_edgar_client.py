import json
from unittest.mock import MagicMock, patch

from collectors.warrants.src.sec_edgar_client import fetch_json


def test_fetch_json_sets_user_agent_header_and_parses_response():
    response_body = json.dumps({"ok": True}).encode("utf-8")

    mock_response = MagicMock()
    mock_response.read.return_value = response_body
    mock_response.__enter__.return_value = mock_response

    with patch(
        "collectors.warrants.src.sec_edgar_client.urlopen",
        return_value=mock_response,
    ) as mocked_urlopen:

        result = fetch_json(
            "https://example.test/data.json",
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=7,
        )

    assert result == {"ok": True}

    called_request = mocked_urlopen.call_args.args[0]
    assert called_request.get_header("User-agent") == "QuantLab test contact@example.com"
    assert mocked_urlopen.call_args.kwargs["timeout"] == 7
