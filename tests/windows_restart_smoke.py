"""Build and restart the real updater in a onefile Windows fixture; no Release."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed", "--name", "YmirBossTimer",
            "--paths", str(Path.cwd()),
            "--distpath", str(root / "dist"),
            "--workpath", str(root / "build"),
            "--specpath", str(root),
            "tests/windows_restart_fixture.py",
        ], check=True)
        env = os.environ.copy()
        env["APPDATA"] = str(root / "data")
        env.pop("YMIR_RESTART_FIXTURE_CHILD", None)
        target = root / "dist" / "YmirBossTimer.exe"
        log = root / "data" / "YmirBossTimer" / "update.log"
        # No user data and no network access are required by this fixture.
        log.parent.mkdir(parents=True)
        process = subprocess.Popen([str(target)], env=env)
        try:
            process.wait(timeout=45)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                text = log.read_text(encoding="utf-8-sig") if log.exists() else ""
                if "Falha:" in text:
                    raise AssertionError(text)
                if "Atualização confirmada:" in text:
                    print(text)
                    time.sleep(8)  # Let the fixture close and release the EXE.
                    return
                time.sleep(1)
            raise AssertionError("No restart confirmation. " + str(log))
        finally:
            subprocess.run(["taskkill", "/IM", "YmirBossTimer.exe", "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)

if __name__ == "__main__":
    main()
