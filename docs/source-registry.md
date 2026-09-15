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
