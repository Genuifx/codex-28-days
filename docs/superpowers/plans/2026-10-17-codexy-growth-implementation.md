# Codexy 首批增长改造 Implementation Plan

按以下四项任务逐项完成；每项先补测试，再实现、验证和提交。执行前需确认本计划与末尾的复核方式。

**Goal:** 在保留当前样式和内容的前提下，补齐中英详情入口、来源标题、静态分享预览和 RSS 回访路径。

**Architecture:** 沿用 scripts/scrape.py 的静态生成职责，先统一 URL 和标题，再让首页、详情、分享、RSS 复用这些数据。新增纯离线构建入口，所有产物验证通过后随同一个 Git 提交发布，不改抓取和分类规则。

**Tech Stack:** Python 3.12 标准库、现有 HTML/CSS/JavaScript、unittest、GitHub Actions、GitHub Pages；云端现有 Chromium/Playwright 只用于视觉与交互验证。

**Spec:** [已确认的设计及视觉约束](../specs/2026-10-17-codexy-growth-design.md)。用户于 2026-10-17 05:57 UTC 确认推进；原设计文件记录的是此前交付时的待审状态。此实施计划待审核及执行方式选择，产品实现尚未开始。

## Global Constraints

- **视觉与交互硬约束：沿用当前站点，只加增量部分。** 复用现有配色、字体、卡片样式、布局、间距和交互，不做整体改版，不重设首页主视觉。
- 只为新增标题、内容和入口作最小必要扩展，不借本批重排既有模块或统一替换样式。
- 代码基线为 281abe68845cc319808c03c5c345455795fd8a67，保留海报“同日不同条目不能串链”的修复。
- 固定验收快照：18 条 entries、4 条 resets、20 个去重顶层 ID、4 条嵌套 follow-ups；未来数量由数据驱动。原文、译文、引用、来源和归属不变。
- 离线构建不得改写 data/days.json。固定快照 SHA-256：c86895d553ff78b818c95883ebb6a0a4171c0e9935d78d232f1b83b2c7cc7c54。
- 英文首页 /，中文首页 /zh/；详情 /updates/{X-post-id}/ 和 /zh/updates/{X-post-id}/；全部旧 #day-* 及补充锚点保留。
- 中文缺译显示英文并标注“暂无中文译文”，英文回退段落标记 lang="en"；不切换 noindex 或临时重定向。
- 不引入新外部服务、账号体系、付费订阅、邮箱收集、统计服务或自动对外发帖；不依赖 UTM 或自定义事件，不承诺流量。

## Review Focus

- 同日多帖、qualifier 修正或缺失 ID：URL 不串条目、不随标题变动、不产生路径穿越（任务 1、2）。
- 缺译、标题脚本覆盖、旧语言偏好：显式 URL 的语言与页级标题一致，无 JS 也可阅读和切换（任务 2）。
- 原文含引号、&、< 或 </script>：HTML、属性、JSON、RSS 分别正确转义且内容不丢失（任务 2、3）。
- 嵌套路径和回退导航：原数据、订阅、前后条目、返回首页锚点及全部分享方式指向正确页面（任务 2、4）。
- 重复构建、来源离线、渲染失败或远端并发更新：不改历史数据、不制造重复 RSS 项、不发布半套产物、不覆盖远端新内容（任务 3、4）。

---

## 文件职责

- 修改 scripts/scrape.py：URL、标题、页面、RSS、sitemap、llms.txt 与统一输出；不重写抓取逻辑。
- 新增 data/titles.json：按帖子 ID 保存 {"en": "短主题", "zh": "短主题", "source_ids": ["依据帖子ID"]}。
- 新增 scripts/build.py：python3 -B -m scripts.build --output DIR，只读现有数据重建；省略 --output 时输出到仓库。
- 新增 assets/og/cover.svg 与 cover.png：沿用现有视觉的分享图源稿和 1200×630 PNG；每日任务无需制图依赖。
- 新增 tests/fixtures/growth_log.json：原始快照的逐字节副本；新增 tests/test_publish.py，修改 tests/test_scrape.py 中相关分享断言。
- 修改 .github/workflows/daily.yml、README.md；生成 index.html、zh/index.html、updates/*/index.html、zh/updates/*/index.html、feed.xml、zh/feed.xml、sitemap.xml、llms.txt。

## 任务 1：固定数据边界、稳定 URL 与来源标题

**Files:** scripts/scrape.py；data/titles.json；tests/fixtures/growth_log.json；tests/test_publish.py。

**Interfaces:** 新增 entry_path(e: dict, lang: str = "en") -> str、entry_url(e: dict, lang: str = "en") -> str、load_titles(path: str | None = None) -> dict、entry_title(e: dict, lang: str = "en", titles: dict | None = None) -> str。保留 day_url(uid) 的旧锚点含义；day_uid 继续供 DOM 和海报键使用。

- [ ] 保存基线 data/days.json 为固定测试 fixture，并验证上述 SHA-256。用 git archive 导出基线至 /tmp/codexy-growth-baseline，保留后续截图对照所需的原始页面。
- [ ] 在 PublishContractTests 写失败测试；最小接口断言如下，另断言每个 fixture ID 的两语路径唯一、修改 day/qual/title 不改变路径、无 ID 或非数字 ID 抛 ValueError。

```python
def test_routes_are_id_based(self):
    e = {"id": "2111244596131111253", "day": 12}
    self.assertEqual(scrape.entry_path(e), "/updates/2111244596131111253/")
    self.assertEqual(scrape.entry_path(e, "zh"), "/zh/updates/2111244596131111253/")
    self.assertEqual(scrape.entry_url(e), "https://codexy.fyi" + scrape.entry_path(e))
```

- [ ] 运行 python3 -B -m unittest tests.test_publish.PublishContractTests -v，确认因新接口不存在而失败。
- [ ] 实现上述接口：仅接受 en/zh；标题映射缺失时使用去掉 Day 标记的来源摘录，英文上限 80 字符、中文上限 60 字符；省略号计入上限。entry_title 返回带 Day/开幕前缀的完整标题，所有消费方不再另加同一前缀。缺译使用英文标题回退。
- [ ] 逐条核对当前 18 条中英短标题与 source_ids。固定 Day 2.2“OpenAI API 使用档位调整”、Day 7“GPT-6.1 Sol 默认上下文增至 500k”；Day 6/8/10 明示 Reset，Day 10 开场玩笑不作为主题。标题源只可引用该条目及其已保存引用、补充中的帖子。测试 fixture 的 18 个 ID 都有标题、来源 ID 有据可查、新条目无标题仍可生成；不要求生产映射永久只有 18 条。
- [ ] 重跑该测试类及 python3 -B -m unittest discover -v，全部通过；提交 feat: add stable update routes and source titles。

## 任务 2：增量详情页、双语静态输出与分享一致性

**Files:** scripts/scrape.py；tests/test_publish.py；tests/test_scrape.py。

**Interfaces:** 使用任务 1 接口。新增 render_entry(e: dict, latest_day: int, lang: str = "en", titles: dict | None = None) -> str、render_detail(log: dict, e: dict, lang: str = "en", titles: dict | None = None) -> str、entry_json_ld(e: dict, lang: str = "en", titles: dict | None = None) -> str。render(log, changed, lang="en", titles=None) 保持原有前两个参数可用；T、render_followups、poster_data 增加默认 en 的 lang 参数；json_ld(entries, lang="en", titles=None) 继续生成首页图谱。share_tags(texts, urls, titles, poster, poster_key="poster", lang="en") 的 urls 是两语 URL 映射。render_llms 的接口在任务 3 定义。

- [ ] 在 PublishPageTests 写失败测试：从 fixture 逐条生成中英详情，断言自指 canonical、en/zh/x-default、对应 H1、原文/译文/引用/补充均存在，且各旧锚点仍存在于首页。断言原始数据链接为 /data/days.json。
- [ ] 增加安全与回退用例：正文含 </script><img src=x>、& 和引号时无注入元素，JSON 可解析且保留原字符串；中文缺译出现“暂无中文译文”及 lang="en"；不会出现 noindex 或自动跳转脚本。运行 python3 -B -m unittest tests.test_publish.PublishPageTests -v，确认预期失败。
- [ ] 提取现有卡片正文，复用原 CSS 类、字体、色值和结构，不重排首页模块。首页只增主题链接和后续 RSS 入口；详情页复用现有页头/卡片/页脚，增 H1、前后条目和返回时间线。返回链接保留当前语种和该条目锚点；前后条目用现有 day_sort_key 排序。首页语言切换保留当前锚点，无 JS 时可用。
- [ ] 将语言切换按钮替换为同外观、位置的真实链接；LANG_JS 从服务器输出的 data-lang 取值，不读取 navigator/localStorage 决定语言，不把详情 title 改回首页。两语元数据在 HTML 中直接正确；详情结构化数据只描述当前条目，首页保留真实可见的列表和 FAQ。
- [ ] 将 share_tags 的 URL 输入改为 {"en": absolute_url, "zh": absolute_url}，增加 lang="en"；当前页面直接输出正确分享/复制 URL。poster_data(entries, latest_day, lang="en") 保留 key=day_uid(e)，URL 改为 entry_url(e, lang)，站点海报指向当前语种首页。无需用语言脚本后补正确 URL。
- [ ] 更新既有两项海报测试：继续验证每个 key 对应正确旧 DOM 锚点，新增断言海报 URL、复制 URL 与 entry_url(e, lang) 一致；移除“海报 URL 必须含 #”这个已被确认变更替代的假设。保留同日多条、不重复 key 的覆盖。检查全部旧来源内容仍在。
- [ ] 重跑新旧测试全部通过；提交 feat: add bilingual update pages without redesign。

## 任务 3：静态 OG 图、RSS 与抓取发现文件

**Files:** assets/og/cover.svg、assets/og/cover.png；scripts/scrape.py；tests/test_publish.py。

**Interfaces:** 使用 entry_url/entry_title。新增 render_feed(log: dict, lang: str = "en", titles: dict | None = None) -> str；扩展 render_sitemap(log) 和 render_llms(log, titles=None)。所有返回值为 UTF-8 文本。

- [ ] 在 PublishDiscoveryTests 写失败测试：两份 RSS 各有 fixture 的 18 个 item，按可解析 posted_at 倒序；GUID 精确为 urn:codexy:x:{id}:{lang}，isPermaLink="false"；增加跟帖后父项的 description 更新且 GUID 不变，不新增 item。link 指向对应详情；pubDate 用来源日期，无法解析时省略，不用当前时间；缺日期项稳定排在末尾。
- [ ] 增加 XML 转义、中文回退、相同数据输出完全相等测试；sitemap fixture 有 38 个唯一页面 URL、没有 #；llms.txt 的完整双语原文、引用与补充保留，含新详情链接。运行 python3 -B -m unittest tests.test_publish.PublishDiscoveryTests -v，确认预期失败。
- [ ] 实现 RSS 2.0：description 为当前语言主帖正文的前 160 字符；有作者补充时附最新一条的前 80 字符，明确标为作者补充，并附对应原帖链接；截断时使用省略号且计入上限。正文使用 XML 转义，不把原文当 HTML 执行。频道设置语言与自身 feed 链接，省略无可靠依据的 lastBuildDate/lastmod。加入与现有样式一致的 RSS 可见入口和 head 自动发现标签。
- [ ] 一次性制作通用 OG 图：复用现有背景/红色、字体和叶片图形，只有站点名与固定介绍，不写动态 Day 数。保留 SVG 源稿，用云端现有 Chromium 导出 1200×630 PNG，检查实际像素，无裁切、错字或字体意外回退；不把浏览器、Pillow 或外部制图依赖加入每日任务。
- [ ] 全部首页/详情输出绝对 og:image/twitter:image、宽高、图片说明及 summary_large_image；测试读取 PNG 文件头确认 1200×630 并验证所有页引用同一 /assets/og/cover.png。新增 PublishDiscoveryTests.test_og_dimensions_and_metadata，缺文件时必须失败。
- [ ] 重跑新旧测试全部通过；提交 feat: add rss feeds and static social preview。

## 任务 4：离线生成、自动发布接线及最终验收

**Files:** scripts/build.py；scripts/scrape.py；.github/workflows/daily.yml；README.md；tests/test_publish.py；tests/test_scrape.py；生成产物。

**Interfaces:** 新增 build_outputs(log: dict, titles: dict) -> dict[str, bytes] 和 write_site(log: dict, changed: bool, output_root: str | None = None) -> None。前者只生成 HTML/RSS/sitemap/llms 文本产物，不读网络、不写文件；后者先完成全部渲染，再暂存验证并写入目标目录，复制 PNG；仅当输出到其他目录时复制原始 JSON 原字节以供离线预览，输出到源仓库时不得重新写入 data/days.json。source 根目录仍为 ROOT，默认 output_root=ROOT。main() 保存已抓取数据后调用 write_site；新 CLI 只 load_log/load_titles 后调用 write_site，不调用 main/save_log/翻译。

- [ ] 在 PublishBuildTests 写失败测试：临时目录构建生成 38 个 HTML、2 个 feed、sitemap、llms、PNG 和 raw JSON；生产数据 SHA-256 不变，固定顶层 ID/补充归属不变。全文件哈希在间隔不同模拟时钟的两次构建后相同；fetch、translate_entry、save_log 被设为一调用即失败时，离线 CLI 仍成功。
- [ ] 写 test_render_failure_keeps_existing_outputs：先记录旧产物哈希，令其中一页渲染抛异常，断言 write_site 抛错且旧产物未改。运行 python3 -B -m unittest tests.test_publish.PublishBuildTests -v，确认预期失败。
- [ ] 实现上述接口与 python3 -B -m scripts.build --output DIR。首页更新时间取 entries/resets/follow-ups 中有效来源时间的最大值；无有效日期显示“更新时间未知”，不取当前时钟。输出先全部渲染再落盘；任何构建/校验异常以非零退出，后续 Git 发布步骤不得执行。可选目标目录不可清空或删除无关文件。
- [ ] 修改原抓取集成测试，让临时 source 根目录具备本批新增的标题/PNG 测试输入；既有来源离线、再次抓取、跟帖去重用例扩展检查新产物。发现来源异常仍保存已知数据并成功重建；渲染失败则停止发布。
- [ ] daily.yml 两处 git add 都覆盖新增目录和 feed；冲突回退后在最新远端数据上重新抓取/生成并重跑完整测试，失败不得提交/推送。README 加离线预览、URL、RSS 和生成文件说明。重新生成并提交产物前验证 data/days.json 与预期基线一致；如远端已有新内容，先重新对齐数据，保留原 20 个 ID 并调整实际页数，不复制旧 JSON 覆盖。
- [ ] 完整验证命令：python3 -B -m unittest discover -v；python3 -B -m scripts.build --output /tmp/codexy-growth-preview；git diff --check。必须全通过，不能以局部测试代替。
- [ ] 用 dot 自己云端的浏览器验证基线与新预览：分别以 python3 -m http.server 在两个临时目录启动服务。固定 1440×1000 和 390×844 视口，对中英首页做截图对照（基线中文用原语言切换按钮进入）；差异只能来自主题标题/RSS 入口及必要占位。检查原主视觉、卡片、字体、配色、模块顺序与操作保持一致；新增详情与 OG 延续同风格。
- [ ] 同一浏览器检查：禁用 JS 访问中英页并切换；预存相反语言偏好后访问详情，语言/title 不变；首页锚点切换语言、前后条目、返回/前进；两次开关海报、复制、X URL 参数、原生分享 payload 均对应当前条目。特别覆盖 Day 3 encore 与 Day 5 dots edition。测试 native share 可用受控 mock 检查 payload，不实际对外发送。
- [ ] 独立审查最终 diff、所有新增静态页/链接、源数据保护与截图；修复后重跑受影响检查及完整测试。仅通过后提交 feat: publish static growth surfaces。记录提交 SHA 与检查结果。
- [ ] 发布步骤须在已确认的执行/发布权限内进行：推送后确认远端准确 SHA、该 SHA 的 Pages 任务成功；实际 HTTPS 检查 /、/zh/、两语详情、两条特殊同日条目、PNG、两份 RSS、sitemap 的状态、正文、元数据和目标链接。未经检查不能宣称上线；阻塞则报告精确阶段。此任务止于站点发布验收，不扩展到对外营销或流量保证。

## 审核与执行方式

本计划建议 **整批完成后独立复核**：在 dot 自己云端顺序完成四个紧密关联的生成器步骤，再独立检查整批变更；无需用户电脑。另一方式为 **每步分别独立复核**：每项完成后先单独审查，再进入下一项，最后审查整批结果；检查更密集，耗时更长。

请先审核本计划并选择执行方式。确认前不写产品代码、不推送；确认后按所选方式执行。该选择不改变已确认的环境和视觉约束。
