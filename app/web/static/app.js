/* 主题切换 + 顶栏滚动阴影。
 *
 * 为什么要单独一份：首帧的主题必须在 <head> 里用内联脚本写死（否则会闪白/闪黑），
 * 但"交互"没必要塞进 HTML，放这里由浏览器缓存。
 * 三态：auto（跟随系统）→ light → dark 循环，选择存 localStorage。
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "theme";
  var ORDER = ["auto", "light", "dark"];
  var LABEL = { auto: "跟随系统", light: "浅色", dark: "深色" };
  var mq = window.matchMedia("(prefers-color-scheme: dark)");

  function resolve(intent) {
    if (intent === "light" || intent === "dark") return intent;
    return mq.matches ? "dark" : "light";
  }

  function paint(intent, animate) {
    if (animate) {
      root.classList.add("theme-anim");
      window.setTimeout(function () { root.classList.remove("theme-anim"); }, 260);
    }
    root.dataset.themeIntent = intent;
    root.dataset.theme = resolve(intent);
    var btn = document.querySelector("[data-theme-toggle]");
    if (btn) {
      btn.dataset.intent = intent;
      var text = "主题：" + LABEL[intent] + "（点击切换）";
      btn.setAttribute("title", text);
      btn.setAttribute("aria-label", text);
    }
  }

  function stored() {
    try { return localStorage.getItem(KEY) || "auto"; } catch (e) { return "auto"; }
  }

  // 首帧可能已由内联脚本写好，这里按存储值再对齐一次（含按钮文案）
  paint(stored(), false);

  // 跟随系统时，系统主题变了要跟着变
  var onSystemChange = function () {
    if (root.dataset.themeIntent === "auto") paint("auto", false);
  };
  if (mq.addEventListener) mq.addEventListener("change", onSystemChange);
  else if (mq.addListener) mq.addListener(onSystemChange);

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var cur = root.dataset.themeIntent || "auto";
    var next = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length];
    try { localStorage.setItem(KEY, next); } catch (err) { /* 隐私模式下忽略 */ }
    paint(next, true);
  });

  // 顶栏：一旦滚动就加一层浅阴影，让内容与栏之间有条界线
  var top = document.querySelector(".top");
  if (top) {
    var onScroll = function () { top.classList.toggle("scrolled", window.scrollY > 2); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
})();
