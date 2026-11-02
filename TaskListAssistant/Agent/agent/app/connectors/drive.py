"""Mock Drive connector (T11) — token-gated file access.

A fake file list including statement PDFs. Fetch works only with a valid scoped
token that includes the drive read scope.

To go real: implement against the Google Drive API, same list/fetch contract.
"""
from __future__ import annotations

from dataclasses import dataclass

from .oauth import ScopedToken

DRIVE_READ_SCOPE = "drive.readonly"


@dataclass
class DriveFile:
    id: str
    name: str
    content: str


class TokenError(Exception):
    pass


class MockDriveConnector:
    def __init__(self) -> None:
        self._files = [
            DriveFile(id="f1", name="Statement_Jun.pdf", content="account statement June"),
            DriveFile(id="f2", name="Statement_Jul.pdf", content="account statement July"),
            DriveFile(id="f3", name="Statement_Aug.pdf", content="account statement August"),
            DriveFile(id="f4", name="grocery_list.txt", content="milk, eggs"),
        ]

    def _check(self, token: ScopedToken | None) -> None:
        if token is None or not token.allows(DRIVE_READ_SCOPE):
            raise TokenError("missing or insufficient Drive scope")

    def list_files(self, token: ScopedToken | None) -> list[DriveFile]:
        self._check(token)
        return list(self._files)

    def fetch(self, token: ScopedToken | None, file_id: str) -> DriveFile | None:
        self._check(token)
        return next((f for f in self._files if f.id == file_id), None)
