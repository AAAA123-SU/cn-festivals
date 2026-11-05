# 中国传统节日 · 法定假期 iCalendar 订阅源

生成一个可直接被 iOS / iPadOS / macOS 系统日历订阅的 `.ics` 订阅源：传统节日名称与公历日期、法定放假天数、调休上班安排，一次订阅长期自动同步。

- **日期不靠手写**：农历节日由天文算法（Meeus 朔日 + 太阳视黄经）实时推算，遵循 GB/T 33661-2017《农历的编算和颁行》，2100 年前的日期都能算准；
- **假期按官方数据**：放假区间、法定天数、调休上班日来自国务院办公厅通知（见 `data/holidays.json`），未公布年度只列法定天数，**不臆造调休**；
- **零第三方依赖**：只用 Python 标准库（3.9+），GitHub Actions 里无需 `pip install` 即可重建；
- **每年自动更新**：工作流每月自动重建并发布，客户端按订阅地址定期拉取。

## 在线订阅地址（已部署，可直接用）

```
https://aaaa123-su.github.io/cn-festivals/china-festivals.ics
```

订阅页：<https://aaaa123-su.github.io/cn-festivals/>

iPhone：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴上面的链接 → 下一步。

## 快速开始

```bash
python build.py                 # 生成 去年 ~ 未来 10 年
python build.py --serve         # 生成并启动本地预览（.ics 使用 text/calendar MIME）
python -m unittest discover -s tests
```

产物：

| 路径 | 说明 |
| --- | --- |
| `docs/china-festivals.ics` | 订阅源本体（可直接导入/订阅） |
| `docs/index.html` | 订阅引导页（iOS 添加步骤、全年一览） |
| `data/holidays.json` | 法定假期与调休数据（唯一需要人工维护的文件） |

## 重新部署 / 迁移到自己的域名

iOS 订阅要求链接可公网访问，本地 `localhost` 只能用于 Apple 日历桌面端测试。当前实例已发布在 GitHub Pages，如需换仓库或换账号：

### 方案一：GitHub Pages（推荐，免费且自动更新）

1. 新建仓库并推送本目录；
2. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**；
3. 之后每次推送、以及每月 1 日的定时任务都会重建并发布。

订阅链接即为：

```
https://<用户名>.github.io/<仓库名>/china-festivals.ics
```

在 iPhone 的 Safari 中打开 `https://<用户名>.github.io/<仓库名>/` 点「添加到我的日历」，或直接粘贴上面的链接到日历订阅。

### 方案二：Cloudflare Pages / Netlify

把 `docs/` 作为发布目录即可，已附 `_headers` 保证 `.ics` 返回 `text/calendar; charset=utf-8`。

### 方案三：局域网临时测试

```bash
python build.py --serve --port 8000
```

同一 Wi-Fi 下用 iPhone 访问 `http://<电脑内网IP>:8000/china-festivals.ics`（启动时会打印地址）。

## 在苹果设备上添加

- **iPhone / iPad**：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴链接 → 下一步。
- **Mac**：日历 App → 文件 → 新建日历订阅 → 粘贴链接。
- 刷新频率：设置 → 日历 → 账户 → 已订阅的日历 → 刷新日程（可选 15 分钟至每周）。订阅源内含 `X-PUBLISHED-TTL:PT6H` 与 `REFRESH-INTERVAL` 提示。

> 提示：iOS 对「已订阅日历」中的提醒（VALARM）支持不一致，部分系统版本会忽略。若需要强提醒，建议把关键节日导出为本地日历。

## 订阅内容

| 类别 | 内容 |
| --- | --- |
| 传统节日 | 除夕、春节、元宵节、龙抬头、上巳节、端午节、七夕节、中元节、中秋节、重阳节、寒衣节、腊八节、小年（南/北） |
| 节气 | 清明节、冬至、寒食节（清明前一日） |
| 法定假期 | 全年各假期的放假区间与总天数，描述中含法定节假日天数、调休上班日、依据通知 |
| 调休上班 | 单独事件（含星期），默认提前一天 20:00 提醒 |

事件均为「全天事件」，UID 由日期生成，重复拉取不会产生重复日程。

## 数据准确性

- 农历：与 `cnlunar`、`lunardate` 逐日比对，**1929 年之后完全一致**（1914—1920 年差异源自 1929 年前旧历采用北京地方时 UTC+7:46，本项目统一按 UTC+8 计算）；
- 已用公开权威日期锁定 2024—2028 年春节、元宵、清明、端午、七夕、中秋、重阳、冬至，见 `tests/test_build.py`；
- 假期数据只录入**已正式公布**的年度：当前为 2024、2025 年。其余年度按《全国年节及纪念日放假办法》给出法定天数（元旦 1 天、春节 4 天、清明 1 天、劳动节 2 天、端午 1 天、中秋 1 天、国庆 3 天），并注明「调休安排待公布」。

## 录入新年度调休安排

每年 11—12 月国务院办公厅公布次年安排后，在 `data/holidays.json` 的 `years` 数组追加对象，然后 `python build.py`：

```json
{
  "year": 2026,
  "confirmed": true,
  "notice": "国务院办公厅关于 2026 年部分节假日安排的通知",
  "periods": [
    { "name": "元旦", "start": "2026-01-01", "end": "2026-01-03", "statutory_days": 1, "note": "1 月 1 日至 3 日放假，共 3 天" },
    { "name": "春节", "start": "2026-02-15", "end": "2026-02-22", "statutory_days": 4, "note": "2 月 15 日至 22 日放假调休，共 8 天" }
  ],
  "workdays": [
    { "date": "2026-02-14", "for": "春节" },
    { "date": "2026-02-28", "for": "春节" }
  ]
}
```

`start`/`end` 为**实际放假区间（含首尾）**，`statutory_days` 为其中的法定节假日天数，`workdays` 为调休上班日，`for` 用于和 `periods.name` 关联。

## 目录结构

```
build.py                 # 入口：生成 ics + 页面
lunar.py                 # 农历/节气天文算法（纯标准库）
festivals.py             # 节日与假期事件构建
ics_builder.py           # RFC 5545 序列化（CRLF、UTF-8 安全折行）
serve.py                 # 本地预览服务器（正确 MIME）
data/holidays.json       # 法定假期与调休（人工维护）
docs/                    # 发布目录（生成的 ics 与页面）
tests/test_build.py      # 回归测试
tools/crosscheck.py      # 与第三方农历库的对拍脚本（需 pip install cnlunar lunardate）
```

## 许可证与免责

代码可自由使用。假期安排以中国政府网及各地官方发布为准；本项目仅作日历同步之用，若遇政策调整请以官方通知为准。
