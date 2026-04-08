"""Tests for the security / privacy hardening module."""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from life_world_model.security.redaction import (
    SENSITIVE_DOMAINS,
    apply_privacy_filter,
    hash_title,
    hash_url,
    hash_url_paranoid,
    is_sensitive_url,
    redact_shell_command,
)
from life_world_model.security.encryption import (
    check_disk_encryption,
    generate_privacy_report,
    secure_database_permissions,
)
from life_world_model.security.export import export_redacted
from life_world_model.storage.sqlite_store import SQLiteStore
from life_world_model.types import RawEvent


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

def _make_event(
    source: str = "chrome",
    title: str | None = "Pull Request #42 — Fix login bug",
    domain: str | None = "github.com",
    url: str | None = "https://github.com/user/repo/pull/42",
    **kwargs,
) -> RawEvent:
    return RawEvent(
        timestamp=datetime(2026, 4, 7, 10, 30, 0, tzinfo=timezone.utc),
        source=source,
        title=title,
        domain=domain,
        url=url,
        **kwargs,
    )


# -----------------------------------------------------------------------
# hash_url
# -----------------------------------------------------------------------

class TestHashUrl:
    def test_preserves_domain(self):
        result = hash_url("https://github.com/user/repo/pull/42")
        assert result.startswith("github.com/h:")

    def test_hashes_path(self):
        result = hash_url("https://github.com/user/repo/pull/42")
        # Should not contain the original path
        assert "/user/repo/pull/42" not in result

    def test_deterministic(self):
        url = "https://example.com/secret/page?token=abc123"
        assert hash_url(url) == hash_url(url)

    def test_different_urls_different_hashes(self):
        a = hash_url("https://example.com/page1")
        b = hash_url("https://example.com/page2")
        assert a != b

    def test_same_domain_different_paths(self):
        a = hash_url("https://example.com/page1")
        b = hash_url("https://example.com/page2")
        # Both should start with the same domain
        assert a.split("/h:")[0] == b.split("/h:")[0]

    def test_paranoid_hides_domain(self):
        result = hash_url_paranoid("https://github.com/user/repo")
        assert "github.com" not in result
        assert result.startswith("h:")


# -----------------------------------------------------------------------
# redact_shell_command
# -----------------------------------------------------------------------

class TestRedactShellCommand:
    def test_preserves_command_name(self):
        result = redact_shell_command("git commit -m 'secret message'")
        assert result.startswith("git ")

    def test_simple_command_no_args(self):
        assert redact_shell_command("ls") == "ls"

    def test_empty_command(self):
        assert redact_shell_command("") == ""

    def test_redacts_openai_key(self):
        cmd = "curl -H sk-proj-abc123defghijk456789"
        result = redact_shell_command(cmd)
        assert "sk-proj-abc123" not in result
        assert result.startswith("curl ")
        assert "[REDACTED:" in result

    def test_redacts_github_pat(self):
        cmd = "gh auth login --with-token ghp_1234567890abcdefghij1234567890ab"
        result = redact_shell_command(cmd)
        assert "ghp_" not in result
        assert "[REDACTED:" in result

    def test_redacts_slack_token(self):
        cmd = "export SLACK_TOKEN=xoxb-123456789-abcdefghij"
        result = redact_shell_command(cmd)
        assert "xoxb-" not in result

    def test_redacts_aws_key(self):
        cmd = "aws configure set aws_access_key_id AKIAIOSFODNN7EXAMPLE"
        result = redact_shell_command(cmd)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_redacts_email_address(self):
        cmd = "git config user.email naledi@example.com"
        result = redact_shell_command(cmd)
        assert "naledi@example.com" not in result
        assert "[email:h:" in result

    def test_redacts_ip_address(self):
        cmd = "ssh root@192.168.1.100"
        result = redact_shell_command(cmd)
        assert "192.168.1.100" not in result
        assert "[ip:h:" in result

    def test_redacts_home_path(self):
        cmd = "cat /Users/naledi/Documents/secrets.txt"
        result = redact_shell_command(cmd)
        assert "/Users/naledi" not in result
        assert "/Users/[user:h:" in result

    def test_deterministic(self):
        cmd = "curl https://api.example.com/secret"
        assert redact_shell_command(cmd) == redact_shell_command(cmd)


# -----------------------------------------------------------------------
# hash_title
# -----------------------------------------------------------------------

class TestHashTitle:
    def test_preserves_activity_keywords(self):
        result = hash_title("Pull Request #42 — Fix login bug")
        assert "Pull" in result
        assert "Request" in result

    def test_hashes_specific_content(self):
        result = hash_title("Pull Request #42 — Fix login bug")
        # "#42" and "Fix", "login", "bug" are not activity keywords
        assert "#42" not in result
        assert "[h:" in result

    def test_preserves_inbox(self):
        result = hash_title("inbox (3) - Gmail")
        assert "inbox" in result

    def test_preserves_stack_overflow(self):
        result = hash_title("Stack Overflow — How to parse JSON in Python")
        # "Stack" and "Overflow" should match (case-insensitive via lowering)
        assert "Stack" in result or "stack" in result.lower()

    def test_deterministic(self):
        title = "Dashboard — Revenue for Q4 2025"
        assert hash_title(title) == hash_title(title)


# -----------------------------------------------------------------------
# is_sensitive_url
# -----------------------------------------------------------------------

class TestIsSensitiveUrl:
    def test_banking_sites(self):
        assert is_sensitive_url("https://chase.com/accounts") is True
        assert is_sensitive_url("https://bankofamerica.com/login") is True
        assert is_sensitive_url("https://paypal.com/myaccount") is True

    def test_email(self):
        assert is_sensitive_url("https://mail.google.com/mail/u/0/") is True
        assert is_sensitive_url("https://outlook.live.com/mail/0/inbox") is True

    def test_messaging(self):
        assert is_sensitive_url("https://web.whatsapp.com/") is True
        assert is_sensitive_url("https://messages.google.com/web/conversations") is True

    def test_health(self):
        assert is_sensitive_url("https://myfitnesspal.com/food/diary") is True
        assert is_sensitive_url("https://patient.info/health") is True

    def test_non_sensitive(self):
        assert is_sensitive_url("https://github.com/user/repo") is False
        assert is_sensitive_url("https://stackoverflow.com/questions") is False
        assert is_sensitive_url("https://docs.python.org/3/library/") is False

    def test_subdomain_matching(self):
        assert is_sensitive_url("https://online.chase.com/dashboard") is True
        assert is_sensitive_url("https://secure.bankofamerica.com/login") is True

    def test_sensitive_paths(self):
        assert is_sensitive_url("https://example.com/login") is True
        assert is_sensitive_url("https://example.com/account/settings") is True

    def test_sensitive_domains_set_not_empty(self):
        assert len(SENSITIVE_DOMAINS) > 10


# -----------------------------------------------------------------------
# apply_privacy_filter
# -----------------------------------------------------------------------

class TestApplyPrivacyFilter:
    def test_standard_mode_passthrough(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "standard")
        assert result[0].url == events[0].url
        assert result[0].title == events[0].title

    def test_standard_mode_returns_same_list(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "standard")
        assert result is events

    def test_enhanced_hashes_url(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "enhanced")
        assert result[0].url != events[0].url
        assert "github.com" in result[0].url  # domain preserved

    def test_enhanced_preserves_domain(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "enhanced")
        assert result[0].domain == "github.com"

    def test_enhanced_hashes_title(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "enhanced")
        # Activity keywords like "Pull" "Request" should be preserved
        assert "Pull" in result[0].title
        assert "Request" in result[0].title

    def test_enhanced_redacts_shell_commands(self):
        events = [
            _make_event(
                source="shell",
                title="git push origin main",
                domain="terminal",
                url=None,
            )
        ]
        result = apply_privacy_filter(events, "enhanced")
        assert result[0].title.startswith("git ")

    def test_enhanced_fully_hashes_sensitive_urls(self):
        events = [
            _make_event(
                url="https://chase.com/accounts/checking/12345",
                domain="chase.com",
                title="Checking Account Summary",
            )
        ]
        result = apply_privacy_filter(events, "enhanced")
        # Sensitive URL should be fully hashed (no domain visible)
        assert "chase.com" not in result[0].url
        assert result[0].url.startswith("h:")
        # Title should also be fully hashed for sensitive pages
        assert result[0].title.startswith("h:")

    def test_paranoid_hashes_everything(self):
        events = [_make_event()]
        result = apply_privacy_filter(events, "paranoid")
        assert result[0].url.startswith("h:")
        assert result[0].title.startswith("h:")
        # Domain replaced with category
        assert result[0].domain.startswith("[")

    def test_paranoid_categorizes_domain(self):
        events = [_make_event(domain="github.com")]
        result = apply_privacy_filter(events, "paranoid")
        assert result[0].domain == "[development]"

    def test_paranoid_unknown_domain(self):
        events = [_make_event(domain="random-site.xyz")]
        result = apply_privacy_filter(events, "paranoid")
        assert result[0].domain == "[other]"

    def test_does_not_mutate_originals(self):
        events = [_make_event()]
        original_url = events[0].url
        apply_privacy_filter(events, "enhanced")
        assert events[0].url == original_url

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown privacy mode"):
            apply_privacy_filter([_make_event()], "maximum")

    def test_handles_none_fields(self):
        events = [_make_event(url=None, title=None, domain=None)]
        result = apply_privacy_filter(events, "enhanced")
        assert result[0].url is None
        assert result[0].title is None

    def test_paranoid_clears_metadata(self):
        events = [_make_event(metadata={"path": "/Users/naledi/secret.txt"})]
        result = apply_privacy_filter(events, "paranoid")
        assert "path" not in result[0].metadata
        assert "category" in result[0].metadata


# -----------------------------------------------------------------------
# check_disk_encryption
# -----------------------------------------------------------------------

class TestCheckDiskEncryption:
    def test_runs_without_error(self):
        # Should not raise, regardless of platform
        result = check_disk_encryption()
        assert isinstance(result, bool)


# -----------------------------------------------------------------------
# secure_database_permissions
# -----------------------------------------------------------------------

class TestSecureDatabasePermissions:
    def test_sets_owner_only(self, tmp_path: Path):
        db = tmp_path / "test.db"
        db.write_text("test data")
        # Make it world-readable first
        os.chmod(db, 0o644)

        secure_database_permissions(db)

        mode = db.stat().st_mode
        # Owner can read/write
        assert mode & stat.S_IRUSR
        assert mode & stat.S_IWUSR
        # Group and other have nothing
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IWGRP)
        assert not (mode & stat.S_IROTH)
        assert not (mode & stat.S_IWOTH)

    def test_secures_journal_files(self, tmp_path: Path):
        db = tmp_path / "test.db"
        wal = tmp_path / "test.db-wal"
        shm = tmp_path / "test.db-shm"
        for f in (db, wal, shm):
            f.write_text("data")
            os.chmod(f, 0o644)

        secure_database_permissions(db)

        for f in (db, wal, shm):
            mode = f.stat().st_mode
            assert not (mode & stat.S_IRGRP)
            assert not (mode & stat.S_IROTH)

    def test_nonexistent_db_is_noop(self, tmp_path: Path):
        db = tmp_path / "nonexistent.db"
        # Should not raise
        secure_database_permissions(db)


# -----------------------------------------------------------------------
# generate_privacy_report
# -----------------------------------------------------------------------

class TestGeneratePrivacyReport:
    def test_report_contains_sections(self, tmp_path: Path):
        db = tmp_path / "test.db"
        db.write_text("fake db content")
        report = generate_privacy_report(db, privacy_mode="enhanced")
        assert "Database" in report
        assert "Disk Encryption" in report
        assert "Privacy Mode" in report
        assert "enhanced" in report
        assert "Recommendations" in report

    def test_report_nonexistent_db(self, tmp_path: Path):
        db = tmp_path / "missing.db"
        report = generate_privacy_report(db)
        assert "does not exist" in report

    def test_report_standard_mode_recommends_upgrade(self, tmp_path: Path):
        db = tmp_path / "test.db"
        db.write_text("data")
        report = generate_privacy_report(db, privacy_mode="standard")
        assert "enhanced" in report.lower()

    def test_report_insecure_permissions(self, tmp_path: Path):
        db = tmp_path / "test.db"
        db.write_text("data")
        os.chmod(db, 0o644)
        report = generate_privacy_report(db, privacy_mode="enhanced")
        assert "600" in report or "chmod" in report.lower() or "secure" in report.lower()


# -----------------------------------------------------------------------
# export_redacted
# -----------------------------------------------------------------------

class TestExportRedacted:
    def _seed_store(self, tmp_path: Path) -> SQLiteStore:
        store = SQLiteStore(tmp_path / "source.db")
        store.initialize()
        events = [
            RawEvent(
                timestamp=datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc),
                source="chrome",
                title="Pull Request #42",
                domain="github.com",
                url="https://github.com/user/repo/pull/42",
            ),
            RawEvent(
                timestamp=datetime(2026, 4, 7, 11, 0, 0, tzinfo=timezone.utc),
                source="shell",
                title="git push origin main",
                domain="terminal",
                url=None,
            ),
            RawEvent(
                timestamp=datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc),
                source="chrome",
                title="Checking Account",
                domain="chase.com",
                url="https://chase.com/accounts/12345",
            ),
        ]
        store.save_raw_events(events)
        return store

    def test_export_creates_file(self, tmp_path: Path):
        store = self._seed_store(tmp_path)
        out = tmp_path / "export" / "redacted.db"
        count = export_redacted(store, out, privacy_level="enhanced")
        assert out.exists()
        assert count == 3

    def test_export_data_is_redacted(self, tmp_path: Path):
        store = self._seed_store(tmp_path)
        out = tmp_path / "redacted.db"
        export_redacted(store, out, privacy_level="enhanced")

        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT url, title, domain FROM raw_events ORDER BY timestamp"
            ).fetchall()

        # First event: github URL should be hashed but domain preserved
        url_0, title_0, domain_0 = rows[0]
        assert "github.com" in url_0
        assert "/user/repo" not in url_0

        # Third event: chase.com is sensitive, URL fully hashed
        url_2, title_2, domain_2 = rows[2]
        assert "chase.com" not in url_2
        assert url_2.startswith("h:")

    def test_export_produces_valid_sqlite(self, tmp_path: Path):
        store = self._seed_store(tmp_path)
        out = tmp_path / "redacted.db"
        export_redacted(store, out, privacy_level="paranoid")

        with sqlite3.connect(out) as conn:
            count = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
        assert count == 3


# -----------------------------------------------------------------------
# Config integration
# -----------------------------------------------------------------------

class TestConfigPrivacyMode:
    def test_default_is_standard(self):
        from life_world_model.config import Settings
        s = Settings()
        assert s.privacy_mode == "standard"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("LWM_PRIVACY_MODE", "paranoid")
        from life_world_model.config import load_settings
        settings = load_settings()
        assert settings.privacy_mode == "paranoid"
