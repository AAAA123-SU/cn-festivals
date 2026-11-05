// 无浏览器环境下的页面脚本冒烟测试：
// 用最小 DOM 桩执行 docs/index.html 中的内联脚本，验证数据注入与渲染逻辑不报错。
// 用法：node tools/smoke_page.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) {
  console.error("未找到内联脚本");
  process.exit(1);
}

const nodes = new Map();
function makeEl(id) {
  const el = {
    id,
    textContent: "",
    innerHTML: "",
    href: "",
    children: [],
    dataset: {},
    classList: { add() {}, remove() {} },
    addEventListener() {},
    setAttribute() {},
    getAttribute() { return null; },
    closest() { return null; },
  };
  nodes.set(id, el);
  return el;
}

const sandbox = {
  console,
  URL,
  clearTimeout() {},
  setTimeout: () => 0,
  location: { href: "https://example.github.io/cn-festivals/" },
  navigator: { clipboard: { writeText: async () => {} } },
  getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
  document: {
    getElementById: (id) => nodes.get(id) || makeEl(id),
    createRange: () => ({ selectNodeContents() {} }),
    querySelectorAll: () => [],
  },
};

let failed = false;
try {
  vm.runInNewContext(match[1], sandbox, { timeout: 5000 });
} catch (err) {
  console.error("脚本执行失败:", err.message);
  failed = true;
}

const checks = [];
function expect(name, cond, extra = "") {
  checks.push({ name, ok: !!cond, extra });
  if (!cond) failed = true;
}

const stats = nodes.get("stats");
const upcoming = nodes.get("upcoming-list");
const yearList = nodes.get("year-list");
const tabs = nodes.get("year-tabs");
const official = nodes.get("official-list");
const webcal = nodes.get("btn-webcal");
const url = nodes.get("ics-url");

expect("统计区已渲染", stats && stats.innerHTML.includes("覆盖年份"));
expect("近期节日条数 ≥ 5", upcoming && (upcoming.innerHTML.match(/class="row"/g) || []).length >= 5,
  upcoming ? String((upcoming.innerHTML.match(/class="row"/g) || []).length) : "缺省");
expect("全年一览已渲染", yearList && (yearList.innerHTML.match(/class="row"/g) || []).length > 5);
expect("年度切换按钮存在", tabs && tabs.innerHTML.includes("aria-selected"));
expect("官方年度说明已渲染", official && official.innerHTML.includes("年"));
expect("webcal 链接已生成", webcal && webcal.href.startsWith("webcal://"));
expect("订阅地址已展示", url && url.textContent.endsWith("china-festivals.ics"));
expect("调休标签样式已定义", html.includes(".tag.t-调休上班"));
expect("存在法定假期标签", upcoming && upcoming.innerHTML.includes("法定假期"));
expect("无 undefined 泄漏", upcoming && !upcoming.innerHTML.includes("undefined"));

for (const c of checks) {
  console.log(`${c.ok ? "  OK" : "FAIL"}  ${c.name}${c.ok || !c.extra ? "" : ` (${c.extra})`}`);
}
process.exit(failed ? 1 : 0);
