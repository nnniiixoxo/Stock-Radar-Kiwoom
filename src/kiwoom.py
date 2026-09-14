from __future__ import annotations

import os
import time
from typing import Any

import requests


class KiwoomError(RuntimeError):
    pass


class KiwoomClient:
    """Read-only Kiwoom REST client. This project intentionally has no order API."""

    PATHS = {
        "ka10020": "/api/dostk/rkinfo",
        "ka10023": "/api/dostk/rkinfo",
        "ka10029": "/api/dostk/rkinfo",
        "ka10032": "/api/dostk/rkinfo",
        "ka10046": "/api/dostk/mrkcond",
        "ka10065": "/api/dostk/mrkcond",
        "ka90009": "/api/dostk/rkinfo",
        "ka10099": "/api/dostk/stkinfo",
        "ka20003": "/api/dostk/sect",
    }

    def __init__(self, app_key: str | None = None, secret_key: str | None = None,
                 mode: str | None = None, session: requests.Session | None = None):
        self.app_key = app_key or os.getenv("KIWOOM_APP_KEY", "")
        self.secret_key = secret_key or os.getenv("KIWOOM_SECRET_KEY", "")
        self.mode = (mode or os.getenv("KIWOOM_MODE", "real")).lower()
        self.base_url = "https://mockapi.kiwoom.com" if self.mode == "mock" else "https://api.kiwoom.com"
        self.session = session or requests.Session()
        self.token = ""
        self.token_expires_at = 0.0

    def authenticate(self) -> str:
        if not self.app_key or not self.secret_key:
            raise KiwoomError("KIWOOM_APP_KEY와 KIWOOM_SECRET_KEY가 설정되지 않았습니다.")
        response = self.session.post(
            self.base_url + "/oauth2/token",
            json={"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.secret_key},
            headers={"Content-Type": "application/json;charset=UTF-8"}, timeout=15,
        )
        data = self._json(response)
        token = data.get("token")
        if not token:
            raise KiwoomError(f"접근토큰 발급 실패: {self._message(data)}")
        self.token = str(token)
        self.token_expires_at = time.time() + 3600
        return self.token

    def call(self, api_id: str, body: dict[str, Any], *, retries: int = 2) -> dict[str, Any]:
        if api_id not in self.PATHS:
            raise KiwoomError(f"허용되지 않은 조회 API: {api_id}")
        if not self.token or time.time() >= self.token_expires_at - 60:
            self.authenticate()
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = self.session.post(
                    self.base_url + self.PATHS[api_id], json=body,
                    headers={
                        "Content-Type": "application/json;charset=UTF-8",
                        "authorization": f"Bearer {self.token}",
                        "api-id": api_id,
                        "cont-yn": "N",
                        "next-key": "",
                    }, timeout=20,
                )
                data = self._json(response)
                return_code = str(data.get("return_code", data.get("return-code", "0")))
                if not response.ok or return_code not in {"0", "", "None"}:
                    raise KiwoomError(f"{api_id} 조회 실패: {self._message(data)}")
                return data
            except (requests.RequestException, KiwoomError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise KiwoomError(str(last_error))

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise KiwoomError(f"JSON이 아닌 응답(HTTP {response.status_code})") from exc
        if not isinstance(data, dict):
            raise KiwoomError("예상하지 못한 API 응답 형식")
        return data

    @staticmethod
    def _message(data: dict[str, Any]) -> str:
        return str(data.get("return_msg") or data.get("return-msg") or data.get("message") or data)

