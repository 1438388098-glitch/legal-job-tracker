# 法学招聘信息中台

一个跑在你自己电脑上的 **法学求职信息收集与管理系统**。自动从 14 个官方渠道收集
珠三角 + 韶关的律所 / 体制内 / 法务 / 实习岗位，统一去重后在本机网页里筛选浏览、
跟踪投递、临期提醒、导出汇总表。

- 单机运行，数据全在本机 SQLite 文件里，不联网上传任何内容
- 无需 Node / 前端构建链，一个命令启动
- 采集器按"配置 + 选择器"驱动，官网改版时改配置即可，不用动代码

---

## 快速开始

```bash
# 1) 建虚拟环境并装依赖（首次）
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install fastapi "uvicorn[standard]" jinja2 httpx \
    selectolax apscheduler python-multipart openpyxl pytest

# 2) 初始化数据库 + 写入 14 个信息源
.venv/Scripts/python.exe scripts/seed_sources.py

# 3) 首次采集（实测 65~80 秒，14 源全部成功，约 300 条）
.venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'.');from app import db;from app.collect.runner import Runner;c=db.connect('data/job.db');db.init_db(c);print(Runner(c).run_all())"

# 4) 启动本地网页
.venv/Scripts/python.exe -m uvicorn app.web.main:create_app --factory --port 8642
```

然后浏览器打开 **http://127.0.0.1:8642** 。

> 服务启动后每天 08:05 会自动采集一次（增量，实测约 10 秒）。设环境变量
> `APP_DISABLE_SCHEDULER=1` 可关掉定时任务。

---

## 日常怎么用

| 我想做的事 | 去哪里 |
|---|---|
| 看有哪些新岗位 | 首页 `/`，默认**只显示可投递岗位**，按截止日期排序，临期在最上面 |
| 查一条早就截止的公告 | 顶部筛选切「全部稿件」，或用关键词搜（结果公示类默认不显示但永远搜得到） |
| 只看某类/某城市 | 首页顶部筛选栏（公告性质 / 类型 / 城市 / 状态 / 关键词） |
| 临期提醒 | 顶栏横幅：3 天内截止标红、7 天内标黄 |
| 投递跟踪 | 点开岗位 →「我要投」→ 在 `/board` 看板按状态列查看（待投/已投/笔试/面试/Offer/拒） |
| 公众号里的招聘信息 | `/paste` 粘贴箱：贴链接 → 系统抓正文提字段 → 你确认入库 |
| 看哪些源挂了 | `/health` 源健康页：每个源的上次成功时间、连续失败次数、最近错误，可单源立即重采 |
| 导出成 Excel | 顶部「导出可投递岗位」/「导出全部稿件」，或直接开 `/export.xlsx?notice_kind=all` |
| 改错字段 | 岗位详情页 →「编辑」（标题/城市/截止日/类型/备注） |

**公告性质过滤（重要）**：政务渠道里很大一部分稿件不是"开放报名的岗位"，而是事后
结果公示（拟聘用人员名单公示 / 笔试成绩 / 分数线 / 体检考察）。实测首批 299 条里
这类占 23%，且天然没有投递截止日。系统把稿件分成三类 —— **可投递 / 结果公示 /
其他信息** —— 默认只显示和三者的第一类，避免"乱七八糟的信息混杂"。

**归档规则**：截止日期过后 7 天自动沉底（`status='archived'`），首页不再显示，但搜索
永远能召回。

**去重规则（两层）**：

1. **链接指纹**：同一条 URL 只入库一次，自动忽略 utm 等跟踪参数；
2. **跨源合并**：同一条招聘同时挂在多个渠道时合成一条，卡片标注"N 个来源"，
   详情页列出全部来源链接。合并条件很严 —— 必须**跨源**、标题足够长（≥10 字）、
   标题高度相似、发布时间相差 45 天以内，四个条件同时满足。

   为什么这么严：早期版本只比"标题像不像"，结果把同一批公告的不同期次（中山某镇
   招聘公示 6 期）、不同年份的同名公告（检察院 2023/2024/2025 选调公告）、泛岗位名
   （不同律所的"律师助理"）都合成了同一条，属于实打实的数据损失。现在是宁可漏合并
   （多出一张卡片）也不错合并（吞掉一条真岗位）。

---

## 信息源（14 个）

| 类别 | 源 |
|---|---|
| 法院 / 检察 | 广东法院网·工作公告、广东省检察院·通知公告 |
| 人社系统（事业单位/公职） | 广东省人社厅、广州、深圳、中山、珠海、佛山、**韶关** 人社局 |
| 律所 / 律师行业 | 广东律师网·律所招聘、惠州市律协·律所招聘 |
| 高校就业网 | 广东外语外贸大学、广州大学（站内按"法务/律师/法律/合规/知识产权/专利"检索） |
| 外校就业中心接口 | 中南财经政法大学就业中心（JSON 接口，含专业要求字段，按 majors 过滤法学） |

完整清单、验证状态、域名陷阱（哪些旧域名已失效、哪些站点需要 http 降级或 gb2312
转码）见 [`docs/source-registry.md`](docs/source-registry.md)。

各源产出（2026-09-15 首次采集，共 299 条）：

| 源 | 条数 | 说明 |
|---|---|---|
| 广外就业网 | 60 | 关键词检索得到，法务专员/律师助理/仲裁院书记员等 |
| 中南财就业中心 | 31 | 全部为法学相关岗位，100% 带投递截止日 |
| 广东律师网 | 30 | 已翻 2 页（共 281 页，可按需调大） |
| 省人社厅 | 27 | 含省属事业单位集中招聘，74% 带截止日 |
| 深圳人社 | 20 | 3 条可投递 + 17 条结果公示 |
| 珠海人社 | 20 | 8 条可投递 |
| 佛山人社 | 20 | 19 条可投递 |
| 中山人社 | 16 | 全部是拟聘公示（该栏目就是这样） |
| 广大就业网 | 14 | 关键词检索 |
| 广州人社 | 13 | |
| 广州大学城… / 惠州律协 | 10 | |
| 广东法院网 | 11 | 该院招聘多走微信公众号，静态栏目以公示为主 |
| 省检察院 | 25 | 需 gb2312 转码 + http 降级 |
| 韶关人社 | 2 | 该栏目以法院送达公告为主，招聘稿件稀疏 |

### 加一个新源

绝大多数源不需要写代码，只要在 `scripts/seed_sources.py` 里加一条配置：

```python
dict(slug="xxx", **_html(
    "某某市人社局·招聘公告",
    _idx("https://xxx.gov.cn/zpgg/index.html", 2),   # 列表页（_idx 自动展开分页）
    "ul.list li",              # 条目容器
    title_attr="title",        # 从 title 属性取标题（避免页面上的"…"截断）
    date_sel="span.time",      # 发布日期
    detail_sel="div.article",  # 详情页正文容器（留空则自动挑最像正文的块）
    city="某市", job_type="public")),
```

改完跑这套"校准三件套"：

```bash
.venv/Scripts/python.exe scripts/probe_sources.py          # 从真实页面推断容器选择器候选
.venv/Scripts/python.exe scripts/peek.py <slug> <正则>      # 打印原始 HTML 片段对照
.venv/Scripts/python.exe scripts/preview_parse.py <slug>    # 预览解析结果对不对
.venv/Scripts/python.exe -m pytest tests/test_sources.py -q # fixture 回归
```

配置字段的完整说明在 `app/collect/generic_html.py` 顶部注释里。常用字段：
`list_urls`（多入口/分页）、`link_sel`、`title_sel`、`title_attr`、`date_sel`、`org_sel`、
`detail_sel`、`no_detail`、`url_scheme`、`keep_keywords`、`title_keywords`、
`exclude_url`、`max_age_days`、`detail_budget`、`notice_kind`、`encoding`、`verify`。

### 改了判定规则怎么办

`notice_kind` / 截止日期这类派生字段可以**用本地快照重算，不必重新联网抓取**：

```bash
.venv/Scripts/python.exe scripts/reclassify.py            # 重算公告性质 + 截止日期
.venv/Scripts/python.exe scripts/reclassify.py --kind-only # 只重算公告性质
```

---

## 目录结构

```
app/
  db.py            SQLite schema、FTS 全文索引、自动归档、老库补列迁移
  dedup.py         URL 指纹 + 跨源合并规则
  dateparse.py     中文日期解析 + 截止日期锚定抽取
  classify.py      岗位类型 / 城市 / 公告性质（可投递·结果公示·其他）
  snapshot.py      详情页正文快照（本地留档，官网删稿也能回看）
  collect/
    http.py        带重试与连接池的抓取（4xx 与硬 TLS 失败不重试）
    generic_html.py 配置驱动的通用列表适配器
    zuel.py        中南财经政法大学 JSON 接口适配器
    pastebox.py    粘贴箱（贴链接抓正文）
    store.py       入库与跨源合并
    runner.py      采集调度、源健康记录、可选 Windows 通知
  web/
    main.py        应用入口 + 每日定时任务
    routes.py      全部路由（列表/详情/看板/粘贴箱/健康/设置/导出）
    templates/     Jinja2 模板
scripts/
  seed_sources.py      信息源配置（**加源改这里**）
  sync_fixtures.py     录制真实页面为测试 fixture
  probe_sources.py / peek.py / preview_parse.py   选择器校准三件套
  reclassify.py        用本地快照重算派生字段
tests/                 109 项测试，含 14 个源的真实 fixture 回归
docs/
  source-registry.md                     全网源清单与域名陷阱
  superpowers/specs/...-design.md        设计文档
  superpowers/plans/...-implement.md     实施计划与验收记录
```

---

## 性能与稳定性

- 首次全量采集：**65~80 秒**（14 源，约 300 条，并发 6 抓详情）
- 日常增量采集：**约 10 秒**（已知 URL 跳过详情抓取，只处理新条目）
- 慢站保护：每个源有 90 秒（慢站 60 秒）的详情抓取预算，超预算后剩余条目只保留
  标题/日期，正文留空 —— 避免深圳人社这类慢站把整轮采集从 1 分钟拖到 10 分钟以上
- 失败隔离：单个源失败只记录到 `/health`，不影响其他源

## 已知取舍

1. **选择器漂移**：官网改版会让某个源解析不到内容 —— `tests/test_sources.py` 用真实
   fixture 做回归，`/health` 显示源健康状况。14 个源各有一份 2026-09-15 录制的页面，
   改版后这里会率先失败，提示你重新校准。
2. **深圳人社走 http**：该站 https 在本机 OpenSSL 3 下握手失败（BAD_ECPOINT），
   配置里用 `url_scheme: "http"` 强制降级。
3. **省检察院需 gb2312**：配置 `encoding: "gb2312"` + http 降级。
4. **JS 渲染站点**（深圳/广州中院、东莞律协、南方电网等）本期不做，覆盖靠上级聚合源
   （广东法院网 / 省人社厅）和粘贴箱弥补。
5. **广外/广大职位板**详情页是 JS 渲染，拿不到"专业要求"字段，改用站内 `?keyword=`
   检索法学相关岗位（实测"法务"→法务专员/法务助理，"律师"→律师助理/仲裁院书记员）。
6. **韶关岗位稀疏**：韶关人社栏目以法院送达公告为主，每页约 2 条招聘稿件；
   韶关的岗位主要靠广东省人社厅集中招聘公告覆盖。
7. **中南财接口**的 `majors=` 服务端过滤语义不完整（`majors=法学` 只返回 4 条，而按
   majors 字段在本地匹配可命中约 1/3 的近期记录），所以改为按页拉取后本地过滤。
8. **截止日期不硬凑**：只在"截止/报名时间/投递"等词所在句子里取日期，取不到就留空。
   早期版本取全篇最大日期，把体检时间、考试时间甚至"年龄截止至报名开始当天"当成
   投递截止（213 条里 70 条明显错）。现在 79 条里只有 3 条可疑 —— **错误的截止日比
   没有截止日更糟**，会造成假的红色临期提醒。

---

## 测试

```bash
.venv/Scripts/python.exe -m pytest tests/ -q     # 109 passed
```

- 单元测试：去重（含 3 类误合并回归）、日期解析、截止锚定、分类、入库、HTTP 重试策略、
  网页路由与筛选、导出
- fixture 回归：14 个源各有一份真实录制的列表页，验证选择器仍能解析出条目
- fixture 录制时间：2026-09-15（测试内用固定基准日，不会随真实日期推移失效）
