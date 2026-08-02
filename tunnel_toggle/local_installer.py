"""Conservative user-local installation for Tunnel Toggle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from tunnel_toggle import __version__

APPLICATION_ID = "io.github.charsus.TunnelToggle"
DESKTOP_FILENAME = f"{APPLICATION_ID}.desktop"
METAINFO_FILENAME = f"{APPLICATION_ID}.metainfo.xml"

INSTALL_DIRECTORY_NAME = "tunnel-toggle"
GENERATIONS_DIRECTORY_NAME = "venvs"
MANIFEST_FILENAME = "install-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
LAUNCHER_FILENAME = "tunnel-toggle"


class InstallerError(RuntimeError):
    """Raised when a local installation cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class InstallLayout:
    """Resolved user-local installation paths."""

    data_home: Path
    bin_directory: Path
    install_root: Path
    generations_directory: Path
    launcher_path: Path
    desktop_path: Path
    metainfo_path: Path
    manifest_path: Path

    @classmethod
    def create(
        cls,
        *,
        home: Path,
        environment: Mapping[str, str],
        data_home: Path | None = None,
        bin_directory: Path | None = None,
    ) -> InstallLayout:
        """Resolve a complete installation layout."""
        normalized_home = _require_absolute_path(
            home,
            name="home",
        )

        if data_home is None:
            configured_data_home = environment.get(
                "XDG_DATA_HOME",
                "",
            ).strip()

            if configured_data_home and Path(configured_data_home).is_absolute():
                resolved_data_home = Path(configured_data_home)
            else:
                resolved_data_home = normalized_home / ".local" / "share"
        else:
            resolved_data_home = _require_absolute_path(
                data_home,
                name="data_home",
            )

        if bin_directory is None:
            resolved_bin_directory = normalized_home / ".local" / "bin"
        else:
            resolved_bin_directory = _require_absolute_path(
                bin_directory,
                name="bin_directory",
            )

        install_root = resolved_data_home / INSTALL_DIRECTORY_NAME

        return cls(
            data_home=resolved_data_home,
            bin_directory=resolved_bin_directory,
            install_root=install_root,
            generations_directory=(install_root / GENERATIONS_DIRECTORY_NAME),
            launcher_path=(resolved_bin_directory / LAUNCHER_FILENAME),
            desktop_path=(resolved_data_home / "applications" / DESKTOP_FILENAME),
            metainfo_path=(resolved_data_home / "metainfo" / METAINFO_FILENAME),
            manifest_path=install_root / MANIFEST_FILENAME,
        )

    def generation_directory(
        self,
        generation_name: str,
    ) -> Path:
        """Return the directory for one installed environment."""
        _validate_generation_name(generation_name)
        return self.generations_directory / generation_name

    def generation_python(
        self,
        generation_name: str,
    ) -> Path:
        """Return the Python executable for one generation."""
        return self.generation_directory(generation_name) / "bin" / "python"

    @property
    def external_files(self) -> tuple[Path, ...]:
        """Return files installed outside the private root."""
        return (
            self.launcher_path,
            self.desktop_path,
            self.metainfo_path,
        )


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """Validated ownership record for one local installation."""

    schema_version: int
    application_id: str
    version: str
    active_generation: str
    files: tuple[tuple[str, str], ...]

    @classmethod
    def load(cls, path: Path) -> InstallManifest:
        """Load and validate a manifest from disk."""
        try:
            raw_value: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InstallerError(
                "The existing installation manifest is unreadable."
            ) from error

        if not isinstance(raw_value, dict):
            raise InstallerError("The existing installation manifest is invalid.")

        schema_version = raw_value.get("schema_version")
        application_id = raw_value.get("application_id")
        version = raw_value.get("version")
        active_generation = raw_value.get("active_generation")
        files_value = raw_value.get("files")

        if schema_version != MANIFEST_SCHEMA_VERSION:
            raise InstallerError(
                "The existing installation manifest uses an unsupported schema."
            )

        if application_id != APPLICATION_ID:
            raise InstallerError(
                "The existing installation belongs to another application."
            )

        if not isinstance(version, str) or not version:
            raise InstallerError("The existing installation version is invalid.")

        if not isinstance(active_generation, str) or not active_generation:
            raise InstallerError("The existing installation generation is invalid.")

        _validate_generation_name(active_generation)

        if not isinstance(files_value, dict):
            raise InstallerError("The existing installation file list is invalid.")

        parsed_files: list[tuple[str, str]] = []

        for file_path, digest in files_value.items():
            if (
                not isinstance(file_path, str)
                or not file_path
                or not isinstance(digest, str)
                or len(digest) != 64
            ):
                raise InstallerError(
                    "The existing installation file record is invalid."
                )

            parsed_files.append((file_path, digest))

        return cls(
            schema_version=MANIFEST_SCHEMA_VERSION,
            application_id=APPLICATION_ID,
            version=version,
            active_generation=active_generation,
            files=tuple(sorted(parsed_files)),
        )

    def to_json(self) -> str:
        """Serialize the manifest deterministically."""
        value = {
            "schema_version": self.schema_version,
            "application_id": self.application_id,
            "version": self.version,
            "active_generation": self.active_generation,
            "files": dict(self.files),
        }
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Summary of a completed installation."""

    layout: InstallLayout
    generation_name: str


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    """Restorable state for one external file."""

    path: Path
    existed: bool
    content: bytes
    mode: int


def install_local(
    *,
    source_root: Path,
    home: Path,
    environment: Mapping[str, str],
    data_home: Path | None = None,
    bin_directory: Path | None = None,
    source_python: Path | None = None,
) -> InstallResult:
    """Install Tunnel Toggle into an isolated user environment."""
    layout = InstallLayout.create(
        home=home,
        environment=environment,
        data_home=data_home,
        bin_directory=bin_directory,
    )
    normalized_source_root = _validate_source_root(source_root)
    normalized_source_python = _require_absolute_path(
        source_python or Path(sys.executable),
        name="source_python",
    )

    previous_manifest = _prepare_existing_install(layout)
    generation_name = _new_generation_name()
    generation_directory = layout.generation_directory(generation_name)
    generation_python = layout.generation_python(generation_name)

    if generation_directory.exists():
        raise InstallerError("The new installation generation already exists.")

    layout.generations_directory.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True,
    )

    try:
        _run_checked(
            (
                str(normalized_source_python),
                "-m",
                "venv",
                str(generation_directory),
            )
        )

        if not generation_python.is_file():
            raise InstallerError(
                "Python did not create the expected virtual environment executable."
            )

        _run_checked(
            (
                str(generation_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                str(normalized_source_root),
            )
        )

        _run_checked(
            (
                str(generation_python),
                "-c",
                (
                    "from tunnel_toggle import __version__; "
                    f"assert __version__ == {__version__!r}"
                ),
            )
        )

        launcher_content = render_launcher(generation_python).encode("utf-8")

        desktop_source = (
            normalized_source_root / "packaging" / DESKTOP_FILENAME
        ).read_text(encoding="utf-8")
        desktop_content = render_desktop_entry(
            desktop_source,
            layout.launcher_path,
        ).encode("utf-8")

        metainfo_content = (
            normalized_source_root / "packaging" / METAINFO_FILENAME
        ).read_bytes()

        snapshots = tuple(_capture_file(path) for path in layout.external_files)

        try:
            _atomic_write(
                layout.launcher_path,
                launcher_content,
                mode=0o755,
            )
            _atomic_write(
                layout.desktop_path,
                desktop_content,
                mode=0o644,
            )
            _atomic_write(
                layout.metainfo_path,
                metainfo_content,
                mode=0o644,
            )

            manifest = InstallManifest(
                schema_version=MANIFEST_SCHEMA_VERSION,
                application_id=APPLICATION_ID,
                version=__version__,
                active_generation=generation_name,
                files=tuple(
                    sorted(
                        (
                            str(path),
                            _sha256_file(path),
                        )
                        for path in layout.external_files
                    )
                ),
            )
            _atomic_write(
                layout.manifest_path,
                manifest.to_json().encode("utf-8"),
                mode=0o600,
            )
        except OSError as error:
            _restore_snapshots(snapshots)
            raise InstallerError(
                "Tunnel Toggle could not write its local installation files."
            ) from error

    except (
        InstallerError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        shutil.rmtree(
            generation_directory,
            ignore_errors=True,
        )
        _remove_empty_install_directories(
            layout,
            had_previous_install=(previous_manifest is not None),
        )

        if isinstance(error, InstallerError):
            raise

        raise InstallerError(
            "Tunnel Toggle could not create its isolated application environment."
        ) from error

    if previous_manifest is not None:
        previous_generation = layout.generation_directory(
            previous_manifest.active_generation
        )

        if previous_generation != generation_directory:
            shutil.rmtree(
                previous_generation,
                ignore_errors=True,
            )

    return InstallResult(
        layout=layout,
        generation_name=generation_name,
    )


def uninstall_local(
    *,
    home: Path,
    environment: Mapping[str, str],
    data_home: Path | None = None,
    bin_directory: Path | None = None,
) -> InstallLayout:
    """Remove a validated user-local Tunnel Toggle installation."""
    layout = InstallLayout.create(
        home=home,
        environment=environment,
        data_home=data_home,
        bin_directory=bin_directory,
    )
    manifest = _require_managed_install(layout)

    _verify_managed_files(layout, manifest)

    for file_path in layout.external_files:
        try:
            file_path.unlink()
        except FileNotFoundError:
            raise InstallerError(
                "A managed installation file disappeared during uninstall."
            ) from None
        except OSError as error:
            raise InstallerError(
                "Tunnel Toggle could not remove a managed installation file."
            ) from error

    try:
        shutil.rmtree(layout.install_root)
    except OSError as error:
        raise InstallerError(
            "Tunnel Toggle could not remove its private installation directory."
        ) from error

    return layout


def render_launcher(venv_python: Path) -> str:
    """Render a shell-free-argument launcher for the installed app."""
    normalized_python = _require_absolute_path(
        venv_python,
        name="venv_python",
    )
    quoted_python = shlex.quote(str(normalized_python))

    return f'#!/bin/sh\nexec {quoted_python} -m tunnel_toggle "$@"\n'


def render_desktop_entry(
    source: str,
    launcher_path: Path,
) -> str:
    """Render a desktop entry using the managed launcher path."""
    normalized_launcher = _require_absolute_path(
        launcher_path,
        name="launcher_path",
    )
    rendered_lines: list[str] = []
    exec_count = 0
    try_exec_count = 0

    for line in source.splitlines():
        if line.startswith("Exec="):
            rendered_lines.append(
                "Exec=" + _quote_desktop_exec_argument(str(normalized_launcher))
            )
            exec_count += 1
            continue

        if line.startswith("TryExec="):
            try_exec_count += 1
            continue

        rendered_lines.append(line)

    if exec_count != 1 or try_exec_count != 1:
        raise InstallerError(
            "The source desktop entry has an unexpected launcher definition."
        )

    return "\n".join(rendered_lines) + "\n"


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the user-local installer command parser."""
    parser = argparse.ArgumentParser(
        prog="python -m tunnel_toggle.local_installer",
        description=("Install or remove Tunnel Toggle for the current user."),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    install_parser = subparsers.add_parser(
        "install",
        help="install or update the user-local application",
    )
    install_parser.add_argument(
        "--source-root",
        type=Path,
        default=_default_source_root(),
        help="Tunnel Toggle source checkout to install",
    )
    install_parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python interpreter used to create the environment",
    )
    _add_layout_arguments(install_parser)

    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="remove the managed user-local installation",
    )
    _add_layout_arguments(uninstall_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local installer command."""
    options = build_argument_parser().parse_args(argv)

    try:
        home = Path.home()

        if options.command == "install":
            result = install_local(
                source_root=options.source_root,
                home=home,
                environment=os.environ,
                data_home=options.data_home,
                bin_directory=options.bin_directory,
                source_python=options.python,
            )
            print(
                f"Installed Tunnel Toggle {__version__} to {result.layout.install_root}"
            )
            print(f"Desktop launcher: {result.layout.desktop_path}")
            return 0

        layout = uninstall_local(
            home=home,
            environment=os.environ,
            data_home=options.data_home,
            bin_directory=options.bin_directory,
        )
        print(f"Removed Tunnel Toggle from {layout.install_root}")
        return 0

    except InstallerError as error:
        print(str(error), file=sys.stderr)
        return 1


def _add_layout_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add optional installation-layout overrides."""
    parser.add_argument(
        "--data-home",
        type=Path,
        default=None,
        help="override the XDG user data directory",
    )
    parser.add_argument(
        "--bin-directory",
        type=Path,
        default=None,
        help="override the user launcher directory",
    )


def _default_source_root() -> Path:
    """Return the checkout root when running from source."""
    return Path(__file__).resolve().parents[1]


def _validate_source_root(source_root: Path) -> Path:
    """Require a complete Tunnel Toggle source checkout."""
    normalized = _require_absolute_path(
        source_root,
        name="source_root",
    )
    required_files = (
        normalized / "pyproject.toml",
        normalized / "packaging" / DESKTOP_FILENAME,
        normalized / "packaging" / METAINFO_FILENAME,
    )

    if not all(path.is_file() for path in required_files):
        raise InstallerError(
            "The source root does not contain complete Tunnel Toggle packaging files."
        )

    return normalized


def _prepare_existing_install(
    layout: InstallLayout,
) -> InstallManifest | None:
    """Validate an existing install or reject unmanaged paths."""
    manifest_exists = layout.manifest_path.is_file()
    managed_paths_exist = layout.install_root.exists() or any(
        path.exists() for path in layout.external_files
    )

    if not manifest_exists:
        if managed_paths_exist:
            raise InstallerError(
                "Existing files occupy Tunnel Toggle installation "
                "paths but are not recognized as managed."
            )

        return None

    manifest = _require_managed_install(layout)
    _verify_managed_files(layout, manifest)
    return manifest


def _require_managed_install(
    layout: InstallLayout,
) -> InstallManifest:
    """Load and validate the current ownership manifest."""
    if not layout.manifest_path.is_file():
        raise InstallerError("No managed Tunnel Toggle installation was found.")

    manifest = InstallManifest.load(layout.manifest_path)
    expected_paths = {str(path) for path in layout.external_files}
    recorded_paths = {path for path, _ in manifest.files}

    if recorded_paths != expected_paths:
        raise InstallerError("The installation manifest contains unexpected paths.")

    active_generation = layout.generation_directory(manifest.active_generation)

    if not active_generation.is_dir():
        raise InstallerError("The active application environment is missing.")

    return manifest


def _verify_managed_files(
    layout: InstallLayout,
    manifest: InstallManifest,
) -> None:
    """Require all externally managed files to remain unchanged."""
    recorded_hashes = dict(manifest.files)

    for file_path in layout.external_files:
        expected_hash = recorded_hashes[str(file_path)]

        if not file_path.is_file():
            raise InstallerError("A managed installation file is missing.")

        if _sha256_file(file_path) != expected_hash:
            raise InstallerError(
                "A managed installation file was modified; "
                "refusing to overwrite or remove it."
            )


def _capture_file(path: Path) -> _FileSnapshot:
    """Capture one file before an atomic replacement."""
    if not path.exists():
        return _FileSnapshot(
            path=path,
            existed=False,
            content=b"",
            mode=0,
        )

    if not path.is_file():
        raise InstallerError("An installation target exists but is not a file.")

    stat_result = path.stat()

    return _FileSnapshot(
        path=path,
        existed=True,
        content=path.read_bytes(),
        mode=stat_result.st_mode & 0o777,
    )


def _restore_snapshots(
    snapshots: tuple[_FileSnapshot, ...],
) -> None:
    """Best-effort restoration after an installation write failure."""
    for snapshot in snapshots:
        try:
            if snapshot.existed:
                _atomic_write(
                    snapshot.path,
                    snapshot.content,
                    mode=snapshot.mode,
                )
            else:
                snapshot.path.unlink(missing_ok=True)
        except OSError:
            continue


def _atomic_write(
    path: Path,
    content: bytes,
    *,
    mode: int,
) -> None:
    """Atomically replace a managed file."""
    path.parent.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True,
    )
    temporary_path = path.with_name(f".{path.name}.tmp-{uuid4().hex}")

    try:
        temporary_path.write_bytes(content)
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one managed file."""
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        for chunk in iter(
            lambda: file_handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _quote_desktop_exec_argument(value: str) -> str:
    """Quote one executable path using desktop-entry rules."""
    if "\n" in value or "\r" in value or "\0" in value:
        raise InstallerError("The launcher path contains unsupported characters.")

    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("`", "\\`")
    escaped = escaped.replace("$", "\\$")
    escaped = escaped.replace("%", "%%")

    return f'"{escaped}"'


def _require_absolute_path(
    path: Path,
    *,
    name: str,
) -> Path:
    """Require and normalize an absolute filesystem path."""
    expanded = path.expanduser()

    if not expanded.is_absolute():
        raise InstallerError(f"{name} must be an absolute path.")

    return expanded


def _validate_generation_name(name: str) -> None:
    """Reject generation names containing path components."""
    if not name or Path(name).name != name or name in {".", ".."}:
        raise InstallerError("The installation generation name is invalid.")


def _new_generation_name() -> str:
    """Return a unique immutable environment name."""
    return f"{__version__}-{uuid4().hex[:12]}"


def _run_checked(arguments: Sequence[str]) -> None:
    """Run one installer command without a shell."""
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"

    subprocess.run(
        list(arguments),
        check=True,
        env=environment,
    )


def _remove_empty_install_directories(
    layout: InstallLayout,
    *,
    had_previous_install: bool,
) -> None:
    """Remove empty directories left by a failed fresh install."""
    if had_previous_install:
        return

    for directory in (
        layout.generations_directory,
        layout.install_root,
    ):
        try:
            directory.rmdir()
        except OSError:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
