import contextlib
import os
from datetime import date, datetime, timedelta
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
        if d < today:
            return ""   # 已过期：不再红色告警（横幅口径只含今天起的 3 天）
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
        if d < today:
            return ""   # 已过期
        if d <= today + timedelta(days=3):
            return "u3"
        if d <= today + timedelta(days=7):
            return "u7"
        return ""
    return urgency


def _deadline_left_filter():
    """把截止日期折算成"剩余几天"，只用在鼠标悬停提示上。

    列表里的日期是 MM-DD 短格式，光看数字判断不出还剩几天；悬停补一句更直接。
    """
    def dleft(deadline: str | None) -> str:
        if not deadline:
            return ""
        try:
            d = date.fromisoformat(deadline)
        except ValueError:
            return ""
        n = (d - date.today()).days
        if n < 0:
            return "（已截止）"
        if n == 0:
            return "（今天截止）"
        return f"（剩余 {n} 天）"
    return dleft


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


def _toast(conn, text: str) -> None:
    """发 Windows 桌面通知；未装 win11toast 或未开启时静默跳过。"""
    if db.get_setting(conn, "toast_enabled", "0") != "1":
        return
    try:
        from win11toast import toast
        toast("法学招聘中台", text)
    except Exception:  # noqa: BLE001 未安装通知依赖则跳过
        pass


def _collect_summary(conn, total: dict) -> str:
    """通知正文：让用户不开网页就知道"今天有没有必要打开看"。"""
    row = conn.execute(
        "SELECT"
        "  SUM(deadline IS NOT NULL AND deadline BETWEEN date('now') AND date('now')) AS d0,"
        "  SUM(deadline IS NOT NULL AND deadline BETWEEN date('now') AND date('now','+3 day')) AS d3"
        " FROM jobs WHERE notice_kind='opening' AND status != 'archived'").fetchone()
    parts = [f"新增 {total.get('inserted', 0)} 条"]
    if row["d0"]:
        parts.append(f"今天截止 {row['d0']} 条")
    if row["d3"]:
        parts.append(f"3 天内截止 {row['d3']} 条")
    if total.get("failed"):
        parts.append(f"{total['failed']} 个源采集失败")
    return "，".join(parts)


def _needs_catchup(conn) -> bool:
    """上次采集是不是在今天之前（服务不是天天开着，错过 08:05 要补）。"""
    row = conn.execute("SELECT MAX(ran_at) m FROM collect_logs").fetchone()
    if not row or not row["m"]:
        return True
    return str(row["m"])[:10] < date.today().isoformat()


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or str(Path(__file__).resolve().parent.parent.parent / "data" / "job.db")
    conn = db.connect(db_path)
    db.init_db(conn)

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def daily():
        total = Runner(conn).run_all()
        _toast(conn, _collect_summary(conn, total))

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.auto_archive(conn)
        if os.environ.get("APP_DISABLE_SCHEDULER") != "1":
            scheduler.add_job(daily, "cron", hour=8, minute=5, id="daily_collect")
            # 晚间第二轮：当天下午发布的公告，不用等到第二天早上才能看到
            scheduler.add_job(daily, "cron", hour=20, minute=5, id="evening_collect")
            # 错过当天采集（电脑晚开机）就立即补一轮：增量采集靠 URL 指纹，不会重复
            if _needs_catchup(conn):
                scheduler.add_job(daily, id="catchup_collect",
                                  next_run_time=datetime.now())
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)
        from ..collect.http import close_clients
        close_clients()

    app = FastAPI(lifespan=lifespan)
    app.state.conn = conn

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    templates = routes.mount(app, str(Path(__file__).parent / "templates"))
    templates.env.filters["dcolor"] = _deadline_class_filter()
    templates.env.filters["urgency"] = _urgency_filter()
    templates.env.filters["dleft"] = _deadline_left_filter()
    templates.env.filters["ts"] = _ts_filter()

    @app.get("/export.xlsx")
    def export(notice_kind: str | None = None):
        return routes.export_xlsx(app, notice_kind)

    return app
