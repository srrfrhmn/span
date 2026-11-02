from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import platform


def main() -> None:
    root = Path(__file__).parent
    try:
        __import__("PyInstaller")
    except ImportError:
        raise SystemExit(
            "PyInstaller is required only for packaging.\n"
            "Install it with: python -m pip install pyinstaller"
        )

    separator = ";" if platform.system() == "Windows" else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        "span",
        "--add-data",
        f"{root / 'assets'}{separator}assets",
    ]
    if platform.system() == "Windows":
        python_root = Path(sys.base_prefix)
        command.extend(
            [
                "--icon",
                str(root / "assets" / "span.ico"),
                "--version-file",
                str(root / "packaging" / "windows-app-version.txt"),
                "--additional-hooks-dir",
                str(root / "packaging_hooks"),
                "--runtime-hook",
                str(root / "packaging_hooks" / "pyi_rth_span_tk.py"),
                "--hidden-import",
                "tkinter",
                "--hidden-import",
                "_tkinter",
                "--add-binary",
                f"{python_root / 'DLLs' / 'tcl86t.dll'}{separator}.",
                "--add-binary",
                f"{python_root / 'DLLs' / 'tk86t.dll'}{separator}.",
                "--add-data",
                f"{python_root / 'tcl' / 'tcl8.6'}{separator}_tcl_data",
                "--add-data",
                f"{python_root / 'tcl' / 'tk8.6'}{separator}_tk_data",
                "--add-data",
                f"{python_root / 'tcl' / 'tcl8'}{separator}tcl8",
            ]
        )
    command.append(str(root / "span.py"))
    subprocess.run(command, cwd=root, check=True)
    suffix = ".exe" if platform.system() == "Windows" else ""
    print(f"Built span in {root / 'dist' / ('span' + suffix)}")

    if platform.system() == "Windows":
        installer_command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            "span-setup",
            "--icon",
            str(root / "assets" / "span.ico"),
            "--version-file",
            str(root / "packaging" / "windows-setup-version.txt"),
            "--additional-hooks-dir",
            str(root / "packaging_hooks"),
            "--runtime-hook",
            str(root / "packaging_hooks" / "pyi_rth_span_tk.py"),
            "--hidden-import",
            "tkinter",
            "--hidden-import",
            "_tkinter",
            "--add-binary",
            f"{python_root / 'DLLs' / 'tcl86t.dll'}{separator}.",
            "--add-binary",
            f"{python_root / 'DLLs' / 'tk86t.dll'}{separator}.",
            "--add-data",
            f"{python_root / 'tcl' / 'tcl8.6'}{separator}_tcl_data",
            "--add-data",
            f"{python_root / 'tcl' / 'tk8.6'}{separator}_tk_data",
            "--add-data",
            f"{python_root / 'tcl' / 'tcl8'}{separator}tcl8",
            "--add-data",
            f"{root / 'assets'}{separator}assets",
            "--add-binary",
            f"{root / 'dist' / 'span.exe'}{separator}span_payload",
            str(root / "installer.py"),
        ]
        subprocess.run(installer_command, cwd=root, check=True)
        print(f"Built installer in {root / 'dist' / 'span-setup.exe'}")


if __name__ == "__main__":
    main()
