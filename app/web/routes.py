import io
import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import db
from ..classify import CITIES
from ..collect import pastebox
from ..collect.runner import Runner
from ..collect.store import _search_text, reindex_fts, save_item
from ..dedup import url_fingerprint

# "unknown" 显示成"其他"而不是"未分类"：规则修好后剩下的确实是
# 律所/体制内/法务/实习之外的岗位（如企业综合岗），是一个正常分类，不是失败。
JOB_TYPES = [("lawfirm", "律所"), ("public", "体制内"), ("legal_counsel", "法务"),
             ("intern", "实习"), ("unknown", "其他")]
APP_STATUSES = ["待投", "已投", "笔试", "面试", "Offer", "拒"]
NOTICE_KINDS = [("opening", "可投递"), ("result", "结果公示"), ("info", "其他信息")]
EMPLOYMENT_TYPES = [("编制", "编制"), ("合同制", "合同制"), ("派遣", "派遣"),
                    ("长期有效", "长期有效")]

# 用户口语和公告用词的差异会直接漏召回：搜"律所"命中 28 条，"律师事务所"61 条。
# 命中任一词时把同组词一起查（OR），分组按首个词识别。
SYNONYM_GROUPS = [
    ["律所", "律师事务所"],
    ["法务", "法律事务", "法务岗"],
    ["书记员", "聘用制书记员", "劳动合同制书记员"],
    ["律师", "执业律师", "授薪律师", "专职律师"],
    ["选调", "选调生"],
    ["应届", "应届生", "应届毕业生", "2026届", "2027届"],
    ["编制", "在编", "事业编制", "公务员编制"],
]


def _search_terms(kw: str) -> list[str]:
    """把用户输入展开成一组同义词；不在任何同义词组里就按原词查。"""
    for group in SYNONYM_GROUPS:
        if kw in group:
            return list(dict.fromkeys(group))
    return [kw]


def mount(app: FastAPI, tpl_dir: str) -> Jinja2Templates:
    templates = Jinja2Templates(directory=tpl_dir)
    router = APIRouter()
    # 静态资源版本号取 CSS 与 JS 的 mtime：改完刷新页面即生效，不会被浏览器缓存卡住
    static_dir = Path(tpl_dir).parent / "static"

    def asset_version() -> str:
        stamps = []
        for name in ("style.css", "app.js"):
            try:
                stamps.append(int((static_dir / name).stat().st_mtime))
            except OSError:
                pass
        return f"{max(stamps) if stamps else 1}"

    def _safe_local(url: str | None, request: Request) -> str | None:
        """只接受站内地址（相对路径，或与本站同 host 的绝对 URL），防 open redirect。"""
        if not url:
            return None
        p = urlsplit(url)
        if p.scheme and p.netloc:
            # Referer 是绝对 URL：只放行与本站同 host 的
            req = urlsplit(str(request.base_url))
            if p.netloc != req.netloc:
                return None
        elif p.scheme or p.netloc:
            return None
        if not p.path.startswith("/"):
            return None
        return p.path + (f"?{p.query}" if p.query else "")

    def redirect_back(request: Request, fallback: str = "/",
                      form_back: str | None = None) -> RedirectResponse:
        """操作完回到来源页（带筛选参数）。

        之前一律 303 回 `/`：用户在"律所+广州"下浏览，点一次"已读"筛选就全丢了。
        Referer 对同源 POST 一定带，所以列表行/详情页的表单都能正确回跳。
        """
        target = (_safe_local(form_back, request)
                  or _safe_local(request.headers.get("referer"), request))
        return RedirectResponse(target or fallback, status_code=303)

    def render(name: str, request: Request, **ctx):
        ctx.setdefault("request", request)
        ctx.setdefault("job_types", JOB_TYPES)
        ctx.setdefault("cities", CITIES)
        ctx.setdefault("app_statuses", APP_STATUSES)
        ctx.setdefault("notice_kinds", NOTICE_KINDS)
        ctx.setdefault("employment_types", EMPLOYMENT_TYPES)
        ctx.setdefault("asset_v", asset_version())
        conn = request.app.state.conn
        ctx["urgent"] = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE deadline IS NOT NULL "
            "AND deadline BETWEEN date('now') AND date('now','+3 day') "
            "AND status != 'archived'").fetchone()["c"]
        # 无截止日的可投递岗位不会进临期提醒，是最容易被漏看的一批，得单独报数
        ctx["no_deadline"] = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE notice_kind='opening' "
            "AND deadline IS NULL AND status != 'archived'").fetchone()["c"]
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
        if q.get("employment_type"):
            where.append("j.employment_type=?")
            params.append(q["employment_type"])
        if q.get("rolling") == "1":
            where.append("j.rolling=1")
        if q.get("fresh") == "1":
            where.append("date(j.created_at)=date('now','localtime')")
        if q.get("nodeadline") == "1":
            where.append("j.deadline IS NULL")
        kw = (q.get("q") or "").strip()
        join = ""
        if kw:
            terms = _search_terms(kw)
            if len(kw) >= 3 and db.has_fts(request.app.state.conn):
                join = "JOIN jobs_fts f ON f.job_id=j.id AND jobs_fts MATCH ?"
                params = [" OR ".join(f'"{t}"' for t in terms)] + params
            else:
                likes = " OR ".join(["j.search_text LIKE ?"] * len(terms))
                where.append(f"({likes})")
                params.extend(f"%{t}%" for t in terms)
        return join, where, params, q

    def overview(request: Request) -> dict:
        """首屏概览数字：进页面第一眼就知道"今天该看什么"。"""
        conn = request.app.state.conn
        row = conn.execute(
            "SELECT "
            "  SUM(notice_kind='opening') AS opening,"
            "  SUM(notice_kind='opening' AND deadline IS NOT NULL"
            "      AND deadline BETWEEN date('now') AND date('now','+3 day')) AS d3,"
            "  SUM(notice_kind='opening' AND deadline IS NOT NULL"
            "      AND deadline BETWEEN date('now') AND date('now','+7 day')) AS d7,"
            "  SUM(date(created_at)=date('now','localtime')) AS fresh"
            " FROM jobs WHERE status != 'archived'").fetchone()
        return {k: (row[k] or 0) for k in ("opening", "d3", "d7", "fresh")}

    @router.get("/", response_class=HTMLResponse)
    def home(request: Request):
        join, where, params, q = list_query(request)
        if q.get("sort") == "pub":
            order = ("ORDER BY j.publish_date IS NULL, j.publish_date DESC, "
                     "j.deadline IS NULL, j.deadline, j.id DESC")
        elif q.get("sort") == "new":
            # "最新收录"：配合首屏"今日新增"数字用，回访时先看刚抓到的
            order = "ORDER BY j.created_at DESC, j.id DESC"
        else:
            # 默认：临期在前（有截止日的按日期升序），无截止日的沉底
            order = ("ORDER BY CASE WHEN j.deadline IS NULL THEN 1 ELSE 0 END, "
                     "j.deadline ASC, j.publish_date DESC, j.id DESC")
        rows = request.app.state.conn.execute(
            f"SELECT j.*, a.id AS aid FROM jobs j "
            f"LEFT JOIN applications a ON a.job_id=j.id "
            f"{join} WHERE {' AND '.join(where)} {order} LIMIT 300",
            params).fetchall()
        return render("list.html", request, jobs=rows, q=q, stats=overview(request))

    @router.get("/jobs/{job_id}", response_class=HTMLResponse)
    def detail(job_id: int, request: Request):
        conn = request.app.state.conn
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if job is None:
            return RedirectResponse("/", status_code=303)
        # 看过就算已读：省掉"看完再点一次标记已读"这一步
        if job["status"] == "new":
            conn.execute("UPDATE jobs SET status='read' WHERE id=?", (job_id,))
            conn.commit()
        app_row = conn.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
        sources = conn.execute("SELECT * FROM job_sources WHERE job_id=?", (job_id,)).fetchall()
        snapshot_text = None
        if job["snapshot_path"] and Path(job["snapshot_path"]).exists():
            snapshot_text = Path(job["snapshot_path"]).read_text("utf-8", errors="replace")
        # 返回列表时保住筛选：从 Referer 取站内来源页
        back = _safe_local(request.headers.get("referer"), request)
        return render("detail.html", request, job=job, app_row=app_row,
                      sources=sources, snapshot_text=snapshot_text, back_url=back or "/")

    @router.post("/jobs/{job_id}/status")
    def set_status(job_id: int, request: Request, status: str = Form(...)):
        request.app.state.conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        request.app.state.conn.commit()
        return redirect_back(request)

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
        # 备注要能搜到：搜索文本里包含 notes，FTS 索引一并重建
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        text = _search_text({"title": row["title"], "org": row["org"],
                             "body": "", "notes": notes})
        conn.execute("UPDATE jobs SET search_text=? WHERE id=?", (text, job_id))
        reindex_fts(conn, job_id, row["title"], row["org"], "")
        conn.commit()
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    @router.post("/jobs/{job_id}/apply")
    def apply(job_id: int, request: Request):
        conn = request.app.state.conn
        conn.execute("INSERT OR IGNORE INTO applications(job_id) VALUES(?)", (job_id,))
        conn.commit()
        # 从列表行直接加跟踪时回到列表（保筛选）；从详情页加则留在详情页
        return redirect_back(request, fallback=f"/jobs/{job_id}")

    @router.post("/jobs/batch")
    def batch(request: Request, action: str = Form(...), ids: str = Form("")):
        """批量操作：ids 为逗号分隔的岗位 id。"""
        conn = request.app.state.conn
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if id_list and action in ("read", "archive", "unarchive"):
            marks = ",".join("?" * len(id_list))
            status = {"read": "read", "archive": "archived", "unarchive": "read"}[action]
            conn.execute(f"UPDATE jobs SET status=? WHERE id IN ({marks})",
                         [status, *id_list])
            conn.commit()
        return redirect_back(request)

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
    ws.append(["序号", "标题", "单位", "类型", "城市", "用工性质", "发布日期",
               "截止日期", "性质", "状态", "链接", "备注"])
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
        emp = r["employment_type"] or ("长期有效" if r["rolling"] else "")
        ws.append([i, r["title"], r["org"] or "", tmap.get(r["job_type"], r["job_type"]),
                   r["city"] or "", emp, r["publish_date"] or "", r["deadline"] or "",
                   kmap.get(r["notice_kind"], r["notice_kind"]),
                   r["status"], r["url"], r["notes"] or ""])
    buf = io.BytesIO()
    wb.save(buf)
    name = quote("招聘信息汇总表.xlsx")
    return Response(
        buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"})
