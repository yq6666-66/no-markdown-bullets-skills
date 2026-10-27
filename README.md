# 去黑点（no-markdown-bullets）

[English](README.en.md)

可复制的 Agent Skill：去掉面向读者正文里由 Markdown 无序列表渲染出的黑点；保留有序列表与表格。本仓独立交付，不修改、也不依赖其他插件仓库。版本以标签与 `CHANGELOG.md` 为准。本仓约定中文名为「去黑点」；技能列表是否显示中文取决于宿主，点名仍可用 id `no-markdown-bullets`。

## 问题

模型常在可见回复里写行首 `-` / `*` / `+` 加空白的无序列表（含空项），以及任务列表。GitHub 预览和不少聊天气泡会把它画成圆点。`•` / `·` 是普通字符，不是列表语法。只改一篇文案或网站 CSS，管不到下次生成、聊天和 Word。

## 功能

1. **禁止**：面向读者的无序列表与任务列表（任务列表不能靠「保留 bullet」例外留下来）。
2. **保留**：有序列表、表格、代码块、分隔线、行内强调等。
3. **例外**：用户当次明确要求保留 bullet 时，该次普通无序列表可以例外；任务列表不例外。
4. **形态**：`skills/no-markdown-bullets/`（含 `SKILL.md`）+ `scripts/strip_md_ul.py`。不做文风润色、不做浏览器/Word 插件、不发 npm 包。**不承诺**宿主强制执行：文件放入 ≠ 已加载 ≠ 模型必遵守。

对齐 tip `90b40d16` / v3.2.0 的实测样本包括：约 1.9 万字论文体正文、七组格式边界构造、人工 Word 项目符号样例、强列表体裁运维手册。**不承诺**任意宿主或模型 100%。

## 技术

1. Python 3.10+ 标准库即可跑脚本；CI 矩阵为 3.10 与 3.12。
2. 主路径是 Skill + `strip_md_ul.py`；`check_docx_numbering.py` / `evals/` / `python-docx` 为可选卫星。
3. 模型正文通过线：`--check` 退出码 `0`，报告 `stripped=0`，且 `summary.suppression_blocks == 0`。人工源文件仍可用抑制区。
4. 规则细节见 `docs/规则与边界.md`；安装路径见 `docs/install.md`。

## 用法

1. **推荐**：把 `skills/no-markdown-bullets/` 整目录交给对应 AI，说明按 `SKILL.md` 自适配。不以宿主 Skill 列表截图或 Discovery 为使用门槛。
2. **自定义指令（常驻）**：把下列「默认写法」原文抄进宿主自定义指令 / system 区（与 `SKILL.md` 一致，不可改义）：

   生成给人看的 Markdown，或将粘贴到 GitHub、聊天、Word 的正文时：

   1. 叙述、解释和结论写成普通段落。
   2. 步骤、顺序和需要逐条引用的内容写成编号列表。
   3. 字段对齐的对照写成表格。聊天客户端不支持表格时，改成编号列表，每条写成「字段：值」。
   4. 没有顺序、又不必编号的短项，拆成独立段落。

   不要先写出无序列表再替换符号。把连字符换成星号或加号，得到的仍是无序列表。

3. **显式点名**：对话里点名 `no-markdown-bullets` 时，应读本仓 `SKILL.md`，并在仓库根目录对模型可见正文执行：

   ```bash
   python scripts/strip_md_ul.py --check --report - body.md
   ```

   通过须同时满足：退出码 `0`，报告 `stripped=0`，且 `summary.suppression_blocks == 0`。

4. **强列表体裁例外**：产品文档、会议纪要等强列表体裁，用户当次明确要求保留 bullet 时，该次普通无序列表可以例外；任务列表仍禁止。
5. （可选）也可复制到宿主 Skills 目录；常见路径见 `docs/install.md`。列不出也不妨碍使用。
6. 脚本默认把改写结果写到标准输出，不修改源文件：

   ```bash
   python scripts/strip_md_ul.py input.md
   python scripts/strip_md_ul.py --dry-run input.md
   ```

7. Muse / WorkBuddy 的接入方式与实测摘要见下方「其他 AI 应用中的实例」；完整限制见 [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md)。
8. 禁 bullet 换来的扫读代价，以及管不到 Word / HTML 等下游，见 [`docs/扫读代价与下游边界.md`](docs/扫读代价与下游边界.md)。

### 其他 AI 应用中的实例

下列结果对齐 v3.2.0 已落盘评估；装目录不等于已加载，亦不承诺任意宿主或模型 100%。

**Muse。** 当次把 `skills/no-markdown-bullets/` 交给对话并明示约定即可试写；长期复用需转写成 Muse 本地说明（无 frontmatter 的 `SKILL.md`）加 `skill.yaml`，脚本仍在仓库根对正文跑 `--check`。论文体试写已走通提示词路径；做不到全局硬禁圆点。

**WorkBuddy。** 将 Skill 目录放入用户 skills 后可被列表发现；要贯穿全文须把「默认写法」抄进自定义指令，交付前再跑通过线。针对约 1.9 万字论文体、七组格式边界、人工 Word 项目符号样例与强列表运维手册这组已落盘样本，脚本可通过线（退出码 `0`，`stripped=0`，`suppression_blocks=0`）。

细节见 [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md)。

许可见 `LICENSE`（MIT）。
