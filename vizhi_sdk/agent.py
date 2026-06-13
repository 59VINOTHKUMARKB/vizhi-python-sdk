"""Agent queue helpers for the Vizhi SDK."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client import _decode_json, _error_message, _normalize_messages, _parse_answer
from .exceptions import APIError, AuthenticationError, InvalidResponseError
from .models import ChatAnswer


Message = Mapping[str, str]
Query = str | Message | Iterable[Message]


@dataclass(frozen=True)
class AgentJob:
    id: str
    query_id: str
    agent_id: str
    provider: str
    model: str
    sdk_type: str | None = None
    endpoint: str = "/v1/chat/completions"
    kind: str = "chat"
    engine: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0


@dataclass(frozen=True)
class AgentCompletion:
    job_id: str
    status: str = "completed"
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    completed_at: str = ""


class AgentQueueProvider:
    """Client for submitting work to a specific Vizhi agent queue."""

    def __init__(
        self,
        agent_cid: str,
        agent_token: str,
        model: str | None,
        *,
        base_url: str | None = None,
        timeout: float = 60.0,
        call_sdk: str | None = None,
    ) -> None:
        if not agent_cid or not agent_cid.strip():
            raise ValueError("agent_cid must not be empty")
        if not agent_token or not agent_token.strip():
            raise ValueError("agent_token must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        resolved_base_url = base_url or os.environ.get("VIZHI_BASE_URL")
        if not resolved_base_url or not resolved_base_url.strip():
            raise ValueError("base_url must not be empty")

        self.agent_cid = agent_cid.strip()
        self.agent_token = agent_token.strip()
        self.model = model.strip() if model else None
        self.base_url = resolved_base_url.strip().rstrip("/")
        self.timeout = timeout
        self.call_sdk = call_sdk

    def chat(
        self,
        queries: Query,
        *,
        temperature: float = 1.0,
        max_tokens: int | None = None,
    ) -> ChatAnswer:
        payload: dict[str, Any] = {
            "messages": _normalize_messages(queries),
            "temperature": temperature,
        }
        if self.model is not None:
            payload["model"] = self.model
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self.call_sdk is not None:
            payload["call_sdk"] = self.call_sdk

        data = self._post("/v1/chat/completions", payload)
        return _parse_answer(data)

    def _post(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return _decode_json(response.read())
        except HTTPError as exc:
            response_data = _decode_json(exc.read(), allow_invalid=True)
            message = _error_message(response_data, exc.reason)
            if exc.code in (401, 403):
                raise AuthenticationError(message) from exc
            raise APIError(
                message, status_code=exc.code, response=response_data
            ) from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise APIError(f"Could not connect to Vizhi backend: {reason}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "X-Agent-CID": self.agent_cid,
            "X-Agent-Token": self.agent_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "vizhi-python-sdk/0.1.0",
        }


class AgentConnection:
    """Client for the on-site agent daemon to register, poll, and submit jobs."""

    def __init__(
        self,
        agent_cid: str,
        agent_token: str,
        *,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not agent_cid or not agent_cid.strip():
            raise ValueError("agent_cid must not be empty")
        if not agent_token or not agent_token.strip():
            raise ValueError("agent_token must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        resolved_base_url = base_url or os.environ.get("VIZHI_BASE_URL")
        if not resolved_base_url or not resolved_base_url.strip():
            raise ValueError("base_url must not be empty")

        self.agent_cid = agent_cid.strip()
        self.agent_token = agent_token.strip()
        self.base_url = resolved_base_url.strip().rstrip("/")
        self.timeout = timeout

    def register(
        self,
        *,
        device_name: str = "",
        os_name: str = "",
        agent_version: str = "",
        available_engines: list[str] | None = None,
    ) -> Mapping[str, Any]:
        payload = {
            "agent_id": self.agent_cid,
            "device_name": device_name,
            "os_name": os_name,
            "agent_version": agent_version,
            "available_engines": available_engines or [],
        }
        return self._request("POST", "/agents/register", payload)

    def heartbeat(
        self,
        *,
        device_name: str = "",
        os_name: str = "",
        agent_version: str = "",
        available_engines: list[str] | None = None,
        status: str = "online",
        active_job_id: str = "",
        active_engine: str = "",
        queue_depth: int = 0,
    ) -> Mapping[str, Any]:
        payload = {
            "agent_id": self.agent_cid,
            "device_name": device_name,
            "os_name": os_name,
            "agent_version": agent_version,
            "available_engines": available_engines or [],
            "status": status,
            "active_job_id": active_job_id,
            "active_engine": active_engine,
            "queue_depth": queue_depth,
        }
        return self._request("POST", "/agents/heartbeat", payload)

    def next_job(self) -> AgentJob | None:
        request = Request(
            f"{self.base_url}/jobs/next",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                data = _decode_json(response.read())
        except HTTPError as exc:
            if exc.code == 204:
                return None
            response_data = _decode_json(exc.read(), allow_invalid=True)
            message = _error_message(response_data, exc.reason)
            if exc.code in (401, 403):
                raise AuthenticationError(message) from exc
            raise APIError(
                message, status_code=exc.code, response=response_data
            ) from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise APIError(f"Could not connect to Vizhi backend: {reason}") from exc
        return AgentJob(
            id=str(data["id"]),
            query_id=str(data["query_id"]),
            agent_id=str(data.get("agent_id", self.agent_cid)),
            provider=str(data["provider"]),
            model=str(data["model"]),
            sdk_type=data.get("sdk_type"),
            endpoint=str(data.get("endpoint", "/v1/chat/completions")),
            kind=str(data.get("kind", "chat")),
            engine=str(data.get("engine", "")),
            input=dict(data.get("input", {})),
            stream=bool(data.get("stream", False)),
            metadata=dict(data.get("metadata", {})),
            attempt_count=int(data.get("attempt_count", 0)),
        )

    def submit(self, completion: AgentCompletion) -> Mapping[str, Any]:
        return self._request("POST", "/jobs/submit", completion.__dict__)

    def _request(self, method: str, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return _decode_json(response.read())
        except HTTPError as exc:
            response_data = _decode_json(exc.read(), allow_invalid=True)
            message = _error_message(response_data, exc.reason)
            if exc.code in (401, 403):
                raise AuthenticationError(message) from exc
            raise APIError(
                message, status_code=exc.code, response=response_data
            ) from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise APIError(f"Could not connect to Vizhi backend: {reason}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "X-Agent-CID": self.agent_cid,
            "X-Agent-Token": self.agent_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "vizhi-python-sdk/0.1.0",
        }


def provide_agent_model(
    agent_cid: str,
    agent_token: str,
    model_name: str | None = None,
    *,
    base_url: str | None = None,
    timeout: float = 60.0,
    call_sdk: str | None = None,
) -> AgentQueueProvider:
    """Create a client bound to a specific on-site agent queue."""
    return AgentQueueProvider(
        agent_cid,
        agent_token,
        model_name,
        base_url=base_url,
        timeout=timeout,
        call_sdk=call_sdk,
    )
