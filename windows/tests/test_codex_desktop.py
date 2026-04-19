from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import patch

from codexcontrol_windows.codex_desktop import (
    build_restart_command,
    build_restart_script,
    encode_powershell_script,
    restart_codex_desktop,
)


class CodexDesktopTests(unittest.TestCase):
    def test_build_restart_script_includes_restart_flow(self) -> None:
        script = build_restart_script(1.25)

        self.assertIn("Write-Log", script)
        self.assertIn("Get-CimInstance Win32_Process", script)
        self.assertIn("Get-AppxPackage", script)
        self.assertIn("taskkill.exe /PID", script)
        self.assertIn("Stop-Process -Id $_.ProcessId -Force", script)
        self.assertIn("Start-Process -FilePath $launcherPath", script)
        self.assertIn("Start-Sleep -Milliseconds 1250", script)

    def test_encode_powershell_script_round_trips_utf16le(self) -> None:
        script = "Start-Process -FilePath 'Codex.exe'"

        encoded = encode_powershell_script(script)
        decoded = base64.b64decode(encoded).decode("utf-16le")

        self.assertEqual(decoded, script)

    def test_build_restart_command_invokes_hidden_powershell_file(self) -> None:
        command = build_restart_command(Path("C:/temp/restart.ps1"))

        self.assertTrue(command[0].lower().endswith("powershell.exe"))
        self.assertIn("-WindowStyle", command)
        self.assertIn("Hidden", command)
        self.assertEqual(command[-2], "-File")
        self.assertTrue(command[-1].lower().endswith("temp\\restart.ps1"))

    def test_restart_codex_desktop_launches_hidden_powershell_without_startfile(self) -> None:
        with (
            patch("codexcontrol_windows.codex_desktop.ensure_directories"),
            patch("pathlib.Path.write_text"),
            patch("codexcontrol_windows.codex_desktop._launch_hidden_powershell") as launch_hidden,
        ):
            restart_codex_desktop()

        launch_hidden.assert_called_once()


if __name__ == "__main__":
    unittest.main()
