"""Database security: file permissions, disk encryption detection, and privacy reporting."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def check_disk_encryption() -> bool:
    """Return ``True`` if FileVault is enabled on the boot volume.

    Uses ``fdesetup status`` which is available on all macOS versions
    that support FileVault 2.  Returns ``False`` on non-macOS platforms or
    if the check fails for any reason.
    """
    try:
        result = subprocess.run(
            ["fdesetup", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "FileVault is On" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # Not macOS, command not found, or other OS-level error.
        return False


def secure_database_permissions(db_path: Path) -> None:
    """Set file permissions to owner-only (``chmod 600``) on the database.

    Also secures the WAL and SHM journal files if they exist.
    """
    if not db_path.exists():
        return

    owner_only = stat.S_IRUSR | stat.S_IWUSR  # 0o600
    os.chmod(db_path, owner_only)

    # SQLite journal files
    for suffix in ("-wal", "-shm", "-journal"):
        journal = db_path.with_name(db_path.name + suffix)
        if journal.exists():
            os.chmod(journal, owner_only)


def _file_permissions_display(path: Path) -> str:
    """Return a human-readable permission string like ``'-rw-------'``."""
    if not path.exists():
        return "file not found"
    mode = path.stat().st_mode
    perms = stat.filemode(mode)
    return perms


def _check_permissions_secure(path: Path) -> bool:
    """Return ``True`` if the file has no group/other access."""
    if not path.exists():
        return True  # nothing to leak
    mode = path.stat().st_mode
    # Check that group and other have zero permissions
    return (mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0


def generate_privacy_report(db_path: Path, privacy_mode: str = "standard") -> str:
    """Generate a security posture report for the database.

    Checks:
    - File permissions
    - FileVault status
    - Privacy mode setting
    - Database file size
    - Recommendations
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  Life World Model — Privacy & Security Report")
    lines.append("=" * 60)
    lines.append("")

    # --- Database file ---
    lines.append("Database")
    lines.append("-" * 40)
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        lines.append(f"  Path:        {db_path}")
        lines.append(f"  Size:        {size_mb:.2f} MB")
        lines.append(f"  Permissions: {_file_permissions_display(db_path)}")
        perms_ok = _check_permissions_secure(db_path)
        lines.append(f"  Secure:      {'YES' if perms_ok else 'NO — run `lwm db secure`'}")
    else:
        lines.append(f"  Path:        {db_path}")
        lines.append("  Status:      does not exist yet")
    lines.append("")

    # --- Disk encryption ---
    lines.append("Disk Encryption")
    lines.append("-" * 40)
    filevault = check_disk_encryption()
    lines.append(f"  FileVault:   {'ENABLED' if filevault else 'DISABLED or unknown'}")
    lines.append("")

    # --- Privacy mode ---
    lines.append("Privacy Mode")
    lines.append("-" * 40)
    lines.append(f"  Current:     {privacy_mode}")
    mode_descriptions = {
        "standard": "URLs, titles, and commands stored as-is",
        "enhanced": "URLs hashed (domain preserved), shell args redacted, sensitive titles hashed",
        "paranoid": "Everything hashed, only activity categories preserved",
    }
    lines.append(f"  Description: {mode_descriptions.get(privacy_mode, 'unknown mode')}")
    lines.append("")

    # --- Recommendations ---
    lines.append("Recommendations")
    lines.append("-" * 40)
    recommendations: list[str] = []

    if db_path.exists() and not _check_permissions_secure(db_path):
        recommendations.append(
            "Set database permissions to owner-only: "
            "lwm db secure (or chmod 600)"
        )

    if not filevault:
        recommendations.append(
            "Enable FileVault for full-disk encryption: "
            "System Settings > Privacy & Security > FileVault"
        )

    if privacy_mode == "standard":
        recommendations.append(
            "Consider 'enhanced' privacy mode to hash URLs and redact "
            "shell commands: export LWM_PRIVACY_MODE=enhanced"
        )

    if not recommendations:
        recommendations.append("No issues found. Security posture looks good.")

    for i, rec in enumerate(recommendations, 1):
        lines.append(f"  {i}. {rec}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
