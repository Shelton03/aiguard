"""SMTP email alerting for the Human Review module.

Configuration is loaded (in priority order) from:
1. Environment variables  (AIGUARD_SMTP_*)
2. A config file          (.aiguard/review_config.toml  or  aiguard.toml)
3. Hard defaults          (localhost:1025, plain SMTP – useful for dev)

Example env vars::

    AIGUARD_SMTP_HOST=smtp.gmail.com
    AIGUARD_SMTP_PORT=587
    AIGUARD_SMTP_USER=alerts@example.com
    AIGUARD_SMTP_PASSWORD=secretpassword
    AIGUARD_SMTP_FROM=alerts@example.com
    AIGUARD_SMTP_TO=reviewer1@example.com,reviewer2@example.com
    AIGUARD_SMTP_USE_TLS=true
    AIGUARD_REVIEW_BASE_URL=http://localhost:8000
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, List
import threading

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-reattr]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------


@dataclass
class SMTPConfig:
    host: str = "localhost"
    port: int = 1025
    user: Optional[str] = None
    password: Optional[str] = None
    from_addr: str = "aiguard@localhost"
    to_addrs: List[str] = field(default_factory=lambda: ["reviewer@localhost"])
    use_tls: bool = False
    base_url: str = "http://localhost:8000"


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "").lower()
    return val in ("1", "true", "yes") if val else default


def _parse_recipients(value: object | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        recipients: List[str] = []
        for item in value:
            if isinstance(item, str):
                recipients.extend(
                    [part.strip() for part in item.split(",") if part.strip()]
                )
        return recipients
    return []


_rr_lock = threading.Lock()
_rr_index = 0


def _choose_recipient(recipients: List[str]) -> str:
    if not recipients:
        return "reviewer@localhost"
    if len(recipients) == 1:
        return recipients[0]
    global _rr_index
    with _rr_lock:
        idx = _rr_index % len(recipients)
        _rr_index += 1
    return recipients[idx]


def load_smtp_config(root: Optional[Path] = None) -> SMTPConfig:
    """Load SMTP config; env overrides file overrides defaults."""
    cfg = SMTPConfig()

    # --- File config (TOML) ---
    root = root or Path.cwd()
    candidates = [
        root / ".aiguard" / "review_config.toml",
        root / "aiguard.toml",
    ]
    if tomllib is not None:
        for candidate in candidates:
            if candidate.exists():
                try:
                    with open(candidate, "rb") as fh:
                        data = tomllib.load(fh)
                    smtp_section = data.get("smtp", {})
                    cfg.host = smtp_section.get("host", cfg.host)
                    cfg.port = int(smtp_section.get("port", cfg.port))
                    cfg.user = smtp_section.get("user", cfg.user)
                    cfg.password = smtp_section.get("password", cfg.password)
                    cfg.from_addr = smtp_section.get("from", cfg.from_addr)
                    to_addrs = _parse_recipients(smtp_section.get("to"))
                    if to_addrs:
                        cfg.to_addrs = to_addrs
                    cfg.use_tls = bool(smtp_section.get("use_tls", cfg.use_tls))
                    cfg.base_url = data.get("review", {}).get("base_url", cfg.base_url)
                    break
                except Exception as exc:  # pragma: no cover
                    logger.warning("Could not parse SMTP config file %s: %s", candidate, exc)

    # --- File config (YAML) ---
    yaml_path = root / "aiguard.yaml"
    if yaml_path.exists():
        try:
            import yaml  # type: ignore[import]

            with yaml_path.open() as fh:
                data = yaml.safe_load(fh) or {}
            smtp_section = data.get("smtp", {}) or {}
            cfg.host = smtp_section.get("host", cfg.host)
            cfg.port = int(smtp_section.get("port", cfg.port))
            cfg.user = smtp_section.get("user", cfg.user)
            cfg.password = smtp_section.get("password", cfg.password)
            cfg.from_addr = smtp_section.get("from", cfg.from_addr)
            to_addrs = _parse_recipients(smtp_section.get("to"))
            if to_addrs:
                cfg.to_addrs = to_addrs
            cfg.use_tls = bool(smtp_section.get("use_tls", cfg.use_tls))
            cfg.base_url = (data.get("review", {}) or {}).get("base_url", cfg.base_url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not parse YAML config file %s: %s", yaml_path, exc)

    # --- Env overrides (always win) ---
    cfg.host = os.getenv("AIGUARD_SMTP_HOST", cfg.host)
    cfg.port = int(os.getenv("AIGUARD_SMTP_PORT", cfg.port))
    cfg.user = os.getenv("AIGUARD_SMTP_USER", cfg.user)
    cfg.password = os.getenv("AIGUARD_SMTP_PASSWORD", cfg.password)
    cfg.from_addr = os.getenv("AIGUARD_SMTP_FROM", cfg.from_addr)
    env_to = os.getenv("AIGUARD_SMTP_TO")
    env_addrs = _parse_recipients(env_to)
    if env_addrs:
        cfg.to_addrs = env_addrs
    cfg.use_tls = _env_bool("AIGUARD_SMTP_USE_TLS", cfg.use_tls)
    cfg.base_url = os.getenv("AIGUARD_REVIEW_BASE_URL", cfg.base_url).rstrip("/")

    return cfg


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------


def _build_review_email(
    *,
    project: str,
    item_id: str,
    module_type: str,
    trigger_reason: str,
    raw_score: float,
    token: str,
    cfg: SMTPConfig,
    recipient: str,
) -> MIMEMultipart:
    review_url = (
        f"{cfg.base_url}/project/{project}/review/{token}"
    )

    subject = f"[AIGuard] Human review required — {project}/{module_type}"

    text_body = f"""\
AIGuard Human Review Alert
===========================

Project      : {project}
Module       : {module_type}
Raw score    : {raw_score:.4f}
Trigger      : {trigger_reason}
Item ID      : {item_id}

Review link (single-use):
{review_url}

This link expires after it is used.
Do not forward this email.
"""

    html_body = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px">
  <h2 style="color:#c0392b">⚠ AIGuard — Human Review Required</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px;font-weight:bold">Project</td><td style="padding:6px">{project}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Module</td><td style="padding:6px">{module_type}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Raw score</td><td style="padding:6px">{raw_score:.4f}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Trigger</td><td style="padding:6px">{trigger_reason}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Item ID</td><td style="padding:6px">{item_id}</td></tr>
  </table>
  <br/>
  <a href="{review_url}"
     style="background:#2980b9;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;display:inline-block">
    Open Review Form
  </a>
  <p style="color:#888;font-size:12px;margin-top:24px">
    This is a single-use link. It expires after use. Do not forward this email.
  </p>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr
    msg["To"] = recipient
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


# ---------------------------------------------------------------------------
# Emailer
# ---------------------------------------------------------------------------


class Emailer:
    """Sends SMTP review alert emails."""

    def __init__(self, config: Optional[SMTPConfig] = None, root: Optional[Path] = None) -> None:
        self.cfg = config or load_smtp_config(root)

    def send_review_alert(
        self,
        *,
        project: str,
        item_id: str,
        module_type: str,
        trigger_reason: str,
        raw_score: float,
        token: str,
    ) -> None:
        """Build and dispatch the review-alert email."""
        recipient = _choose_recipient(self.cfg.to_addrs)
        msg = _build_review_email(
            project=project,
            item_id=item_id,
            module_type=module_type,
            trigger_reason=trigger_reason,
            raw_score=raw_score,
            token=token,
            cfg=self.cfg,
            recipient=recipient,
        )
        try:
            self._send(msg, recipient)
            logger.info(
                "Review alert sent to %s for project=%s item=%s",
                recipient,
                project,
                item_id,
            )
        except Exception as exc:
            logger.error("Failed to send review alert: %s", exc)
            raise

    def _send(self, msg: MIMEMultipart, recipient: str) -> None:
        if self.cfg.use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.cfg.host, self.cfg.port) as server:
                server.ehlo()
                server.starttls(context=context)
                if self.cfg.user and self.cfg.password:
                    server.login(self.cfg.user, self.cfg.password)
                server.sendmail(self.cfg.from_addr, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(self.cfg.host, self.cfg.port) as server:
                if self.cfg.user and self.cfg.password:
                    server.login(self.cfg.user, self.cfg.password)
                server.sendmail(self.cfg.from_addr, [recipient], msg.as_string())
