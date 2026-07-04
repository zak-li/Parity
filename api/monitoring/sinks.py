from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from core.models.monitoring import Alert

logger = logging.getLogger(__name__)


class AlertSink(Protocol):
    def dispatch(self, subject: str, alerts: list[Alert]) -> None: ...


class ConsoleAlertSink:
    def __init__(self, stream_logger: logging.Logger | None = None) -> None:
        self._logger = stream_logger or logger

    def dispatch(self, subject: str, alerts: list[Alert]) -> None:
        for alert in alerts:
            self._logger.warning(
                "alert",
                extra={
                    "subject": subject,
                    "code": alert.code,
                    "severity": alert.severity.value,
                    "alert_message": alert.message,
                },
            )


class CollectingAlertSink:
    def __init__(self) -> None:
        self.dispatched: list[tuple[str, list[Alert]]] = []

    def dispatch(self, subject: str, alerts: list[Alert]) -> None:
        self.dispatched.append((subject, list(alerts)))


class WebhookAlertSink:
    def __init__(self, url: str, session=None, timeout: float = 10.0) -> None:
        self._url = url
        self._timeout = timeout
        if session is None:
            import requests

            session = requests.Session()
        self._session = session

    def dispatch(self, subject: str, alerts: list[Alert]) -> None:
        payload = {
            "subject": subject,
            "alerts": [
                {"code": a.code, "severity": a.severity.value, "message": a.message} for a in alerts
            ],
        }
        try:
            self._session.post(
                self._url,
                data=json.dumps(payload),
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
        except Exception as exc:
            logger.warning("webhook_dispatch_failed", extra={"error": str(exc)})


class EmailAlertSink:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        recipients: list[str],
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        smtp_factory=None,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._recipients = recipients
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._smtp_factory = smtp_factory or smtplib.SMTP

    def dispatch(self, subject: str, alerts: list[Alert]) -> None:
        body = "\n".join(f"[{a.severity.value.upper()}] {a.code}: {a.message}" for a in alerts)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._sender
        message["To"] = ", ".join(self._recipients)
        message.set_content(body)
        try:
            with self._smtp_factory(self._host, self._port) as server:
                if self._use_tls:
                    server.starttls(context=ssl.create_default_context())
                if self._username and self._password:
                    server.login(self._username, self._password)
                server.send_message(message)
        except Exception as exc:
            logger.warning("email_dispatch_failed", extra={"error": str(exc)})
