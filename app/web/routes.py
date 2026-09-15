import io
import json
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import db
from ..collect import pastebox
from ..collect.runner import Runner
from ..collect.store import save_item
from ..dedup import url_fingerprint

JOB_TYPES = [("lawfirm", "律所"), ("public", "体制内"), ("legal_counsel", "法务"),
             ("intern", "实习"), ("unknown", "未分类")]
APP_STATUSES = ["待投", "已投", "笔试", "面试", "Offer", "拒"]
CITIES = ["广州", "深圳", "珠海", "佛山", "惠州", "东莞", "中山", "江门", "肇庆", "韶关"]
NOTICE_KINDS = [("opening", "可投递"), ("result", "结果公示"), ("info", "其他信息")]


def mount(app: FastAPI, tpl_dir: str) -> Jinja2Templates:
    templates = Jinja2Templates(directory=tpl_dir)
    router = APIRouter()

    def render(name: str, request: Request, **ctx):
        ctx.setdefault("request", request)
        ctx.setdefault("job_types", JOB_TYPES)
        ctx.setdefault("cities", CITIES)
        ctx.setdefault("app_statuses", APP_STATUSES)
        ctx.setdefault("notice_kinds", NOTICE_KINDS)
        ctx["urgent"] = request.app.state.conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE deadline IS NOT NULL "
            "AND deadline BETWEEN date('now') AND date('now','+3 day') "
            "AND status != 'archived'").fetchone()["c"]
        return templates.TemplateResponse(request, name, ctx)

    def list_query(request: Request):
        q = dict(request.query_params)
        where, params = ["j.status != 'archived'"], []
        # 默认只看"可投递"的岗位；政务渠道里大量事后结果公示对求职者没有价值
        kind = q.get("notice_kind")
        if kind == "all":
            pass
        elif kind:
            where.append("j.notice_kind=?")
            params.append(kind)
        else:
            where.append("j.notice_kind='opening'")
        if q.get("job_type"):
            where.append("j.job_type=?")
            params.append(q["job_type"])
        if q.get("city"):
            where.append("j.city LIKE ?")
            params.append(f"%{q['city']}%")
        if q.get("status"):
            where.append("j.status=?")
            params.append(q["status"])
        kw = (q.get("q") or "").strip()
        join = ""
        if kw:
            if len(kw) >= 3 and db.has_fts(request.app.state.conn):
                join = "JOIN jobs_fts f ON f.job_id=j.id AND jobs_fts MATCH ?"
                params = ['"%s"' % kw.replace('"', " ")] + params
            else:
                where.append("j.search_text LIKE ?")
                params.append(f"%{kw}%")
        return join, where, params, q

    @router.get("/", response_class=HTMLResponse)
    def home(request: Request):
        join, where, params, q = list_query(request)
        order = ("ORDER BY CASE WHEN j.deadline IS NULL THEN 1 ELSE 0 END, "
                 "j.deadline ASC, j.publish_date DESC, j.id DESC")
        rows = request.app.state.conn.execute(
            f"SELECT j.* FROM jobs j {join} WHERE {' AND '.join(where)} {order} LIMIT 200",
            params).fetchall()
        return render("list.html", request, jobs=rows, q=q)

    @router.get("/jobs/{job_id}", response_class=HTMLResponse)
    def detail(job_id: int, request: Request):
        conn = request.app.state.conn
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            return RedirectResponse("/", status_code=303)
        app_row = conn.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
        sources = conn.execute("SELECT * FROM job_sources WHERE job_id=?", (job_id,)).fetchall()
        snapshot_text = None
        if job["snapshot_path"] and Path(job["snapshot_path"]).exists():
            snapshot_text = Path(job["snapshot_path"]).read_text("utf-8", errors="replace")
        return render("detail.html", request, job=job, app_row=app_row,
                      sources=sources, snapshot_text=snapshot_text)

    @router.post("/jobs/{job_id}/status")
    def set_status(job_id: int, request: Request, status: str = Form(...)):
        request.app.state.conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        request.app.state.conn.commit()
        return RedirectResponse("/", status_code=303)

    @router.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
    def edit(job_id: int, request: Request):
        job = request.app.state.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return render("confirm.html", request, job=job)

    @router.post("/jobs/{job_id}/confirm")
    def confirm(job_id: int, request: Request, title: str = Form(...),
                city: str = Form(""), deadline: str = Form(""),
                job_type: str = Form("unknown"), notes: str = Form("")):
        conn = request.app.state.conn
        conn.execute(
            "UPDATE jobs SET title=?, city=?, deadline=NULLIF(?,''), job_type=?, notes=?, "
            "status='new', needs_review=0 WHERE id=?",
            (title, city or None, deadline, job_type, notes, job_id))
        conn.commit()
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    @router.post("/jobs/{job_id}/apply")
    def apply(job_id: int, request: Request):
        conn = request.app.state.conn
        conn.execute("INSERT OR IGNORE INTO applications(job_id) VALUES(?)", (job_id,))
        conn.commit()
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    @router.post("/applications/{app_id}/status")
    def app_status(app_id: int, request: Request, status: str = Form(...),
                   note: str = Form("")):
        conn = request.app.state.conn
        row = conn.execute("SELECT timeline FROM applications WHERE id=?", (app_id,)).fetchone()
        if row:
            tl = json.loads(row["timeline"] or "[]")
            tl.append({"at": date.today().isoformat(), "status": status, "note": note})
            conn.execute("UPDATE applications SET status=?, timeline=? WHERE id=?",
                         (status, json.dumps(tl, ensure_ascii=False), app_id))
            conn.commit()
        return RedirectResponse("/board", status_code=303)

    @router.get("/board", response_class=HTMLResponse)
    def board(request: Request):
        conn = request.app.state.conn
        cols = {}
        for s in APP_STATUSES:
            cols[s] = conn.execute(
                "SELECT a.id aid, a.status, a.notes, a.timeline, j.* FROM applications a "
                "JOIN jobs j ON j.id=a.job_id WHERE a.status=? ORDER BY a.id DESC",
                (s,)).fetchall()
        return render("board.html", request, cols=cols)

    @router.get("/paste", response_class=HTMLResponse)
    def paste_form(request: Request):
        return render("paste.html", request, error=None)

    @router.post("/paste")
    def paste(request: Request, url: str = Form(...)):
        try:
            draft = pastebox.collect_url(url.strip())
        except Exception as e:  # noqa: BLE001
            return render("paste.html", request, error=f"抓取失败：{e}")
        conn = request.app.state.conn
        _, jid = save_item(conn, draft)
        if jid is None:
            return render("paste.html", request, error="该链接已存在")
        return RedirectResponse(f"/jobs/{jid}/edit", status_code=303)

    @router.get("/health", response_class=HTMLResponse)
    def health(request: Request):
        conn = request.app.state.conn
        sources = conn.execute("SELECT * FROM sources ORDER BY slug").fetchall()
        logs = conn.execute("SELECT * FROM collect_logs ORDER BY id DESC LIMIT 50").fetchall()
        return render("health.html", request, sources=sources, logs=logs)

    @router.post("/collect/run")
    def collect_run(request: Request, slug: str = Form("")):
        r = Runner(request.app.state.conn).run_all([slug] if slug else None)
        return RedirectResponse(f"/health?inserted={r.get('inserted', 0)}", status_code=303)

    @router.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        toast = db.get_setting(request.app.state.conn, "toast_enabled", "0")
        return render("settings.html", request, toast_enabled=toast)

    @router.post("/settings")
    def settings_save(request: Request, toast_enabled: str = Form("0")):
        db.set_setting(request.app.state.conn, "toast_enabled", toast_enabled)
        return RedirectResponse("/settings", status_code=303)

    app.include_router(router)
    return templates


def export_xlsx(app: FastAPI, notice_kind: str | None = None) -> Response:
    """导出汇总表。默认只导"可投递"岗位，与首页默认视图一致；
    需要全部稿件（含结果公示）时传 notice_kind=all。"""
    from openpyxl import Workbook

    conn = app.state.conn
    wb = Workbook()
    ws = wb.active
    ws.title = "招聘信息汇总"
    ws.append(["序号", "标题", "单位", "类型", "城市", "发布日期", "截止日期",
               "性质", "状态", "链接", "备注"])
    tmap = dict(JOB_TYPES)
    kmap = dict(NOTICE_KINDS)
    where, params = ["status != 'archived'"], []
    if notice_kind == "all":
        pass
    elif notice_kind in kmap:
        where.append("notice_kind=?")
        params.append(notice_kind)
    else:
        where.append("notice_kind='opening'")
    rows = conn.execute(
        f"SELECT * FROM jobs WHERE {' AND '.join(where)} "
        "ORDER BY deadline IS NULL, deadline, id", params).fetchall()
    for i, r in enumerate(rows, 1):
        ws.append([i, r["title"], r["org"] or "", tmap.get(r["job_type"], r["job_type"]),
                   r["city"] or "", r["publish_date"] or "", r["deadline"] or "",
                   kmap.get(r["notice_kind"], r["notice_kind"]),
                   r["status"], r["url"], r["notes"] or ""])
    buf = io.BytesIO()
    wb.save(buf)
    name = quote("招聘信息汇总表.xlsx")
    return Response(
        buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"})
