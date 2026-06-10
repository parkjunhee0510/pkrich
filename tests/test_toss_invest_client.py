from __future__ import annotations

import unittest

from src.collector.providers.toss_invest_client import TossInvestApiError, TossInvestClient


class _FakeResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> object:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("No fake response queued")
        return self.responses.pop(0)


class TossInvestClientTests(unittest.TestCase):
    def test_issue_token_posts_client_credentials_form(self) -> None:
        session = _FakeSession([
            _FakeResponse({"access_token": "token-123", "token_type": "Bearer", "expires_in": 3600})
        ])
        client = TossInvestClient(
            client_id="client-id",
            client_secret="client-secret",
            session=session,
            now=lambda: 1_000.0,
        )

        token = client.issue_token()

        self.assertEqual(token, "token-123")
        self.assertEqual(session.requests[0]["method"], "POST")
        self.assertEqual(session.requests[0]["url"], "https://openapi.tossinvest.com/oauth2/token")
        self.assertEqual(
            session.requests[0]["data"],
            {
                "grant_type": "client_credentials",
                "client_id": "client-id",
                "client_secret": "client-secret",
            },
        )

    def test_get_prices_uses_bearer_token_and_symbols_query(self) -> None:
        session = _FakeSession([
            _FakeResponse({"result": [{"symbol": "AAPL", "lastPrice": "200", "currency": "USD"}]})
        ])
        client = TossInvestClient(
            client_id="client-id",
            client_secret="client-secret",
            access_token="token-123",
            session=session,
        )

        payload = client.get_prices(["AAPL", "MSFT"])

        self.assertEqual(payload["result"][0]["symbol"], "AAPL")
        self.assertEqual(session.requests[0]["method"], "GET")
        self.assertEqual(session.requests[0]["url"], "https://openapi.tossinvest.com/api/v1/prices")
        self.assertEqual(session.requests[0]["params"], {"symbols": "AAPL,MSFT"})
        self.assertEqual(session.requests[0]["headers"], {"Authorization": "Bearer token-123"})

    def test_request_json_raises_toss_error_on_http_error(self) -> None:
        session = _FakeSession([_FakeResponse({"error": "too_many_requests"}, status_code=429)])
        client = TossInvestClient(
            client_id="client-id",
            client_secret="client-secret",
            access_token="token-123",
            session=session,
        )

        with self.assertRaises(TossInvestApiError) as caught:
            client.get_prices(["AAPL"])

        self.assertIn("429", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
