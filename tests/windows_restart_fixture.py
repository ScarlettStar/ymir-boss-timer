"""Used only by the Windows CI build to exercise a real frozen restart."""
import os
import shutil
import sys
from pathlib import Path
import ymir_boss_timer as ymir

if os.environ.get("YMIR_RESTART_FIXTURE_CHILD") == "1":
    app = ymir.BossTimerApp()
    app.after(5000, app.quit_app)
    app.mainloop()
else:
    os.environ["YMIR_RESTART_FIXTURE_CHILD"] = "1"
    target = Path(sys.executable)
    stage = target.with_name(target.name + ".new")
    shutil.copy2(target, stage)
    app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
    app.latest_release = {"version": "v" + ymir.APP_VERSION}
    app.quit_app = lambda: sys.exit(0)
    app._launch_update(stage, target)
