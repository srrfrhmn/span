from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
import traceback
import winreg
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Callable


APP_NAME = "span"
VERSION = "1.0.0"
APP_ID = "span.habits.desktop"
StatusCallback = Callable[[str], None]


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return root / relative


def install_dir() -> Path:
    local_app_data = Path(os.environ["LOCALAPPDATA"])
    return local_app_data / "Programs" / APP_NAME


def shortcut_path() -> Path:
    app_data = Path(os.environ["APPDATA"])
    return app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "span.lnk"


def log_path() -> Path:
    path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME / "installer.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_error(error: BaseException) -> Path:
    path = log_path()
    with path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {error}\n")
        traceback.print_exception(type(error), error, error.__traceback__, file=log)
    return path


def quote_powershell(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def stop_running_app(target: Path) -> None:
    script = (
        f"$target = [IO.Path]::GetFullPath({quote_powershell(target)}); "
        "Get-Process -Name 'span' -ErrorAction SilentlyContinue | "
        "Where-Object { "
        "  $_.Path -and "
        "  [string]::Equals([IO.Path]::GetFullPath($_.Path), $target, "
        "  [StringComparison]::OrdinalIgnoreCase) "
        "} | Stop-Process -Force"
    )
    subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def replace_with_retry(source: Path, target: Path) -> None:
    last_error: OSError | None = None
    for _ in range(20):
        try:
            os.replace(source, target)
            return
        except OSError as error:
            last_error = error
            time.sleep(0.15)
    if last_error is not None:
        raise last_error


def create_shortcut(target: Path) -> None:
    shortcut = shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$link = $shell.CreateShortcut({quote_powershell(shortcut)}); "
        f"$link.TargetPath = {quote_powershell(target)}; "
        f"$link.WorkingDirectory = {quote_powershell(target.parent)}; "
        f"$link.IconLocation = {quote_powershell(str(target) + ',0')}; "
        "$link.Description = 'A quiet, local habit tracker'; "
        "$link.Save()"
    )
    subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def register_uninstaller(target_dir: Path, uninstaller: Path, app_exe: Path) -> None:
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        values = {
            "DisplayName": "span",
            "DisplayVersion": VERSION,
            "DisplayIcon": str(app_exe),
            "Publisher": "span",
            "InstallLocation": str(target_dir),
            "UninstallString": f'"{uninstaller}" --uninstall',
            "QuietUninstallString": f'"{uninstaller}" --uninstall --quiet',
        }
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        estimated_kb = sum(
            path.stat().st_size for path in target_dir.glob("*") if path.is_file()
        ) // 1024
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, estimated_kb)


def notify_shell() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except (AttributeError, OSError):
        pass


def install(status: StatusCallback | None = None) -> Path:
    update_status = status or (lambda _message: None)
    target_dir = install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    app_exe = target_dir / "span.exe"
    uninstaller = target_dir / "Uninstall span.exe"
    staged_app = target_dir / ".span-installing.exe"
    staged_uninstaller = target_dir / ".span-uninstaller-installing.exe"

    update_status("Preparing span...")
    shutil.copy2(resource_path("span_payload/span.exe"), staged_app)
    shutil.copy2(Path(sys.executable), staged_uninstaller)

    update_status("Closing the installed copy of span...")
    stop_running_app(app_exe)
    replace_with_retry(staged_app, app_exe)
    replace_with_retry(staged_uninstaller, uninstaller)

    update_status("Creating the Start Menu entry...")
    create_shortcut(app_exe)
    update_status("Registering span with Windows...")
    register_uninstaller(target_dir, uninstaller, app_exe)
    notify_shell()
    return app_exe


def unregister() -> None:
    try:
        shortcut_path().unlink()
    except FileNotFoundError:
        pass
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass
    notify_shell()


def uninstall(quiet: bool = False) -> None:
    if not quiet:
        root = tk.Tk()
        root.withdraw()
        if not messagebox.askyesno(
            "Uninstall span",
            "Remove span from this computer?\n\nYour habit data will be kept.",
        ):
            root.destroy()
            return
        root.destroy()
    unregister()
    target = install_dir()
    script = (
        "Start-Sleep -Milliseconds 800; "
        f"Remove-Item -LiteralPath {quote_powershell(target)} -Recurse -Force"
    )
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


class Installer:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Install span")
        self.root.geometry("520x360")
        self.root.resizable(False, False)
        self.root.configure(bg="#111111")
        try:
            icon = tk.PhotoImage(file=str(resource_path("assets/span.png")))
            self.root.iconphoto(True, icon)
            self.root._icon = icon
        except tk.TclError:
            pass
        self._build()

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg="#111111", padx=54, pady=42)
        shell.pack(fill="both", expand=True)
        tk.Label(
            shell,
            text="span",
            bg="#111111",
            fg="#f5f5f5",
            font=("Segoe UI Variable Display", 28, "bold"),
        ).pack(anchor="w")
        tk.Label(
            shell,
            text="A quiet place for the habits that matter.",
            bg="#111111",
            fg="#999999",
            font=("Segoe UI Variable", 11),
        ).pack(anchor="w", pady=(8, 30))
        card = tk.Frame(
            shell,
            bg="#191919",
            padx=20,
            pady=18,
            highlightthickness=1,
            highlightbackground="#353535",
        )
        card.pack(fill="x")
        tk.Label(
            card,
            text="Install for this Windows account",
            bg="#191919",
            fg="#f5f5f5",
            font=("Segoe UI Variable", 11, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=r"%LOCALAPPDATA%\Programs\span",
            bg="#191919",
            fg="#999999",
            font=("Segoe UI Variable", 9),
        ).pack(anchor="w", pady=(5, 0))
        self.status = tk.Label(
            shell,
            text="",
            bg="#111111",
            fg="#999999",
            font=("Segoe UI Variable", 9),
        )
        self.status.pack(anchor="w", pady=(18, 8))
        self.button = tk.Button(
            shell,
            text="Install span",
            command=self._install,
            bg="#f5f5f5",
            fg="#111111",
            activebackground="#dddddd",
            activeforeground="#111111",
            relief="flat",
            bd=0,
            padx=22,
            pady=11,
            cursor="hand2",
            font=("Segoe UI Variable", 10, "bold"),
        )
        self.button.pack(anchor="e")

    def _install(self) -> None:
        self.button.configure(state="disabled", text="Installing...")
        self._set_status("Preparing span...")
        try:
            app_exe = install(self._set_status)
        except Exception as error:
            details = log_error(error)
            self.button.configure(state="normal", text="Try again")
            self.status.configure(text="Installation failed.")
            messagebox.showerror(
                "Install span",
                "span could not be installed.\n\n"
                "Close span and try again. Technical details were saved to:\n"
                f"{details}",
            )
            return
        self.status.configure(text="Installed. span is now available in Windows Search.")
        self.button.configure(
            state="normal",
            text="Open span",
            command=lambda: subprocess.Popen([app_exe]),
        )

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)
        self.root.update_idletasks()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    if "--uninstall" in sys.argv:
        uninstall("--quiet" in sys.argv)
        return
    if "--install" in sys.argv:
        try:
            install()
        except Exception as error:
            log_error(error)
            raise SystemExit(1) from error
        return
    Installer().run()


if __name__ == "__main__":
    main()
