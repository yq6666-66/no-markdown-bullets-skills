# 安装指南

本文档说明怎么把 Skill 交给宿主或 AI，以及怎么用仓库里的脚本做自测。它不改变 Skill 的约定。约定见 `skills/no-markdown-bullets/SKILL.md`，块规则见 `docs/规则与边界.md`，三个场景的操作见 `docs/三场景实操.md`。

**推荐用法**：把本仓库的 Skill（`skills/no-markdown-bullets/` 整目录，含 `SKILL.md`）丢给对应 AI / 助手，由对方按 `SKILL.md` 自行适配。下表是各宿主常见放置路径，仅供参考。不以「宿主 Skill 列表截图 / 列出可见 Skill」为使用门槛；Discovery 不作门槛。文件放进目录，不等于宿主已经加载，也不等于模型会遵守；本仓库不承诺宿主强制执行。

说明：本文与 README 描述用法与安装；`skills/no-markdown-bullets/SKILL.md` 正文未改。

## 快速开始

1. 在下面的位置表里选一个位置。项目级和全局级不要各放一份。也可以不依赖宿主目录，直接把 Skill 目录交给目标 AI。
2. 把仓库里的 `skills/no-markdown-bullets/` 整个目录复制到该位置（目录里要有 `SKILL.md`）；或把该目录交给目标 AI，由它按 `SKILL.md` 自行适配。
3. 若走了宿主目录安装：重新打开目标工具，或新开一段会话（有助于工具侧加载，但不是硬门槛）。
4. 在本仓库根目录执行 `python scripts/strip_md_ul.py --check fixtures/02_ordered/input.md`（可加 `--report -`，JSON 写到 stderr）。退出码应当是 `0`，stderr 或报告里应当有 `stripped=0`（或 `summary.stripped == 0`）。本步只测脚本样例；模型正文通过线按第 5 步与「首次使用自测」。
5. 用 `docs/三场景实操.md` 文末的固定提示词做一次真实输出（或交给 AI 后按约定生成），再对存下来的模型正文跑 `--check`。通过线是退出码 `0`、`stripped=0`，且没有抑制区（`--report` 的 `summary.suppression_blocks` 为 `0`，或正文无 `no-markdown-bullets:`）。人工源文件仍可使用抑制区。

「请宿主列出 Skill 名单」不是必过关步骤；列不出也不妨碍使用。

## Skill 目录和脚本不是同一个目录

复制到宿主的只有 Skill 目录：

```text
skills/no-markdown-bullets/
  SKILL.md
```

两个脚本都留在本仓库，不放进 Skill 目录。其中 `scripts/check_docx_numbering.py` 是**卫星（可选，不进 Skill 验证主路径）**，不跟着 Skill 复制。

```text
scripts/strip_md_ul.py
scripts/check_docx_numbering.py
```

只复制 `SKILL.md` 也可以被读取，但请复制整个 `skills/no-markdown-bullets/` 目录，避免以后这个目录里增加文件时漏掉。Skill 的复制路径不变。脚本不要拆进宿主的 Skills 目录后再改相对路径。自测命令都在本仓库根目录执行。

## 分工具安装位置

项目级只影响当前项目。全局级通常作用于该工具打开的项目。同一工具里不要同时放两份。

| 工具 | 项目级 | 全局级 | 说明 |
| --- | --- | --- | --- |
| Cursor | `.cursor/skills/no-markdown-bullets` | `~/.cursor/skills/no-markdown-bullets` | 常见放置（路径示例） |
| Codex | `.codex/skills/no-markdown-bullets` | `~/.codex/skills/no-markdown-bullets` | 常见放置（路径示例） |
| OpenCode | `.opencode/skills/no-markdown-bullets` | `~/.config/opencode/skills/no-markdown-bullets` | 常见放置（路径示例） |
| Claude Code | `.claude/skills/no-markdown-bullets` | `~/.claude/skills/no-markdown-bullets` | 常见放置（路径示例） |
| 跨工具共享 | `.agents/skills/no-markdown-bullets` | `~/.agents/skills/no-markdown-bullets` | 常见放置（路径示例） |

### 操作系统路径

1. 表里的 `~` 在 macOS 和 Linux 上是用户主目录，在 Windows 上对应 `%USERPROFILE%`。
2. Windows 全局级举例：Cursor 对应 `%USERPROFILE%\.cursor\skills\no-markdown-bullets`。
3. Windows 项目级仍是项目目录下的相对位置，例如 `<项目>\.cursor\skills\no-markdown-bullets`。
4. 路径里有空格时，把完整路径用引号包起来。

### 怎么选位置

| 使用情形 | 选择 |
| --- | --- |
| 只在一个项目里试 | 该工具的项目级 |
| 多个项目只用一个工具 | 该工具的全局级 |
| 几个工具想共用一份 Skill | 跨工具共享位置 `.agents/skills` |
| 试完就要拆掉 | 单独的试验项目，用项目级 |
| 不依赖宿主目录 | 把 `skills/no-markdown-bullets/` 整目录交给目标 AI |

OpenCode 除了自己的目录，也会读取 `.claude/skills` 和 `.agents/skills`。Codex 是否读取 `.agents/skills` 以你安装的版本为准；路径仅供参考，不要只对照旧笔记。

## 安装步骤

1. 选定上表的一个位置；或跳过宿主目录，直接把 Skill 交给 AI。
2. 把 `skills/no-markdown-bullets/` 整个目录复制过去，确认里面有 `SKILL.md`（若走宿主目录）。
3. 重新打开工具或新开会话。已经打开的会话不一定会重新加载 Skill；新开会话有帮助，但不是硬门槛。
4. （可选）可尝试请宿主列出当前能发现的 Skill。列不出也不妨碍把 Skill 交给 AI 使用；不要把「列不出」写成安装失败。
5. 按下一节做脚本自测。

## 更新

1. 记下当前安装位置（若有），以及本仓库的提交号。版本以本文件和 `CHANGELOG.md` 为准。
2. 若走宿主目录：用新的 `skills/no-markdown-bullets/` 覆盖同一个位置，不要在旁边再放一份。若采用交给 AI 的方式：把更新后的整目录重新交给对方即可。
3. 重新打开工具或新开会话（宿主目录安装时更有帮助）。
4. 再跑一次快速开始里的 `--check`。
5. 若行为没变，先查是不是项目级和全局级各有一份，再查旧会话有没有关掉。

## 卸载与回滚

1. 若走宿主目录：卸载就是删掉安装位置下的 `no-markdown-bullets` 目录，不用改工具的其他配置。若采用交给 AI 的方式：停止使用旧目录即可。
2. 目录里如果有自己改过的备注，先备份再删。
3. 回滚是把上一版的完整目录覆盖回去（或重新交给 AI），然后按更新一节再验证一次。
4. 卸掉或回滚之后同样建议新开会话。

## 剥除器

依赖是 Python 3.10 及以上的标准库。不需要 `pip install`。命令在本仓库根目录执行。脚本不扫描目录，一次只处理一个文件或一段 stdin。它不修改源文件，改写结果在 stdout，诊断在 stderr。

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --check input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py --report report.json input.md
python scripts/strip_md_ul.py --report - --check input.md
python scripts/strip_md_ul.py < input.md
```

| 退出码 | 含义 |
| --- | --- |
| 0 | 结果里没有残留 UL。源文件里原来有 UL 时，只要剥干净，仍然是 0 |
| 2 | 有跳过。例如未闭合围栏、未闭合抑制区、未闭合的 HTML 原始块。结果里仍可能没有残留 UL。**不是**脚本崩溃 |
| 1 | 失败。剥后仍有 UL、剥后新产生跳过区、文件打不开或参数错误。这时的 stdout 不能当终稿 |

确认源文件本来就干净，要同时看到退出码 `0`，以及 stderr（人类诊断）或 `--report` 目标（`-` 时为 stderr 上的 JSON，路径时为该文件）里的 `stripped=0` / `summary.stripped`。只看退出码不够。

`--report PATH` 把 JSON 写到文件，stdout 仍是正文。`--report -` 把 JSON 写到 stderr，不再混入人类可读诊断。JSON 不会写到 stdout。

抑制区用来让一段原文保持不改写。`reason` 必填。写法、嵌套规则和未闭合时的退出码 `2` 见 `docs/规则与边界.md`。这是给人编辑源文件用的，不是让模型用注释把圆点藏起来。

## 卫星（可选，不进 Skill 验证主路径）

`scripts/check_docx_numbering.py`、`evals/` 和 `python-docx` 是**卫星（可选，不进 Skill 验证主路径）**。可进仓库、可手动用。主路径仍是 Skill 加 `scripts/strip_md_ul.py`。Skill 复制路径不变，仍是 `skills/no-markdown-bullets/`。核对模型正文的通过线见「首次使用自测」。人工源文件仍可使用抑制区。

## Word 文件

这一节是**卫星（可选，不进 Skill 验证主路径）**。`scripts/check_docx_numbering.py` 只报告 `.docx` 里解析成 bullet 的段落，不改写文件，也不处理 Markdown。它的退出码和剥除器不同，不要混用。

| 退出码 | 含义 |
| --- | --- |
| 0 | 没有 bullet 编号 |
| 1 | 发现了 bullet 编号 |
| 2 | 路径不存在或文件读不了 |

```bash
python scripts/check_docx_numbering.py report.docx
python scripts/check_docx_numbering.py --format json report.docx
```

运行它只用标准库。`python-docx` 同样是**卫星（可选，不进 Skill 验证主路径）**，不是运行依赖，只在可选测试里用来生成一份真实文档。没装它时，那一组测试会跳过，其余测试仍然要过。

## 度量

这一节是**卫星（可选，不进 Skill 验证主路径）**。`evals/` 用来对照模型有没有少写无序列表。默认 CI 只检查提示集结构，执行 `python evals/run_eval.py --dry-run`，不调用模型。手动跑法和指标见 `evals/README.md`。

## 首次使用自测

1. 让工具写一段连续叙述，看它是不是用了段落。
2. 让工具写一个三步操作，看步骤是不是编号列表。
3. 让工具做一组同构对照，看它是不是用了表格。聊天不支持表格时，应改成编号列表。
4. 把模型可见正文存成 Markdown，跑 `python scripts/strip_md_ul.py --check --report - 输出.md`。通过线是退出码 `0`，报告里 `stripped=0`（或 `summary.stripped == 0`），并且 `summary.suppression_blocks` 为 `0`（或正文无 `no-markdown-bullets:` 抑制注释）。人工写的源文件仍可使用抑制区，脚本不会因此改变默认剥除。
5. 任何一步不对，先查安装位置和会话有没有重开，再重做。不要把退出码 `0` 但 `stripped` 大于 0 当成源文件已经干净。模型正文里若用抑制注释藏列表，`stripped=0` 也不算通过。列不出宿主 Skill 名单时，仍可用 `--check` 验正文，不要因此标成「未安装」。

## 故障排查

| 现象 | 先查什么 | 处理 |
| --- | --- | --- |
| 输出里还有无序列表 | 是否已把 Skill 交给 AI；位置对不对；会话有没有重开 | 再交给 AI 或纠正位置，新开会话，再做自测 |
| 退出码 1 | stderr 是打不开文件，还是剥后仍有 UL | 前者改路径或编码；后者不要把 stdout 当终稿 |
| 退出码 2 | 是不是未闭合围栏、抑制区或 HTML 原始块 | 先补上闭合，再决定要不要采用 stdout |
| 退出码 0，但源文件里还有列表标记 | 有没有同时看 `stripped=0` | 没有 `stripped=0` 就说明源文件被剥过，并不本来干净 |
| 更新后行为没变 | 是不是放了两份 Skill | 只留选定的那一份，再新开会话 |
| Word 里仍有圆点 | 粘贴方式，或 docx 里的编号属性 | 按 `docs/三场景实操.md` 只保留文本；已有 docx 时再跑 docx 检查器 |
| 宿主列不出 Skill | Discovery 不作门槛 | 仍可把目录交给 AI；用 `--check` 验正文 |

## 常见问题

1. 问：只装到一个工具里，别的工具会不会自动生效。答：不会。每个工具读自己的位置。想共用时用 `.agents/skills`，或分别把 Skill 交给各工具侧的 AI。
2. 问：装完不用新开会话行不行。答：新开会话更有利于工具侧加载，但不是硬门槛；也可直接把 Skill 目录交给 AI。
3. 问：`--check` 返回 0 是不是安装失败。答：不是。0 表示结果里没有残留 UL。源文件是不是本来就干净，还要看 `stripped=0`。
4. 问：旧文档里的无序列表会自动消失吗。答：不会。脚本只把改写结果写到 stdout，不改源文件。退出码是 1 时不要把 stdout 写回去。
5. 问：能不能让脚本默认保留 bullet。答：不能。用户当次明确要求保留普通 UL 时，不要把那一次输出送进脚本。任务列表没有这个例外。
6. 问：CI 会不会调用模型做 eval。答：不会。CI 只跑单元测试和 `evals/run_eval.py --dry-run`。
7. 问：宿主列不出 `no-markdown-bullets` 还能不能用。答：能。Discovery / 列表截图不作门槛；把 Skill 丢给对应 AI，并用 `--check` 验正文。

## 检查清单

1. 装前：位置已选定，同一工具里没有第二份同名目录；或已决定直接把目录交给 AI。
2. 装中：目录里有 `SKILL.md`（若走宿主目录）。
3. 装后：建议新开会话；列出 Skill 名单为可选，列不出仍可用。
4. 脚本：`fixtures/02_ordered/input.md` 的 `--check` 是退出码 `0`，且 stderr 或 `--report` 含 `stripped=0`。
5. 首次输出：段落、编号、表格都看过。存下来的模型正文要退出码 `0`、`stripped=0`，且没有抑制区。第 4 条只是脚本自测。

## 命令速查

| 用途 | 命令 |
| --- | --- |
| 确认有序列表样例本来就干净 | `python scripts/strip_md_ul.py --check fixtures/02_ordered/input.md` |
| 剥一个文件到新文件 | `python scripts/strip_md_ul.py input.md > input.stripped.md` |
| 只判定、不打印正文 | `python scripts/strip_md_ul.py --check input.md` |
| JSON 报告写到文件 | `python scripts/strip_md_ul.py --report report.json input.md` |
| JSON 报告写到 stderr | `python scripts/strip_md_ul.py --report - --check input.md` |
| 核对模型正文 | `python scripts/strip_md_ul.py --check --report - 输出.md` |
| 检查 docx 的 bullet 编号 | `python scripts/check_docx_numbering.py report.docx` |
| 离线查看 eval 提示集 | `python evals/run_eval.py --dry-run` |
| 跑全部单元测试 | `python -m unittest discover -s tests -v` |
