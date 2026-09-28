/* 界面语言切换（中 / EN）。
 *
 * 与主题切换同一套路：默认中文，服务端渲染的 HTML 就是中文原文；
 * 选了 EN 才由这里把带 data-i18n 标记的文案换成英文。选择存 localStorage，
 * <html lang> 由 <head> 内联脚本在首帧前写好（和主题一样不闪）。
 *
 * 标记约定（模板里用）：
 *   data-i18n        —— 替换该元素的文本内容
 *   data-i18n-ph     —— 替换 placeholder
 *   data-i18n-title  —— 替换 title（悬停提示）
 *   data-i18n-aria   —— 替换 aria-label
 *   data-i18n-args   —— 可选 JSON，用于字典值里的 {name} 占位符（数字等动态值）
 *
 * 动态数据（岗位标题、单位名、城市、来源名等）不翻译，照原样显示。
 */
(function () {
  "use strict";

  var KEY = "lang";
  var root = document.documentElement;

  /* 英文文案表。中文不需要字典——服务端渲染的原文就是中文。 */
  var EN = {
    /* 顶栏 / 全局 */
    title_home: "Legal Job Tracker",
    title_detail: "{t} · Legal Job Tracker",
    title_profile: "Profile · Legal Job Tracker",
    title_rec: "Matched jobs · Legal Job Tracker",
    brand: "Legal Job Tracker",
    skip: "Skip to content",
    nav_jobs: "Jobs",
    nav_board: "Board",
    nav_reco: "Matches",
    nav_paste: "Paste box",
    nav_health: "Source health",
    nav_profile: "Profile",
    nav_settings: "Settings",
    nav_export: "Export",
    theme_tip_auto: "Theme: follows system (click to change)",
    theme_tip_light: "Theme: light (click to change)",
    theme_tip_dark: "Theme: dark (click to change)",
    btn_collecting: "Collecting…",
    alert_urgent: "jobs close within 3 days",
    alert_view: "View them",

    /* 固定枚举：岗位类型 */
    jt_lawfirm: "Law firm",
    jt_public: "Public sector",
    jt_legal_counsel: "In-house",
    jt_intern: "Internship",
    jt_unknown: "Other",

    /* 公告性质 */
    nk_opening: "Open",
    nk_result: "Result notice",
    nk_info: "Other info",
    nk_opening_only: "Open jobs only",
    nk_all: "All posts",
    opt_only_result: "Only result notices",
    opt_only_info: "Only other info",

    /* 列表页 */
    list_n_jobs: "{n} jobs",
    list_filtered: " (filtered)",
    list_showing: "· showing first {n}",
    sort_dl_meta: "· sorted by deadline",
    sort_pub_meta: "· sorted by publish date",
    sort_new_meta: "· sorted by date added",
    bulk_off: "Bulk",
    bulk_on: "Exit bulk",
    stat_opening: "Open jobs",
    stat_opening_title: "All open jobs",
    stat_d3: "Due within 3 days",
    stat_d7: "Due within 7 days",
    stat_fresh: "New today",
    stat_nodeadline: "No deadline",
    stat_nodeadline_title: "Jobs without a stated deadline (often email applications or "
      + "long-term openings). They never trigger urgency alerts and are easy to miss.",
    ph_search: "Search title / org / body / notes",
    aria_jobtype: "Job type",
    aria_city: "City",
    aria_emp: "Employment type",
    aria_kind: "Notice kind",
    aria_status: "Status",
    aria_sort: "Sort",
    aria_joblist: "Job list",
    aria_pick: "Select",
    aria_actions: "Actions",
    opt_all_type: "All types",
    opt_all_city: "All cities",
    opt_all_emp: "All employment",
    opt_all_status: "All statuses",
    st_new: "Unread",
    st_read: "Read",
    st_pending: "Pending review",
    st_archived: "Archived",
    opt_by_dl: "By deadline",
    opt_by_pub: "By publish date",
    opt_by_new: "By date added",
    f_clear: "Clear",
    flash_archived: "Archived {n} jobs",
    flash_restored: "Restored {n} jobs",
    f_undo: "Undo",
    f_got: "Dismiss",
    b_all: "Select all",
    b_sel_pre: "Selected: ",
    b_sel_post: "",
    b_read: "Mark read",
    k_archive: "Archive",
    k_restore: "Restore",
    b_note: "Actions return to the current filtered view",
    empty_none: "No matching jobs.",
    empty_a: "Open the",
    empty_b: "and click \u300cCollect now\u300d, or paste an official-account link in the",
    empty_c: ".",
    h_deadline: "Due",
    h_type: "Type",
    h_city: "City",
    h_title: "Title",
    h_org: "Org",
    h_src: "Source",

    /* 列表行 */
    row_roll: "Rolling",
    t_roll: "Long-term opening: apply by email as the employer requires",
    t_nodeadline: "No deadline stated in the notice",
    row_nsrcs: "{n} sources",
    row_follow: "Track",
    t_follow: "Add to application tracking (no need to open the detail page)",
    row_unfollow: "Untrack",
    t_unfollow: "Stop tracking (the job goes back to untracked)",
    t_open: "Open original ({s})",
    t_archive: "Archive (find it later under the \u300cArchived\u300d filter)",

    /* 详情页 */
    back_list: "\u2190 Job list",
    k_deadline: "Due",
    k_org: "Org",
    k_pub: "Published",
    k_kind: "Kind",
    k_status: "Status",
    k_merge: "Merged",
    n_sources: "{n} sources",
    k_added: "Added",
    weak_match: "weakly related to your profile",
    match_chip: "Match {n}",
    act_status: "Application status: ",
    act_view_board: "Manage on board",
    act_track: "Track application",
    act_mark_read: "Mark read",
    act_edit: "Edit fields",
    k_orig: "Original",
    k_srcs: "Sources",
    k_notes: "Notes",
    snap_h: "Body snapshot (local archive)",
    snap_key_h: "Key info",
    snap_raw: "Raw text",
    snap_none: "No body snapshot (this source does not fetch detail pages, or the fetch "
      + "failed at collection time). See the original links above.",

    /* 投递状态（存储值仍是中文，这里只管显示） */
    as_todo: "To apply",
    as_sent: "Applied",
    as_exam: "Written test",
    as_iv: "Interview",
    as_offer: "Offer",
    as_rej: "Rejected",
    prev_0: "Back to To apply",
    prev_1: "Back to Applied",
    prev_2: "Back to Written test",
    prev_3: "Back to Interview",
    prev_4: "Back to Offer",
    next_1: "Applied \u2192",
    next_2: "Written test \u2192",
    next_3: "Interview \u2192",
    next_4: "Offer \u2192",
    next_5: "Rejected \u2192",
    ph_note: "Note",
    pfx_note: "Note: ",

    /* 投递看板 */
    board_h: "Application board",
    board_count: "{n} tracked in total",
    board_help: "\u2190 step back \u00b7 add a note and advance to the next step",
    board_empty_1: "Nothing tracked yet. Open any job's detail page and click "
      + "\u300cTrack application\u300d and it shows up here;",
    board_empty_2: "then update the status and add a note here at each step "
      + "(apply \u2192 written test \u2192 interview \u2192 offer).",

    /* 粘贴箱 */
    paste_h: "Paste box",
    paste_meta: "Grab recruitment articles from official accounts and other pages "
      + "without a fixed column",
    paste_fetch: "Fetch",
    paste_help: "After you paste a link, the system fetches the body and auto-extracts "
      + "title, city, deadline and other fields, then lets you review before saving. "
      + "If fetching fails (some official-account articles require login / risk "
      + "control), save the page manually, open the original link in a browser, and "
      + "enter the key info via \u300cEdit fields\u300d on the job detail page.",
    err_fetch: "Fetch failed: ",

    /* 源健康 */
    health_h: "Source health",
    health_n: "{n} sources",
    health_bad: "{n} failing",
    health_run_all: "Collect all sources now",
    health_n_grp: "{n} sources",
    th_src: "Source",
    th_name: "Name",
    th_lastok: "Last success",
    th_fails: "Fails",
    th_err: "Last error",
    health_collect: "Collect",
    health_empty_a: "No sources yet. Run",
    health_empty_b: ".",
    logs_h: "Recent collection logs",
    th_time: "Time",
    th_ins: "Added",
    th_merged: "Merged",
    th_err2: "Error",
    no_logs: "No logs yet",

    /* 分类名（与 classify.SOURCE_CATEGORIES 对应） */
    "cat_top-law": "Top law schools",
    "cat_gd-univ": "Guangdong universities",
    cat_soe: "SOEs",
    cat_gov: "Government agencies",
    cat_lawfirm: "Bar associations",
    cat_talent: "Talent markets",

    /* 设置 */
    settings_h: "Settings",
    sec_collect: "Collection",
    set_toast: "Pop a Windows desktop notification after each collection",
    set_toast_hint_a: "Requires",
    set_toast_hint_b: " first.",
    k_save: "Save",
    set_sched_k: "Schedule",
    set_sched_v: "Automatic incremental collection at 08:05 every day "
      + "(while the service is running)",
    set_manual_k: "Manual",
    set_manual_b: " page lets you collect a single source or all sources right away",
    sec_export: "Export",
    set_exp_open: "Open jobs",
    dl_xlsx: "Download xlsx",
    set_exp_open_v: " (matches the list's default view)",
    set_exp_all: "All posts",
    set_exp_all_v: " (including result notices and info posts)",
    sec_data: "Data",
    set_loc_k: "Location",
    set_loc_v: " (local SQLite; no data is ever uploaded to any server)",
    set_snap_k: "Snapshots",
    set_snap_v: " (archived detail-page bodies \u2014 still readable if the source "
      + "deletes the post)",
    set_cfg_k: "Source config",
    set_cfg_v: " \u2014 re-run that script after changing it",

    /* 个人画像 */
    profile_h: "Profile",
    profile_src: "Source: {s}",
    profile_src_manual: "Source: filled by hand",
    to_reco: "See matched jobs \u2192",
    to_reco_btn: "See matched jobs",
    err_no_parser_a: "This format needs an extra dependency: run",
    err_no_parser_b: "in the venv and retry (.txt / .md upload directly).",
    err_empty: "No text found in the file. Scanned (image) PDFs cannot be parsed "
      + "\u2014 use a text-based PDF or .docx.",
    err_too_big: "The file exceeds 8MB \u2014 compress it and retry.",
    prof_empty_a: "No profile yet. Upload a resume to generate one, or fill the form "
      + "below by hand.",
    prof_empty_b: "The profile stays in local",
    prof_empty_c: " and never leaves this machine.",
    sec_upload: "Upload resume",
    btn_parse: "Parse",
    upload_hint: "Supports PDF / Word / plain text. Parsing is rule-based extraction "
      + "and not guaranteed complete \u2014 review and fix the result on the right; "
      + "the more accurate the profile, the more useful the matches.",
    sec_parsed: "Parsed result",
    k_skills: "Skills",
    k_exp: "Experience",
    k_int_city: "Target cities",
    k_int_type: "Target types",
    profile_kw: "Words actually used in scoring ({n})",
    profile_kw_hint: "If recommendations feel off, this list is usually what to adjust.",
    sec_edit: "Edit profile",
    f_name: "Name",
    ph_optional: "optional",
    f_years: "Years of experience",
    ph_fresh: "enter 0 for new grads",
    f_cities: "Target cities",
    ph_cities: "Guangzhou, Shenzhen, Foshan",
    f_types: "Target job types",
    hint_type: "Worth +22 when it matches the job's type \u2014 the heaviest factor.",
    f_skills: "Skills / keywords",
    ph_skills: "contract review, legal research, litigation, bar admission\u2026",
    hint_skills: "Separate with commas or line breaks; hits in the job body add points.",
    f_exp: "Experience types",
    ph_exp: "law firm, court, in-house",
    hint_exp: "Extra points when it matches the job type "
      + "(e.g. law-firm experience for a law-firm job).",
    f_edu: "Education",
    ph_edu: "bachelor's",
    btn_save_profile: "Save profile",
    btn_cancel: "Cancel",

    /* 推荐岗位 */
    reco_h: "Matched jobs",
    reco_meta: "Sorted by match with your profile",
    to_profile: "Adjust profile \u2192",
    stat_scored: "Jobs scored",
    stat_top: "Strong matches (\u226560)",
    reco_basis: "Scoring basis: target city (\u00b126) \u00b7 job type (+22/\u22124) "
      + "\u00b7 keyword hits (title hits weigh \u00d72, capped at 26) \u00b7 relevant "
      + "experience (+14) \u00b7 education (+8 if satisfied / \u221214 if short) "
      + "\u00b7 experience requirement (\u221210 if short / +6 if satisfied or "
      + "new-grad-friendly) \u00b7 clear deadline (+6). Every reason is written under "
      + "each job; if a match feels wrong, adjust your profile.",
    reco_empty_a: "No jobs to recommend yet. Go to the",
    reco_empty_b: "and run a collection.",
    h_match: "Match",
    h_job: "Job",
    h_why: "Why",
    t_match: "Match {n}/100",
    roll_short: "Long-term opening",
    reco_weak: "Base score only \u2014 profile and job are weakly related",
    tag_tracking: "Tracking",
    t_open2: "Open original",

    /* 修改字段 */
    back_job: "\u2190 Back to job",
    confirm_meta: "Auto-extracted fields may be wrong \u2014 check before saving",
    f_title: "Title",
    f_jobtype: "Job type",
    f_deadline: "Deadline",
    ph_deadline: "YYYY-MM-DD; leave empty if the notice doesn't state one",
    ph_notes: "e.g. needs bar admission / contacted a senior / written test in October",
    opt_any: "Any"
  };

  function current() {
    try { return localStorage.getItem(KEY) === "en" ? "en" : "zh"; }
    catch (e) { return "zh"; }
  }

  /* {name} 占位符替换；args 里没有的键原样保留，方便发现问题 */
  function fmt(str, args) {
    if (!args) return str;
    return str.replace(/\{(\w+)\}/g, function (m, k) {
      return Object.prototype.hasOwnProperty.call(args, k) ? String(args[k]) : m;
    });
  }

  function put(el, attr, key, en) {
    var store = el.__lji18n || (el.__lji18n = {});
    /* 首次替换前把原文存起来，切回中文时原样恢复 */
    if (!(attr in store)) {
      store[attr] = (attr === "text") ? el.textContent : el.getAttribute(attr);
    }
    var v;
    if (en) {
      var t = EN[key];
      if (t == null) return;
      var args = null;
      var raw = el.getAttribute("data-i18n-args");
      if (raw) {
        try { args = JSON.parse(raw); } catch (e) { args = null; }
      }
      v = fmt(t, args);
    } else {
      v = store[attr];
      if (v == null) v = "";
    }
    if (attr === "text") el.textContent = v;
    else el.setAttribute(attr, v);
  }

  function walk(en) {
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      put(el, "text", el.getAttribute("data-i18n"), en);
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      put(el, "placeholder", el.getAttribute("data-i18n-ph"), en);
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      put(el, "title", el.getAttribute("data-i18n-title"), en);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      put(el, "aria-label", el.getAttribute("data-i18n-aria"), en);
    });
  }

  function paintSwitch(lang) {
    document.querySelectorAll("[data-lang-set]").forEach(function (b) {
      var on = b.getAttribute("data-lang-set") === lang;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function apply(lang, persist) {
    if (persist) {
      try { localStorage.setItem(KEY, lang); } catch (e) { /* 隐私模式下忽略 */ }
    }
    root.lang = (lang === "en") ? "en" : "zh-CN";
    root.dataset.lang = lang;
    paintSwitch(lang);
    walk(lang === "en");
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang: lang } }));
  }

  /* 首帧时 <head> 内联脚本已写好 lang；这里把字典挂到全局并完成首次替换 */
  window.LJI18N = {
    current: current,
    /* 只在 EN 模式下给词，中文一律回落到模板里的原文 */
    t: function (key) { return current() === "en" ? (EN[key] != null ? EN[key] : null) : null; }
  };

  apply(current(), false);

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-lang-set]");
    if (!btn) return;
    apply(btn.getAttribute("data-lang-set") === "en" ? "en" : "zh", true);
  });
})();
