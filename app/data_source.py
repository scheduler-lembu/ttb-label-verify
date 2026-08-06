"""Application data-source layer.

Single responsibility: supply "applications" — the expected values a label is
checked against — behind ONE interface, so the source can be a bundled demo CSV
now and TTB's COLA/Azure tenant later without anything downstream changing. This
is the seam the batch-import path and the future production connection both plug
into; it is what lets expected values come from a dataset instead of being
hand-typed.

The loader is driven by the field registry (``app.fields.FIELD_REGISTRY``): any
application column whose key is a registry field flows into ``expected``; every
other column (e.g. ``beverage_type``) flows into ``extra`` untouched. So adding a
registry field automatically makes the loader pull it, and unknown columns ride
along without ever reaching the matcher.

Offline only — reads a local CSV; no AI, no network.
"""

from __future__ import annotations

import abc
import csv
from pathlib import Path

from pydantic import BaseModel

from app.fields import FIELD_REGISTRY

# Registry field keys — the ONLY keys allowed into an Application's ``expected``.
_REGISTRY_KEYS = {f.key for f in FIELD_REGISTRY}

# Columns pulled out of a row by name (not part of expected/extra).
_META_COLUMNS = {"application_id", "display_name", "image_filename"}


class Application(BaseModel):
    """One application record (expected values for a label)."""

    application_id: str
    display_name: str
    image_filename: str | None = None
    expected: dict[str, str | None]  # ONLY keys that exist in the field registry
    extra: dict[str, str]            # any other columns (e.g. beverage_type)


class ApplicationSource(abc.ABC):
    """Interface every application source implements (demo CSV, Azure/COLA, ...)."""

    @abc.abstractmethod
    def list_applications(self) -> list[Application]:
        """Return all applications in source order."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_application(self, application_id: str) -> Application | None:
        """Return the application with ``application_id``, or None if absent."""
        raise NotImplementedError


class DemoCsvSource(ApplicationSource):
    """Application source backed by a bundled demo CSV (a stand-in for COLA)."""

    def __init__(self, csv_path: "str | Path") -> None:
        self.csv_path = Path(csv_path)
        self._apps: list[Application] = self._load()

    def _load(self) -> list[Application]:
        # Load once at construction and hold in memory: the demo DB is small and
        # read-only, so re-reading per request would be wasted I/O. A missing file
        # or a CSV lacking the identity columns fails loudly here with a message
        # naming the fix, rather than yielding silently empty results downstream.
        if not self.csv_path.exists():
            raise ValueError(
                f"Demo application database not found: {self.csv_path}. "
                "Expected a CSV of application records (see sample_data/demo_applications.csv)."
            )
        with self.csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            for required in ("application_id", "display_name"):
                if required not in headers:
                    raise ValueError(
                        f"Demo application database {self.csv_path} is missing the "
                        f"required '{required}' column. Found columns: {headers}."
                    )
            apps = [self._row_to_application(row) for row in reader]
        return apps

    @staticmethod
    def _row_to_application(row: dict) -> Application:
        # Registry-driven split (see module docstring): a column is routed to
        # ``expected`` only if its key is a real registry field, so only known
        # fields ever reach the matcher; everything else rides along in ``extra``
        # untouched. A blank registry cell becomes None (no expected value to
        # check) rather than an empty string, which the matcher treats distinctly.
        expected: dict[str, str | None] = {}
        extra: dict[str, str] = {}
        for col, raw in row.items():
            if col is None or col in _META_COLUMNS:
                continue
            val = (raw or "").strip()
            if col in _REGISTRY_KEYS:
                expected[col] = val or None  # blank cell -> None
            else:
                extra[col] = val
        image = (row.get("image_filename") or "").strip() or None
        return Application(
            application_id=(row.get("application_id") or "").strip(),
            display_name=(row.get("display_name") or "").strip(),
            image_filename=image,
            expected=expected,
            extra=extra,
        )

    def list_applications(self) -> list[Application]:
        return list(self._apps)

    def get_application(self, application_id: str) -> Application | None:
        for app in self._apps:
            if app.application_id == application_id:
                return app
        return None


class AzureApplicationSource(ApplicationSource):
    """Production seam. In production this pulls application records from TTB's
    COLA/Azure tenant and returns the SAME Application shape, so nothing
    downstream changes. Out of scope for the prototype (CON-01); the demo runs on
    DemoCsvSource or an uploaded CSV."""

    _MESSAGE = (
        "Production seam. In production this pulls application records from TTB's "
        "COLA/Azure tenant and returns the SAME Application shape, so nothing "
        "downstream changes. Out of scope for the prototype (CON-01); the demo runs "
        "on DemoCsvSource or an uploaded CSV."
    )

    def list_applications(self) -> list[Application]:
        raise NotImplementedError(self._MESSAGE)

    def get_application(self, application_id: str) -> Application | None:
        raise NotImplementedError(self._MESSAGE)


def get_application_source(settings) -> ApplicationSource:
    """Select the application source from settings (defaults to the demo CSV)."""
    if getattr(settings, "DATA_SOURCE", "demo") == "azure":
        return AzureApplicationSource()
    return DemoCsvSource(
        getattr(settings, "DEMO_DB_PATH", "sample_data/demo_applications.csv")
    )


if __name__ == "__main__":
    for a in DemoCsvSource("sample_data/demo_applications.csv").list_applications():
        print(a.application_id, "|", a.display_name)
