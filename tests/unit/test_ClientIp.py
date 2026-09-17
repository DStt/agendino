from starlette.requests import Request

from app.client_ip import get_client_ip


def _request(headers=None, client=("1.2.3.4", 1234)):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": raw,
        "client": client,
    }
    return Request(scope)


class TestGetClientIp:
    def test_uses_socket_address_by_default(self, monkeypatch):
        monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
        req = _request(headers={"x-forwarded-for": "9.9.9.9"})
        assert get_client_ip(req) == "1.2.3.4"

    def test_honours_forwarded_for_when_trusted(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        req = _request(headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
        assert get_client_ip(req) == "9.9.9.9"

    def test_falls_back_to_real_ip(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        req = _request(headers={"x-real-ip": "8.8.8.8"})
        assert get_client_ip(req) == "8.8.8.8"

    def test_falls_back_to_socket_when_no_headers(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        assert get_client_ip(_request()) == "1.2.3.4"

    def test_missing_client_is_unknown(self, monkeypatch):
        monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
        assert get_client_ip(_request(client=None)) == "unknown"

    def test_trust_flag_accepts_yes(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "yes")
        req = _request(headers={"x-forwarded-for": "9.9.9.9"})
        assert get_client_ip(req) == "9.9.9.9"
