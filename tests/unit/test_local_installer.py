"""Tests for conservative user-local installation."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

import tunnel_toggle.local_installer as installer
from tunnel_toggle.local_installer import (
    DESKTOP_FILENAME,
    METAINFO_FILENAME,
    InstallerError,
    InstallLayout,
    InstallManifest,
    install_local,
    render_desktop_entry,
    render_launcher,
    uninstall_local,
)

PROJECT_ROOT = Path(__file__).parents[2]


def create_layout(tmp_path: Path) -> InstallLayout:
    """Create a fully isolated installation layout."""
    home = tmp_path / "home"
    home.mkdir()

    return InstallLayout.create(
        home=home,
        environment={},
        data_home=tmp_path / "data",
        bin_directory=tmp_path / "bin",
    )


def install_with_fake_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    generation_names: Sequence[str] = ("generation-one",),
) -> tuple[
    InstallLayout,
    list[tuple[str, ...]],
]:
    """Install using a fake virtual-environment command runner."""
    layout = create_layout(tmp_path)
    commands: list[tuple[str, ...]] = []
    names = iter(generation_names)

    monkeypatch.setattr(
        installer,
        "_new_generation_name",
        lambda: next(names),
    )

    def fake_run(arguments: Sequence[str]) -> None:
        command = tuple(arguments)
        commands.append(command)

        if command[1:3] == ("-m", "venv"):
            generation_directory = Path(command[3])
            bin_directory = generation_directory / "bin"
            bin_directory.mkdir(parents=True)
            python_path = bin_directory / "python"
            python_path.write_text(
                "#!/bin/sh\nexit 0\n",
                encoding="utf-8",
            )
            python_path.chmod(0o755)

    monkeypatch.setattr(
        installer,
        "_run_checked",
        fake_run,
    )

    result = install_local(
        source_root=PROJECT_ROOT,
        home=tmp_path / "home",
        environment={},
        data_home=layout.data_home,
        bin_directory=layout.bin_directory,
        source_python=Path(sys.executable),
    )

    assert result.layout == layout
    return layout, commands


def test_layout_uses_xdg_data_home_when_absolute(
    tmp_path: Path,
) -> None:
    """Absolute XDG data paths should control desktop placement."""
    home = tmp_path / "home"
    data_home = tmp_path / "custom-data"

    layout = InstallLayout.create(
        home=home,
        environment={
            "XDG_DATA_HOME": str(data_home),
        },
    )

    assert layout.data_home == data_home
    assert layout.desktop_path == (data_home / "applications" / DESKTOP_FILENAME)
    assert layout.metainfo_path == (data_home / "metainfo" / METAINFO_FILENAME)


def test_layout_ignores_relative_xdg_data_home(
    tmp_path: Path,
) -> None:
    """Relative XDG data values are invalid and should be ignored."""
    home = tmp_path / "home"

    layout = InstallLayout.create(
        home=home,
        environment={
            "XDG_DATA_HOME": "relative/data",
        },
    )

    assert layout.data_home == home / ".local" / "share"


def test_launcher_uses_absolute_environment_python(
    tmp_path: Path,
) -> None:
    """The launcher should forward arguments without evaluating them."""
    python_path = tmp_path / "environment with spaces" / "bin" / "python"

    launcher = render_launcher(python_path)

    assert launcher.startswith("#!/bin/sh\nexec ")
    assert "-m tunnel_toggle" in launcher
    assert '"$@"' in launcher
    assert str(python_path) in launcher


def test_desktop_entry_uses_absolute_managed_launcher(
    tmp_path: Path,
) -> None:
    """Installed desktop metadata should not depend on session PATH."""
    source = (
        "[Desktop Entry]\nType=Application\nExec=tunnel-toggle\nTryExec=tunnel-toggle\n"
    )
    launcher_path = tmp_path / "bin with spaces" / "tunnel-toggle"

    rendered = render_desktop_entry(
        source,
        launcher_path,
    )

    assert f'Exec="{launcher_path}"' in rendered
    assert "TryExec=" not in rendered


def test_install_creates_managed_files_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh install should create one isolated generation."""
    layout, commands = install_with_fake_commands(
        tmp_path,
        monkeypatch,
    )

    assert len(commands) == 3
    assert layout.launcher_path.is_file()
    assert layout.launcher_path.stat().st_mode & 0o111
    assert layout.desktop_path.is_file()
    assert layout.metainfo_path.is_file()
    assert layout.manifest_path.is_file()

    manifest = InstallManifest.load(layout.manifest_path)

    assert manifest.active_generation == "generation-one"
    assert layout.generation_directory("generation-one").is_dir()
    assert {path for path, _ in manifest.files} == {
        str(path) for path in layout.external_files
    }


def test_install_refuses_unmanaged_existing_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The installer must not overwrite an unrelated launcher."""
    layout = create_layout(tmp_path)
    layout.launcher_path.parent.mkdir(parents=True)
    layout.launcher_path.write_text(
        "unrelated executable\n",
        encoding="utf-8",
    )
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        installer,
        "_run_checked",
        lambda arguments: commands.append(tuple(arguments)),
    )

    with pytest.raises(
        InstallerError,
        match="not recognized as managed",
    ):
        install_local(
            source_root=PROJECT_ROOT,
            home=tmp_path / "home",
            environment={},
            data_home=layout.data_home,
            bin_directory=layout.bin_directory,
            source_python=Path(sys.executable),
        )

    assert commands == []
    assert layout.launcher_path.read_text(encoding="utf-8") == "unrelated executable\n"


def test_reinstall_replaces_old_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful update should remove its superseded environment."""
    layout = create_layout(tmp_path)
    names = iter(
        (
            "generation-one",
            "generation-two",
        )
    )

    monkeypatch.setattr(
        installer,
        "_new_generation_name",
        lambda: next(names),
    )

    def fake_run(arguments: Sequence[str]) -> None:
        command = tuple(arguments)

        if command[1:3] == ("-m", "venv"):
            generation_directory = Path(command[3])
            bin_directory = generation_directory / "bin"
            bin_directory.mkdir(parents=True)
            python_path = bin_directory / "python"
            python_path.write_text(
                "#!/bin/sh\\nexit 0\\n",
                encoding="utf-8",
            )
            python_path.chmod(0o755)

    monkeypatch.setattr(
        installer,
        "_run_checked",
        fake_run,
    )

    install_arguments = {
        "source_root": PROJECT_ROOT,
        "home": tmp_path / "home",
        "environment": {},
        "data_home": layout.data_home,
        "bin_directory": layout.bin_directory,
        "source_python": Path(sys.executable),
    }

    first_result = install_local(**install_arguments)
    second_result = install_local(**install_arguments)

    assert first_result.generation_name == "generation-one"
    assert second_result.generation_name == "generation-two"
    assert not layout.generation_directory("generation-one").exists()
    assert layout.generation_directory("generation-two").is_dir()

    manifest = InstallManifest.load(layout.manifest_path)
    assert manifest.active_generation == "generation-two"


def test_uninstall_removes_managed_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unchanged managed installation should uninstall cleanly."""
    layout, _ = install_with_fake_commands(
        tmp_path,
        monkeypatch,
    )

    uninstall_local(
        home=tmp_path / "home",
        environment={},
        data_home=layout.data_home,
        bin_directory=layout.bin_directory,
    )

    assert not layout.install_root.exists()
    assert not layout.launcher_path.exists()
    assert not layout.desktop_path.exists()
    assert not layout.metainfo_path.exists()


def test_uninstall_refuses_modified_managed_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User-modified installed metadata must not be deleted."""
    layout, _ = install_with_fake_commands(
        tmp_path,
        monkeypatch,
    )
    original_launcher = layout.launcher_path.read_bytes()
    layout.desktop_path.write_text(
        "user modification\n",
        encoding="utf-8",
    )

    with pytest.raises(
        InstallerError,
        match="was modified",
    ):
        uninstall_local(
            home=tmp_path / "home",
            environment={},
            data_home=layout.data_home,
            bin_directory=layout.bin_directory,
        )

    assert layout.install_root.exists()
    assert layout.launcher_path.read_bytes() == original_launcher
    assert layout.desktop_path.read_text(encoding="utf-8") == "user modification\n"


def test_desktop_entry_escapes_reserved_path_characters() -> None:
    """Reserved characters should remain one literal Exec argument."""
    source = (
        "[Desktop Entry]\nType=Application\nExec=tunnel-toggle\nTryExec=tunnel-toggle\n"
    )
    launcher_path = Path('/tmp/dir\\name/$money%/"quoted`/tunnel-toggle')

    rendered = render_desktop_entry(source, launcher_path)

    assert r"dir\\name" in rendered
    assert r"\$money" in rendered
    assert "%%" in rendered
    assert r"\"quoted" in rendered
    assert r"\`" in rendered
    assert "TryExec=" not in rendered
