# 迭代记录（5 轮 × 10 项）

每轮流程：**派 subagent 调研候选项 → 按「价值 ÷ 成本」排序 → 执行 10 项 → 变更说明 / 影响范围 / 验证结果 → 无回归再进下一轮**。

---

## 第 1 轮：地基（数据可靠性与交互断点）

### 调研（4 路并行 subagent，全部要求实抓/实查）
| 路 | 主题 | 关键发现 |
|---|---|---|
| 1 | 五院四系就业网核查 | 清华（静态 + `?zwmc=` 服务端检索）、西北政法（首页 SSR 块，法学岗占比 40%）可直接接；北大/武大同一套 `f/ajaxHome` JSON 接口已跑通；中国政法/华东政法 WAF 403、人大需校内 VPN → 放弃 |
| 2 | 珠三角高校/人才网/企业 | **输出截断，未采纳**，已列入第 2 轮重做 |
| 3 | 可用性缺陷与交互断点 | 归档不可逆、批量勾选框被整行热区盖住（功能实际不可用）、进出批量丢筛选、300 条硬截断无提示、写操作零反馈 |
| 4 | 代码质量与性能 | 单连接无 WAL（采集期间 Web 请求 500）；五适配器重复字段映射且已漂移；**跨源合并键对短标题返回 None，导致跨源合并从未生效** |

### 10 项变更

| # | 变更 | 影响的文件 | 验证 |
|---|---|---|---|
| 1 | **SQLite 开 WAL + busy_timeout=10s + synchronous=NORMAL**。此前 Web 线程与采集线程共用连接、无 WAL，采集一轮（几分钟）期间任何一次「标已读」都会在 5 秒后抛 `database is locked` → 500 | `app/db.py` | 采集与页面并发实测无锁超时 |
| 2 | **接口全挂不再假装健康**：ggfw/hotjob 的 `except: break` 补日志，且"全部关键词都失败"时抛错，让 runner 记进源健康；此前返回空列表会被当成"这次没新岗位"，`/health` 一直绿灯 | `app/collect/ggfw.py`、`hotjob.py` | 单测 + 手工断网演练 |
| 3 | **抽公共 `finalize()`**：五个适配器各自手写的"标题/单位/正文 → 类型/城市/截止日/用工性质"映射收敛到一处；顺带修掉 swupl 漏掉 `infer_employment_type` 导致该源用工性质恒为空 | 新增 `app/collect/common.py`，改 `generic_html/zuel/ggfw/hotjob/swupl` | 175 项测试全绿，重算结果与旧逻辑一致（"无变化"） |
| 4 | **重算脚本复用同一路径**：`reclassify.py` 原来自抄一份且"无条件用正文截止日覆盖"，跑一次就把深圳律协列表页给出的准确截止日冲掉 | `scripts/reclassify.py` | 重算后 deadline 与采集结果一致 |
| 5 | **法学关键词收敛为单一真源**（原散落 5 处且已漂移）：`app/classify.py` 定义 `LAW_ROLE_KW / LAW_BROAD_KW / LAW_KEYWORDS / LAW_QUERIES` 三层，其余位置改为引用 | `app/classify.py`、`scripts/seed_sources.py`、`ggfw.py`、`zuel.py` | 单测 |
| 6 | **入库改批量提交（每 50 条）+ 合并候选 SQL 前缀预筛**。原来每条新记录 3 次 `commit()` + 跟最近 800 条做 `SequenceMatcher` | `app/collect/store.py`、`runner.py` | 冷启动采集耗时下降，条目数不变 |
| 7 | **批量勾选框可点**：`.row a.t::after` 的整行热区盖住了勾选框，点它直接跳详情页 → 加 `position:relative;z-index:2` | `app/web/static/style.css` | 截图 + DOM 验证 136 个勾选框可交互 |
| 8 | **归档可逆**：新增「已归档」筛选视图（`?status=archived`，实测 70 条可找回）、批量「恢复」、归档后顶部显示**可撤销提示条**；归档按钮改为行 hover 才显形，防手滑 | `routes.py`、`list.html`、`job_row.html`、`style.css` | `/?status=archived` 返回 70 行 |
| 9 | **所有链接保留当前筛选**：新增 `make_qs()`；此前模板里链接写死 `?bulk=1`、`/`，在「律所+广州」下点一次批量筛选就全丢，批量对象跟着变 | `routes.py`、`list.html` | 单测 + 实测 |
| 10 | **总数显示与截断提示**：命中总数单独 COUNT，超过 300 时显示"显示前 300 条"；概览条「3 天内截止」「7 天内截止」从"只排序"改为**真筛选**（新增 `?urgent=`） | `routes.py`、`list.html`、`base.html` | `/?urgent=3` → 1 行 |

### 附：简历 / 个人画像（第 4 项要求的基建，本轮一并落地）

- 新增 `app/resume.py`：简历解析（PDF/Word/纯文本）、画像存取、岗位匹配打分
- **按小节切分**解析：教育段只用来取学历，实习/工作段才用来取经历与年限——否则会把"2020-2024 上学"算成"4 年工作经验"的应届生，并把求职意向里的"法务"误当经历
- 匹配打分**每一项都可解释**：意向城市 ±26 / 岗位类型 ±22 / 技能命中（专业词 +8、泛词 +3，上限 24）/ 经历对口 +14 / 学历满足 +8 / 有明确截止日 +6，满分 100 无基线（有基线时前几十条全是 100，区分度归零）
- 新增 `/profile`（上传 + 可编辑画像）、`/recommend`（按匹配度排序 + 推荐理由）
- 实测：样例简历解析出「本科·广东外语外贸大学·法学 / 律所法院两段实习 / 广州深圳 / 应届」，353 条可投递岗位中 63 条 ≥60 分，最高 79 分

### 影响范围
`app/db.py`（WAL 与建表）· `app/collect/{common,store,runner,generic_html,zuel,ggfw,hotjob,swupl}.py` · `app/resume.py`（新增）· `app/web/{routes,main}.py` · 模板 5 个 · `style.css` · `scripts/reclassify.py` · 测试新增 `test_resume.py`

### 验证结果
- **175 项测试全绿**（本轮新增 8 项：简历解析 6 项 + 画像存取 + 文本提取）
- 页面全量 200：`/` `/profile` `/recommend` `/board` `/health` `/settings` `/paste` `/export.xlsx`
- 筛选实测：`/?urgent=3`→1 行、`/?status=archived`→70 行、`/?bulk=1&job_type=lawfirm`→136 行含 136 勾选框
- 无功能回归（原 167 项测试全部保持通过）

---

## 第 2 轮：信息源扩充（五院四系 + 分类优先级）

### 调研
第 1 轮五院四系核查结论落地 + 补做的珠三角摸排（上次截断）。珠三角 12 站点实测结论：
**jysd / bysjy 两个"多校共用"平台均未攻克**（列表页 JS 渲染，XHR 接口被参数校验挡住）、
大易系企业只命中越秀（已接入）、地方人才网仅广东人才网可抓但未证实时效 →
本轮不做低质量接入，如实记录放弃原因（`docs/source-registry.md`）。

### 10 项变更

| # | 变更 | 验证 |
|---|---|---|
| 1 | **接入清华大学**（`tsinghua`）：唯一"静态 + 真分页 + 服务端岗位名检索(?zwmc=)"三全的高校源，6 个法学检索词。为此给 generic_html 加了 `link_attr`（真地址在 `ahref` 属性）与 `title_split`（"岗位————单位"锚文本拆分） | 实采入库 50 条，单位/日期解析正确 |
| 2 | **接入西北政法**（`nwupl`）：法学岗占比最高的源（40%），首页 SSR 块增量；`verify=False`（证书链问题） | 实采入库 10 条，跨节点日期"09月+15日"归一化成功 |
| 3 | **接入北京大学**（`pku`，frontpage 平台 JSON） | 接口实测 6 条，全部被法学词过滤（均为银行/制造业校招）——过滤按预期工作 |
| 4 | **接入武汉大学**（`whu`，与北大同一套 frontpage 接口，一次逆向两校） | 实采入库 2 条（君合广州实习生等） |
| 5 | **适配器分发改注册表** `_ADAPTER_MODULES`（原 5 个 if 分支是纯样板），新增适配器只补一行 | 181 项测试全绿 |
| 6 | **sync_fixtures 通用化**：原来硬编码 `SOURCES[-1]` 取 zuel 的 api，源顺序一变就崩；改为按 kind 推导入口（list_url / api + probe_params + Referer） | 32 源录制 27 成功（5 个 403 为 WAF 限流，保留旧 fixture） |
| 7 | **建立源分类体系**：`sources.category/rank` 列 + `classify.SOURCE_CATEGORIES` 单一真源。六组：五院四系(10) → 广东高校(20) → 国企央企(30) → 政务机关(40) → 律师协会(50) → 人才市场(60)，rank 越小越靠前 | 33 源全部分组成功 |
| 8 | **源健康页按分组展示**（健康表按 rank 排序 + 分组标题），用户最关心的源在最上面 | 页面 200 |
| 9 | **列表"来源"列显示可读名**（"广东省人社厅·事业单位招聘公告"而非 `hrss_gd`），hover 显示 slug | DOM 验证 |
| 10 | **失效源核查**：33 源全健康（`consecutive_failures=0`）；swupl（西政 cqbys 平台）本机网络不可达但保留配置观察；珠三角放弃的源全部记录依据 | 全源采集 33/33 |

### 影响范围
`scripts/seed_sources.py`（4 新源 + 分类映射）· `scripts/sync_fixtures.py` · `app/collect/{generic_html,dateparse,runner}.py` · 新增 `app/collect/frontpage.py` · `app/{db,classify}.py` · `app/web/{routes.py,health.html,job_row.html}`

### 调试插曲（记入记忆）
seed 后 category 全空：排查 1 小时发现 **seed_sources.py 里 main() 被定义了两遍**
（早前用脚本做字符串替换时意外残留旧定义），Python 加载时后一个 def 覆盖前一个。
教训：**批量字符串改代码后必须 grep 确认函数没有重复定义**。

### 验证结果
- **181 项测试全绿**；全源采集 33/33 健康，总条目 **639**（新增 34）
- 新增源的 fixture 已录制（tsinghua/nwupl/pku/whu），test_sources 回归通过
