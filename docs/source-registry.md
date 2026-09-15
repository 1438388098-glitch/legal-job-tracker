# 信息源清单（全网摸排结果）

摸排日期：2026-09-15。验证口径：**已验证** = WebFetch/curl 实际抓到目标页面且内容匹配；**未验证** = 域名存在但栏目无法定位、JS 渲染拿不到内容或访问被拦。

分级说明：
- **T1 静态规整**：列表页为静态 HTML、结构清晰，直接做配置驱动的通用适配器（MVP 首批）。
- **T2 可抓有毛刺**：静态可达但需关键词过滤 / http 降级 / gb2312 转码 / 慢站，第二批接入。
- **T3 需渲染或逆向**：JS 单页应用 / WAF / 接口未逆向，暂缓，用粘贴箱或上级聚合源弥补。
- **P 粘贴箱**：无可用网页栏目（仅公众号/邮箱/JS 门户），人工粘链接入库。

---

## T1 静态规整（MVP 首批 13 个）

| 源 | 列表页/接口 URL | 覆盖 | 验证 | 备注 |
|---|---|---|---|---|
| 广东法院网·工作公告 | https://www.gdcourts.gov.cn/gsxx/fayuangonggao/index.html | 全省法检招聘聚合主源（书记员/审判辅助/选调公示） | 已验证 | 全省核心，优先做 |
| 广东省人社厅·事业单位招聘公告 | https://hrss.gd.gov.cn/zwgk/sydwzp/zpgg/index.html | 全省事业单位（含法律岗），约200页 | 已验证 | 静态分页 index_2… |
| 广州市人社局·事业单位公开招聘 | https://rsj.gz.gov.cn/ywzt/rszdgg/sydwgkzp/ | 广州市直事业单位 | 已验证 | 旧域名 hrss.gz.gov.cn 已失效；分页 index_2…index_27 |
| 深圳市人社局·公职人员招考 | https://hrss.sz.gov.cn/gzryzk/ | 深圳公职/选聘转发，全省最活跃 | 已验证 | 静态列表 |
| 中山市人社局·事业单位公开招聘 | http://hrss.zs.gov.cn/xxgk/rsxx/sydwgkzp/index.html | 中山事业单位（另有雇员招聘 /xxgk/rsxx/gyzp/） | 已验证 | 静态 |
| 珠海市人社局·公职招考 | https://zhrsj.zhuhai.gov.cn/zw/tzgg/gzzk/index.html | 珠海公职招考 | 已验证 | 正确域名 zhrsj.zhuhai.gov.cn |
| 佛山市人社局·机关事业单位招录 | https://hrss.foshan.gov.cn/zwgk/jgsydwzl/index.html | 佛山机关事业单位 | 已验证 | 静态 |
| 广东省检察院·通知公告 | http://www.gd.jcy.gov.cn/tzgg/ | 全省检察系统辅助人员招录 | 已验证 | **https 证书异常须用 http**；gb2312 编码须转码 |
| 佛山市律师协会·招聘信息 | https://www.gdlawyers.net/recruit/index.html | 律所招聘 4209 条/281 页，最佳律协源 | 已验证 | 详情 /recruit/details.html?id=N |
| 惠州市律师协会·律所招聘 | https://new.hzlawyers.cn/list/recruitment_info | 律所招聘 14 页，更新至 2026-08 | 已验证 | 分页 ?page=N，详情 /show/{ID} |
| 中南财经政法大学就业中心 | 接口 https://jyzx.zuel.edu.cn/api/publicly/recruit/list?page=1&limit=20&type=1 | 校招公告(type=1)/实习(type=2)，2万+条，majors 含"法学" | 已验证 | **Vue SPA，必须对接 JSON 接口**（免登录，code=0，字段 title/companyName/nature/validTime/createTime/education/majors/number） |
| 广东外语外贸大学·招聘职位 | https://career.gdufs.edu.cn/job-list | 广外就业网职位 | 已验证 | 详情 /web/Index/notice-detail?id=N |
| 广州大学·职位信息 | https://jy.gzhu.edu.cn/job-list | 广州大学就业网职位 | 已验证 | 同广外平台风格；job.gzhu.edu.cn 返回 403 勿用 |

## T2 可抓有毛刺（第二批）

| 源 | URL | 备注 |
|---|---|---|
| 惠州市政府门户·人事信息 | http://www.huizhou.gov.cn/zwgk/rsxx/index.html | 人社局无独立域名挂靠门户；公告混杂需关键词过滤 |
| 东莞市人社局·公开招聘 | http://dghrss.dg.gov.cn/xwzx/gsgg/gkzp/index.html | 域名是 dghrss.dg.gov.cn（hrss.dg.gov.cn 已失效）；混杂公示需过滤 |
| 江门市人社局·事业单位招聘 | http://www.jiangmen.gov.cn/bmpd/jmsrlzyhshbzj/sylm/rsks/syks/ | 挂靠门户部门频道；更新中等 |
| 韶关市人社局·通知公告 | https://www.sg.gov.cn/bmpdlm/rlzyhshbzj/tzgg/ | **域名是 www.sg.gov.cn（shaoguan.gov.cn 无解析）**；内容混杂需过滤，配合省厅 sydwzp 弥补 |
| 佛山市中院·工作公告 | https://www.fszjfy.gov.cn/gzgg/ | 无专门招聘栏目，招聘多走广东法院网 |
| 东莞市中院·综合公告 | https://www.dgcourt.gov.cn/News/Default.asp?cataid=00020001 | 旧式 ASP，首访慢需长超时 |
| 珠海市中院·本院公告 | http://www.zhcourt.gov.cn/article/index/id/M8zJNTBIMiAOAAA.shtml | **https 证书错误，必须 http** |
| 深圳市检察院·通知公告 | https://www.shenzhen.jcy.gov.cn/ygjw/tzgg/ | 域名是 shenzhen.jcy.gov.cn（非 sz）；有辅助人员招录 |
| 珠海市检察院·通知公告 | http://www.zhuhai.jcy.gov.cn/jwgk/tzgg/ | 需带 www |
| 佛山市检察院·通知公告 | https://www.fsjcy.gov.cn/jwgk/tzgg/index.html | https 可用 |
| 中山市检察院·文件公开 | https://zhongshan.jcy.gov.cn/xxgk/wjgk/list/50.html | 招聘全流程（公告→公示）首页可见 |
| 肇庆市检察院·通知公告 | http://www.zqjcy.gov.cn/jwgk/tzgg/ | http 强跳 https 可访问 |
| 广东组织工作网·通知公告 | https://www.gdzz.gov.cn/tzgg/index.html | 省考/选调公告入口；**gdzz.cn 已被第三方占用勿用** |
| 广东人事考试网·公务员考试 | https://rsks.gd.gov.cn/wsbs/gwyks/index.html | 省考兜底源 |
| 广东人事考试网·其他考试 | https://rsks.gd.gov.cn/wsbs/qtks/index.html | 事业单位集中招聘/三支一扶兜底 |
| 广州市国资委·通知公告 | https://gzw.gz.gov.cn/xw/tzgg/ | 直属企业选聘、急需人才引进（含法务） |
| 深圳市国资委·社会招聘 | https://gzw.sz.gov.cn/gzrc/shzp/ | 市属国企公开招聘 |
| 广东国企招聘平台（省国资委） | https://www.gdrc.com/index.php?m=&c=state_enterprise&a=index | 社招/校招子栏目 c=socialRecruitment / c=campusRecruitment |
| 中伦·职位列表 | https://www.zhonglun.com/career/jobs_1 | 红圈所唯一可用职位列表，8 页，含广深筛选，翻页 jobs_2…jobs_8 |
| 广信君达·招贤纳士 | https://www.etrlawfirm.com/cn/zxns/index_30.aspx?lcid=8 | 结构化职位表（职位/学历/人数/地点） |
| 金桥百信·广纳英才 | https://www.gdjqbx.com/recruittalents/list.aspx?lcid=0 | 职位列表 2 页 14 条 |
| 连越·人才招聘 | https://www.gdlianyue.com/recrui.php | 列表简单，更新频率低 |
| 广东省国资委·通知公告 | https://gzw.gd.gov.cn/tzgg/index.html | 国企招聘稿件转发，非专门栏目 |

## T3 需渲染/逆向（暂缓）

| 源 | URL/情况 | 缺口 |
|---|---|---|
| 广东省考系统 | https://ggfw.hrss.gd.gov.cn/gwyks/index.do | 公告区 JS 动态加载；旧 gdrsks.gov.cn 已失效 |
| 深圳市中院 | https://www.szcourt.gov.cn/ | 整站 JS 渲染；基层院静态页可补（福田 https://www.ftcourt.gov.cn/xwzx/fygg/qtgg/ 已验证） |
| 惠州市中院 | https://www.hzzy.gov.cn/ | SPA，栏目无法静态定位 |
| 广州市检察院 | https://guangzhou.jcy.gov.cn/ | JS 渲染；区院为 guangzhouxx/hz/th.jcy.gov.cn 模式 |
| 东莞市检察院 | https://www.dongguan.jcy.gov.cn/ | JS 渲染 |
| 肇庆市人社局 | https://www.zhaoqing.gov.cn/zqrsj/gkmlpt/index | **网站迁移中，列表 JS 动态加载，子栏目 404，全清单最高风险**；招聘信息暂靠省厅栏目覆盖 |
| 南方电网招聘 | https://zhaopin.csg.cn/ | SPA 动态渲染 |
| 深圳市律师协会·招聘信息 | https://www.szlawyers.com/ | 栏目确认存在且体量大，但整站 JS 渲染拿不到 href |
| 中山大学·校园招聘 | https://career.sysu.edu.cn/campus | 列表异步注入，需无头浏览器或逆向 XHR |
| 暨南大学/广东财经大学 | career.jnu.edu.cn 门户 + bysjy.com.cn 平台 | 列表在第三方 bysjy 平台，SPA 需渲染；门户公务员/选调静态栏目可抓 |
| 华工/深大/华师就业网 | scut.ncss.cn / job.szu.edu.cn / career.scnu.edu.cn | 境外环境超时未验证，需境内复测 |
| 国家大学生就业服务平台 | https://www.ncss.cn/student/jobs/index.html | 有"法律类"职类筛选但为页内 JS，无固定法学频道 URL；作补充源 |

## P 粘贴箱兜底（无可用网页栏目）

| 渠道 | 情况 |
|---|---|
| 广州市律师协会 | 新版官网无招聘栏目（gzlawyer.org.cn/notices 已验证），律所招聘走"律兴"APP/公众号 |
| 珠海/韶关/中山律协 | 官网无招聘栏目（韶关 sglawyer.org.cn 已验证无）；中山 gdzslx.com 实为点援平台 |
| 东莞律协 | dgla.org.cn TLS 证书错配（*.homolo.net），暂无法抓取 |
| 金杜 | careers 页为介绍型，无职位列表；职位走公众号+内推 |
| 方达 | talent 页无职位列表，走公众号/邮箱 |
| 海问 | 官网 haiwen-law.com SSL 失效，仅公众号 |
| 汉坤 | 职位在北森 hankun.zhiye.com，JS 渲染 |
| 竞天公诚 | 整站 JS 渲染 |
| 君合 | junhe.com/careers 入口可用，办公室子页可做二级适配器（后续） |
| 华商 | 仅招聘流程+邮箱 hr@huashang.cn，无在线职位 |
| 律新社/智合 | 无可用官网（DNS 失败/证书过期），仅公众号 |
| 惠州/江门/韶关检察院 | 无可用静态官网域名，招聘主要经"广东检察"公众号 |
| 国智律所 | gdguozhi.com 443 拒绝连接 |

## 摸排发现的域名陷阱（配置时必读）

1. 网上流传的多个"人社局域名"已失效：hrss.gz.gov.cn、hrss.zhuhai.gov.cn、hrss.huizhou.gov.cn、hrss.dg.gov.cn、rsj.sg.gov.cn、shaoguan.gov.cn 均 DNS 不存在，以上表为准。
2. gdzz.cn 已被第三方小说站占用，官方是 gdzz.gov.cn。
3. 需 http 降级：省检察院（证书链异常）、珠海中院（证书指向无关域名）。
4. 需 gb2312 转码：省检察院。
5. 需 WAF 对策：韶关门户（www.sg.gov.cn）直抓路径易 403。

---

## 实施期校准记录（2026-09-15，13 源真实录制后逐条核对）

### 选定的容器选择器

| slug | 列表容器 | 标题来源 | 日期 | 备注 |
|---|---|---|---|---|
| gdcourts | `ul.list li` | `a[title]` | `span.time` | |
| gd_jcy | `tr` + `a.b16[href^="./20"]` | 链接文本 | `span.h12` | 嵌套表格会让同一 `<a>` 被多个 `tr` 命中，必须按 URL 去重 |
| hrss_gd | `ul.list li` | `a[title]` | `span.pubDate` | |
| hrss_gz | `ul.infoList li` | `a[title]` | `span.time` | 列表头部混有"网上报名"子栏目须知，用 `exclude_url=[sydwzpwsbm]` 排除 |
| hrss_sz | `div.AllListCon li` | `a[title]` | `span` | 页面文本被"…"截断，必须取 title 属性 |
| hrss_zs | `ul.news_list li` | 链接文本 | `span` | |
| hrss_zh | `ul.news-list-02 li` | `a[title]` | `span.time` | |
| hrss_fs | `div.list_rightbox li` | `a[title]` | `span.time` | 日期在标题之前 |
| sg_gov | `div.pageList ul li` | `a[title]` | `span.time` | **栏目以法院送达公告为主，招聘稿件每页仅约 2 条**，需 `title_keywords` 过滤 |
| fs_lvxie | `div.recruit.ny a[href*="recruit/details"]`（`link_sel="self"`） | `a[title]` | 无 | 一条 `<div>` 容器里并列多个 `<a>`，每个 `<a>` 就是一个律所 |
| hz_lvxie | `a[href^="/show/"]`（`link_sel="self"`） | `div.text-base` | `div.text-xs div` | Tailwind 站，详情正文用 `div.rich-text` |
| gdufs / gzhu | `div.jobs-list div.col-xs-6` | `div.job-name` | `div.job-time` | 单位取 `div.job-company` |
| zuel | JSON 接口 | — | — | 见下 |

分页规律三种：政务 CMS `index.html`→`index_2.html`…；律协 `?page=N`；高校平台 `?p=N`。

### 新发现（摸排时未记录的）

1. **深圳人社 https 在本机 OpenSSL 3 下完全不可用**（`[SSL: BAD_ECPOINT]`，verify 关了也一样），
   但 **http 正常**。列表页里却是绝对 https 链接，因此需要 `url_scheme: "http"` 在解析阶段改写协议。
2. **高校就业平台支持站内关键词检索**：`.../job-list?keyword=法务` 能直接返回法务专员/法务助理，
   `?keyword=律师` 返回律师助理/仲裁院书记员。这比"全量拉取后本地过滤"精准得多。
   注意该平台详情页是 JS 渲染，HTML 里拿不到"专业要求"，只能靠检索词命中。
3. **中南财接口的 `majors=` 参数语义不完整**：`majors=法学` 只返回 4 条（且匹配逻辑不透明），
   而按返回记录的 `majors` 字段在本地做子串匹配，近期记录里约 1/3 命中。因此改用
   "按页拉取 + 本地过滤"，并在正文里写入专业/学历/人数/截止等字段。
4. **律协站点的"日期"常常不是投递截止日**：广东律师网列表页无日期，detail 页的日期是律所
   资料发布时间。这类源的 deadline 一律留空，由用户在详情页手工确认。
5. **政务栏目的稿件性质需要分流**：广东法院网/深圳人社/中山人社等栏目里，事后结果公示
   （拟聘用人员名单公示、笔试成绩、合格分数线）占比很高（首批 299 条里 68 条），
   它们天然没有截止日期，混在"岗位列表"里就是噪音。系统按标题+正文前 600 字判为
   `opening`/`result`/`info`，默认只显示 `opening`。律所招聘栏目与校园职位板
   （条目本身就是岗位）用源级 `notice_kind: "opening"` 直接指定，不靠标题猜。

### 需 WAF / 慢站对策的源

- `hrss_sz`：慢（单页详情常 > 20 秒），详情抓取预算降到 60 秒。
- `hrss_gz`：详情慢，预算 60 秒。
- `sg_gov`：直抓路径易 403，实际用正式 UA 抓 index.html 可通（本次录制成功）。


---

## 2026-09-15 二轮扩容（14 → 29 源）摸排结论

四路并行实测（高校 / 律协 / 国企 / 其他权威），全部真抓验证，共测 60+ URL。

### 新增 15 源
高校：gduf（广东金融学院）、gcc（广州商学院）——与广外/广大同平台，配置照抄；
swupl（西南政法，cqbys 平台首页 SSR 块，详情页 SSR 可抓）。
律协：gz_lvxie（广州，JSP 片段接口 GET 即可，no_detail）、sz_lvxie（深圳，SSR 表格，
列表自带截止日列，tbody 前两行是登录弹窗表格需按"有无链接"过滤）、zs_lvxie（中山，
日期拆"日+年月"两节点，dateparse 已做归一化）、jm_lvxie（江门，list_url 必须带尾斜杠）。
国企：gzw_gd（省国资委百万英才汇南粤专栏，静态，8 页全量）、ggfw_gq（省人社厅国企
招聘专区，POST JSON 接口，从前端 chunk 逆向；body 需带 aab020=单位性质码过滤，
否则混入配送员/家政岗；须带 Referer 否则空数据）、yuexiu（越秀大易系统 JSON，
positionName 参数服务端精准过滤，519→7）、geg（广东能源集团，静态，keep_keywords 过滤）。
其他：gdzz_luqu（广东组织工作网·公务员录用，省考+选调首发）、hrss_dg（东莞人社，
域名是 dghrss.dg.gov.cn，hrss.dg.gov.cn 是无效域名）、sg_rsrc（韶关人社人事人才栏，
比 tzgg 聚焦）、army_81rc（军队人才网文职招考，用 http）。

### 事实修正
- www.gdlawyers.net 实测是"佛山市律师协会"官网（页脚有主办单位声明），不是省律协；
  fs_lvxie 的显示名已改为"佛山市律师协会·律所招聘"。
- 深圳律协真实域名 www.szlawyers.com；用户常见的 szlawyer.org.cn 已 502。
- 广东省国资委官网是 gzw.gd.gov.cn（不是 gdei.gd.gov.cn）。

### 摸排后放弃的源（都有实测依据，别再试）
- 高校：华工（CAS 登录墙）、暨大（平台维护）、深职大（SPA 需登录）、华政（403 WAF）、
  法大（JS 跳转壳/412）、汕大（DNS 不存在）、广海（子域全不存在）
- 高校暂缓（值得逆向 XHR）：中山大学/广工/深大（jysd 平台，一次逆向通三校）；
  五邑/韶关学院/广财/华师/南科大（bysjy 平台 EJS 模板，一次逆向通五校）
- 律协：东莞（Nuxt 3 JS 渲染 + 证书主机名错配）、珠海（无招聘栏目）、
  韶关律协（无招聘栏目）、肇庆（无招聘栏目）、省律协（无独立招聘站）
- 国企：广新（Angular SPA）、广州工控（JS）、深投控（跳转壳）、深圳能源（502）、
  广晟/粤海（502）、机场集团（HTTP 468 反爬）、国聘 iguopin（接口需签名，放弃）、
  广东交通集团（结构完美但更新停在 2023）
- 其他：省考录系统（公告已由组织工作网覆盖）、人事考试网（招聘稿占比 <20%）、
  肇庆人社（gkmlpt JS 渲染）、广东人才网/南方人才网（旧闻+JS）、江门人社
  （本机网络不可达，配置可写但暂缓激活，站点本身价值高——法院/检察辅助招聘）
