import io
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from fastapi import APIRouter, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import snapshot_view
from .. import db
from .. import resume
from ..classify import CITIES, SOURCE_CATEGORIES
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


def _with_flash(resp: RedirectResponse, action: str, ids: list[int]) -> RedirectResponse:
    """给重定向 URL 挂上"刚做了什么"，让下一屏能显示可撤销的提示条。

    用 query 而不是 session：这是单用户本地工具，没有登录态，query 足够且无状态。
    """
    loc = resp.headers.get("location", "/")
    sep = "&" if "?" in loc else "?"
    idstr = ",".join(str(i) for i in ids[:200])
    resp.headers["location"] = f"{loc}{sep}done={action}&ids={idstr}"
    return resp


def make_qs(q: dict):
    """生成"保留当前筛选"的链接。

    没有它之前，模板里每一个链接都是写死的 `?bulk=1`、`/`——用户在「律所+广州」
    下点一下「批量」，筛选就全丢了，批量操作的对象也跟着变，可能误归档无关岗位。
    值 None/''/'0' 视为"去掉这个参数"，正好用来做开关的两种状态。
    """
    def qs(**overrides):
        d = {k: v for k, v in q.items() if v not in (None, "", "0")}
        for k, v in overrides.items():
            if v in (None, "", "0", False):
                d.pop(k, None)
            else:
                d[k] = v
        return ("?" + urlencode(d)) if d else "/"
    return qs


def mount(app: FastAPI, tpl_dir: str) -> Jinja2Templates:
    templates = Jinja2Templates(directory=tpl_dir)
    # auto_reload 关掉：这是常驻服务，模板不会中途变，省掉每次渲染的 stat。
    # 改模板要重启服务（本来改 .py 也要重启，心智负担一致）。
    templates.env.auto_reload = False
    router = APIRouter()
    # 静态资源版本号取 CSS 与 JS 的 mtime：改完刷新页面即生效，不会被浏览器缓存卡住
    static_dir = Path(tpl_dir).parent / "static"

    def asset_version() -> str:
        # 注意：这里刻意**不缓存**。mtime 每次都取，改 CSS/JS 刷新页面即生效——
        # 这是已交付的开发体验；两次 stat 的开销（微秒级）远不值得破坏它。
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
        # 源的展示信息：分类映射 + slug→中文名（列表页"来源"列显示可读名）
        ctx.setdefault("source_categories", SOURCE_CATEGORIES)
        conn = request.app.state.conn
        ctx["src_names"] = dict(conn.execute("SELECT slug, name FROM sources").fetchall())
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
        # 归档默认隐藏，但要能专门看：否则误归档（行内 × 只有 24px，很容易点错）
        # 就等于永久删除，用户连找回的入口都没有
        if q.get("status") == "archived":
            where, params = ["j.status='archived'"], []
        else:
            where, params = ["j.status != 'archived'"], []
        # 默认只看"可投递"的岗位；政务渠道里大量事后结果公示对求职者没有价值
        kind = q.get("notice_kind")
        # 归档视图不套"仅可投递"：找回误归档的岗位时，不能因为它是结果公示就看不见
        if kind == "all" or (q.get("status") == "archived" and not kind):
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
        if q.get("status") and q["status"] != "archived":
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
        if q.get("urgent") in ("3", "7"):
            # 概览条上的"3 天内/7 天内截止"必须真能筛出来，否则数字和点进去的
            # 结果对不上——之前它只是排序，用户会以为筛选坏了
            where.append("j.deadline IS NOT NULL AND j.deadline BETWEEN date('now') "
                         "AND date('now',?)")
            params.append(f"+{q['urgent']} day")
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
        limit = 300
        where_sql = " AND ".join(where)
        rows = request.app.state.conn.execute(
            f"SELECT j.*, a.id AS aid FROM jobs j "
            f"LEFT JOIN applications a ON a.job_id=j.id "
            f"{join} WHERE {where_sql} {order} LIMIT {limit}",
            params).fetchall()
        # 命中总数要告诉用户：之前只显示"300 条"，实际可投递 400+，
        # 用户会以为看完了，剩下的一百多条静默不可见
        total = request.app.state.conn.execute(
            f"SELECT COUNT(*) c FROM jobs j {join} WHERE {where_sql}", params).fetchone()["c"]
        # 上一次写操作的回执（批量归档/恢复后显示"已归档 N 条 · 撤销"）
        flash = None
        if q.get("done") in ("archive", "unarchive"):
            ids = [x for x in (q.get("ids") or "").split(",") if x.strip().isdigit()]
            flash = {"action": q["done"], "n": len(ids), "ids": ",".join(ids)}
        return render("list.html", request, jobs=rows, q=q, stats=overview(request),
                      total=total, limit=limit, qs=make_qs(q), flash=flash)

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
            # 整读再按字符截：按字节读 60KB 会把多字节汉字拦腰斩断出乱码
            with open(job["snapshot_path"], "rb") as fh:
                snapshot_text = fh.read().decode("utf-8", errors="replace")[:20000]
        snap = snapshot_view.render_snapshot(snapshot_text) if snapshot_text else None
        # 返回列表时保住筛选：从 Referer 取站内来源页
        back = _safe_local(request.headers.get("referer"), request)
        # 有画像就算一下匹配度：用户从列表点进来时最想知道"这个跟我配不配"
        match = None
        prof = resume.load_profile(conn)
        if prof:
            match = resume.match_job(prof, dict(job))
        return render("detail.html", request, job=job, app_row=app_row,
                      sources=sources, snapshot_text=snapshot_text, snap=snap,
                      back_url=back or "/", match=match)

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
            # 写操作必须留痕：之前静默回跳，归档后整片行消失，用户不知道是成功了
            # 还是出错了，更没有反悔的机会。回跳时带上"做了什么 + 影响哪些 id"，
            # 页面顶部渲染一条可撤销的提示。
            if action != "read":
                return _with_flash(redirect_back(request), action, id_list)
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

    @router.post("/applications/{app_id}/remove")
    def app_remove(app_id: int, request: Request):
        """取消跟踪：误点「跟踪」要能撤销。原来只能加不能删，用户只能干看着。"""
        conn = request.app.state.conn
        row = conn.execute("SELECT job_id FROM applications WHERE id=?",
                           (app_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
            conn.commit()
        back = request.headers.get("referer") or "/board"
        return RedirectResponse(back, status_code=303)

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
        # 按分类的展示优先级排（五院四系 → 广东高校 → 国企 → 政务 → 律协 → 人才市场），
        # 再按组内权重（rank 相同按 slug），让"用户最关心的源"出现在最上面
        sources = conn.execute(
            "SELECT * FROM sources ORDER BY rank, name").fetchall()
        grouped: dict[str, list] = {}
        for s in sources:
            grouped.setdefault(s["category"] or "talent", []).append(s)
        logs = conn.execute("SELECT * FROM collect_logs ORDER BY id DESC LIMIT 50").fetchall()
        return render("health.html", request, grouped=grouped, sources=sources, logs=logs)

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

    # ── 简历 / 个人画像 ───────────────────────────────────────────────────
    @router.get("/profile", response_class=HTMLResponse)
    def profile_page(request: Request):
        prof = resume.load_profile(request.app.state.conn)
        return render("profile.html", request, prof=prof, job_types=JOB_TYPES,
                      err=request.query_params.get("err"))

    @router.post("/profile/upload")
    async def profile_upload(request: Request, file: UploadFile = File(...)):
        """上传简历 → 解析 → 写入画像（随后可在页面上改）。"""
        data = await file.read()
        if len(data) > 8 * 1024 * 1024:
            return RedirectResponse("/profile?err=too-big", status_code=303)
        try:
            text = resume.extract_text(file.filename or "", data)
        except ImportError:
            # pdf/docx 的可选依赖没装：明确告诉用户，而不是静默存一份乱码
            return RedirectResponse("/profile?err=no-parser", status_code=303)
        if not text.strip():
            return RedirectResponse("/profile?err=empty", status_code=303)
        parsed = resume.parse_resume(text)
        parsed["raw_text"] = text[:20000]
        parsed["source_file"] = file.filename or ""
        resume.save_profile(request.app.state.conn, parsed)
        return RedirectResponse("/profile", status_code=303)

    @router.post("/profile")
    async def profile_save(request: Request):
        """手动编辑画像。解析抽错的、想调整的，都在这里改——解析只是起个草稿。

        列表字段按逗号/顿号/分号/换行切分，不要求用户记格式。
        意向类型是勾选框（用户不该被要求背英文代码），勾了哪个算哪个。
        """
        conn = request.app.state.conn
        old = resume.load_profile(conn) or {}
        form = await request.form()

        def split(v: str) -> list[str]:
            return [x.strip() for x in re.split(r"[,，、;；\n\r]+", v or "") if x.strip()]

        prof = {
            "name": (form.get("name") or "").strip(),
            "skills": split(form.get("skills") or ""),
            "cities": split(form.get("cities") or ""),
            # 勾选框：勾了才提交，name 形如 job_type_lawfirm
            "job_types": [val for val, _ in JOB_TYPES if form.get(f"job_type_{val}")],
            "years": (form.get("years") or "").strip(),
            "education": [{"degree": d, "level": 0, "school": "", "major": "",
                           "year": ""} for d in split(form.get("education") or "")],
            "experiences": [{"kind": k, "detail": ""}
                            for k in split(form.get("experiences") or "")],
            "raw_text": old.get("raw_text", ""),
            "source_file": old.get("source_file", ""),
        }
        if prof["years"].isdigit():
            prof["years"] = int(prof["years"])
        else:
            prof["years"] = None
        resume.save_profile(conn, prof)
        return RedirectResponse("/profile", status_code=303)

    @router.get("/recommend", response_class=HTMLResponse)
    def recommend_page(request: Request):
        conn = request.app.state.conn
        prof = resume.load_profile(conn)
        if prof is None:
            return render("profile.html", request, prof=None,
                          need_profile=True, job_types=JOB_TYPES)
        kws = prof.get("keywords") or []
        # 已跟踪的不进推荐（推荐是给"还没决定投哪"用的）；已过期的没意义。
        # 平分时按源的展示优先级排——五院四系的 71 分比人才市场的 71 分更该先看。
        rows = conn.execute(
            "SELECT j.*, a.id AS aid, s.rank AS src_rank FROM jobs j "
            "LEFT JOIN applications a ON a.job_id=j.id "
            "LEFT JOIN sources s ON s.slug=j.source_slug "
            "WHERE j.status != 'archived' AND j.notice_kind='opening' "
            "AND a.id IS NULL "
            "AND (j.deadline IS NULL OR j.deadline >= date('now')) "
            "ORDER BY j.deadline IS NULL, j.deadline LIMIT 400").fetchall()
        scored = []
        for r in rows:
            m = resume.match_job(prof, dict(r), kws)
            scored.append((m, r))
        scored.sort(key=lambda x: (-x[0]["score"], x[1]["src_rank"] or 99,
                                   x[1]["deadline"] or "9999"))
        top = scored[:60]
        return render("recommend.html", request, prof=prof, items=top,
                      top_n=sum(1 for m, _ in top if m["score"] >= 60),
                      job_types=JOB_TYPES)

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
