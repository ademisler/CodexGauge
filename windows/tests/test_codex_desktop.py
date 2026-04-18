from __future__ import annotations

import base64
import unittest

from codexcontrol_windows.codex_desktop import build_restart_launcher, build_restart_script, encode_powershell_script


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

    def test_build_restart_launcher_invokes_powershell_file(self) -> None:
        launcher = build_restart_launcher()

        self.assertIn("start \"\" /min", launcher)
        self.assertIn("powershell.exe", launcher.lower())
        self.assertIn("-ExecutionPolicy Bypass -File", launcher)


if __name__ == "__main__":
    unittest.main()
