"""
مزامنة المشروع تلقائياً مع GitHub.

يستخدم هذا السكريبت GITHUB_TOKEN المخزّن في متغيرات البيئة
لرفع التغييرات تلقائياً إلى المستودع عند بدء التطبيق أو تغيير الملفات.
"""

import os
import time
import logging
import threading
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

IGNORE_PATHS = {
    ".git", "__pycache__", ".pyc", "node_modules",
    ".env", "*.log", ".DS_Store", "*.pyc",
}


def _should_ignore(path: str) -> bool:
    p = Path(path)
    for part in p.parts:
        if part in IGNORE_PATHS:
            return True
    return p.suffix in {".pyc", ".log"}


def _run_git(args: list[str], cwd: str = ".") -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        logger.error("انتهت مهلة أمر git.")
        return False, "timeout"
    except Exception as e:
        logger.error("خطأ أثناء تنفيذ git: %s", e)
        return False, str(e)


def configure_git_remote() -> bool:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.warning("⚠️  GITHUB_TOKEN أو GITHUB_REPO غير محددين — المزامنة مُعطَّلة.")
        return False

    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"

    ok, out = _run_git(["remote", "get-url", "origin"])
    if ok:
        _run_git(["remote", "set-url", "origin", remote_url])
    else:
        _run_git(["remote", "add", "origin", remote_url])

    _run_git(["config", "user.email", "clavo-bot@users.noreply.github.com"])
    _run_git(["config", "user.name", "كلافو — مزامنة تلقائية"])
    logger.info("✅ تم ضبط إعدادات git بنجاح.")
    return True


def commit_and_push(message: str = "مزامنة تلقائية من كلافو") -> bool:
    if not GITHUB_TOKEN:
        return False

    _run_git(["add", "-A"])
    ok_status, status_out = _run_git(["status", "--porcelain"])
    if not status_out.strip():
        logger.debug("لا توجد تغييرات لرفعها.")
        return True

    ok_commit, commit_out = _run_git(["commit", "-m", message])
    if not ok_commit:
        logger.warning("لم يتم إنشاء commit: %s", commit_out.strip())
        return False

    ok_push, push_out = _run_git(["push", "origin", "HEAD"])
    if ok_push:
        logger.info("✅ تمت المزامنة مع GitHub بنجاح.")
    else:
        logger.error("❌ فشل الرفع إلى GitHub: %s", push_out.strip())
    return ok_push


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, debounce_seconds: float = 5.0):
        self._debounce = debounce_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _schedule_sync(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._do_sync)
            self._timer.start()

    def _do_sync(self):
        logger.info("🔄 رصد تغييرات — بدء المزامنة مع GitHub...")
        commit_and_push("تحديث تلقائي عند اكتشاف تغييرات")

    def on_modified(self, event):
        if not event.is_directory and not _should_ignore(event.src_path):
            self._schedule_sync()

    def on_created(self, event):
        if not event.is_directory and not _should_ignore(event.src_path):
            self._schedule_sync()

    def on_deleted(self, event):
        if not event.is_directory and not _should_ignore(event.src_path):
            self._schedule_sync()


def start_sync_watcher(watch_path: str = ".") -> Observer | None:
    if not configure_git_remote():
        return None

    logger.info("🔄 مزامنة أولية عند بدء التطبيق...")
    commit_and_push("بدء تشغيل كلافو — مزامنة أولية")

    handler = ChangeHandler(debounce_seconds=10.0)
    observer = Observer()
    observer.schedule(handler, path=watch_path, recursive=True)
    observer.start()
    logger.info("👁️  مراقب الملفات نشط — سيتم رفع أي تغييرات تلقائياً.")
    return observer


def stop_sync_watcher(observer: Observer | None) -> None:
    if observer:
        observer.stop()
        observer.join()
        logger.info("تم إيقاف مراقب الملفات.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("تشغيل أداة المزامنة مباشرة...")
    configure_git_remote()
    commit_and_push("مزامنة يدوية من sync_github.py")
