import contextlib
import os
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

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

    templates = routes.mount(app, str(Path(__file__).parent / "templates"))
    templates.env.filters["dcolor"] = _deadline_class_filter()

    @app.get("/export.xlsx")
    def export(notice_kind: str | None = None):
        return routes.export_xlsx(app, notice_kind)

    return app
