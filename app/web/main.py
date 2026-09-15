import contextlib
import os
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .. import db
from ..collect.runner import Runner
from . import routes


def _deadline_class_filter():
    def dcolor(deadline: str | None) -> str:
        if not deadline:
            return ""
        try:
            d = date.fromisoformat(deadline)
        except ValueError:
            return ""
        today = date.today()
        if d <= today + timedelta(days=3):
            return "red"
        if d <= today + timedelta(days=7):
            return "yellow"
        return ""
    return dcolor


def _urgency_filter():
    """把截止日期折算成行首细条的语义类：3 天内 / 7 天内。

    放在 Python 端算，模板里就不用做日期比较（Jinja 里做容易出错且难读）。
    """
    def urgency(deadline: str | None) -> str:
        if not deadline:
            return ""
        try:
            d = date.fromisoformat(deadline)
        except ValueError:
            return ""
        today = date.today()
        if d <= today + timedelta(days=3):
            return "u3"
        if d <= today + timedelta(days=7):
            return "u7"
        return ""
    return urgency


def _ts_filter():
    """把 ISO 时间戳压成 MM-DD HH:MM。

    原始值形如 2026-09-15T19:45:56，在表格里又长又挤，会把"最近错误"列压没。
    """
    def ts(v) -> str:
        if not v:
            return "从未"
        s = str(v).replace("T", " ")
        return s[5:16] if len(s) >= 16 else s
    return ts


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or str(Path(__file__).resolve().parent.parent.parent / "data" / "job.db")
    conn = db.connect(db_path)
    db.init_db(conn)

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def daily():
        Runner(conn).run_all()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.auto_archive(conn)
        if os.environ.get("APP_DISABLE_SCHEDULER") != "1":
            scheduler.add_job(daily, "cron", hour=8, minute=5, id="daily_collect")
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(lifespan=lifespan)
    app.state.conn = conn

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    templates = routes.mount(app, str(Path(__file__).parent / "templates"))
    templates.env.filters["dcolor"] = _deadline_class_filter()
    templates.env.filters["urgency"] = _urgency_filter()
    templates.env.filters["ts"] = _ts_filter()

    @app.get("/export.xlsx")
    def export(notice_kind: str | None = None):
        return routes.export_xlsx(app, notice_kind)

    return app
