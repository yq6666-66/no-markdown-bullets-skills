# CHANGELOG

本文件只记录变更。用法见 `README.md`，约定见 `skills/no-markdown-bullets/SKILL.md`，安装见 `docs/install.md`。

主工具是 `scripts/strip_md_ul.py`。退出码 `0` / `2` / `1` 的含义以 `docs/规则与边界.md` 为准。

## Unreleased

### Changed

精简根 README（中文主 + 英文 `README.en.md`）：只保留简述、问题、功能、技术、用法；事实对齐 v3.2.0。GitHub About 建议文案见 PR 说明（合入后再改仓库 description）。

补 SKILL description 触发词与中文可发现性；README 用法补自定义指令、显式点名与强列表例外；新增 docs/扫读代价与下游边界.md。

## 3.2.0

1. 在 v3.1 基线上补了 front matter 遮罩：TOML `+++`、空行作废、200 行窗口。YAML 仍可用 `---` 或 `...` 闭合。
2. 引用变浅时，更深引用里没闭合的围栏随引用结束。引用深度变化时丢掉不属于当前层的列表帧，避免四格缩进被当成还开着的列表。
3. 增加抑制区。范围内原样保留，不改写。`reason` 必填。不嵌套。未闭合退出码 `2`。front matter 和抑制区共用同一种区域标记。
4. 增加 `--report`。JSON 只写到文件或 stderr，不进入 stdout。进程退出码仍是 `0` / `2` / `1`。
5. 把并行检查器分支上的五份黄金样例改写成 `fixtures/59` 到 `fixtures/63` 的 input / expected / meta。
6. 增加 `scripts/check_docx_numbering.py`。它只报告 docx 的 bullet 编号，退出码和剥除器不同。它和 `python-docx` 都是**卫星（可选，不进 Skill 验证主路径）**。
7. 增加 `evals/`。CI 只做提示集的离线校验，不调用模型。`evals/` 同样是**卫星（可选，不进 Skill 验证主路径）**。
8. 增加 `docs/install.md`，路径改为 `skills/no-markdown-bullets/` 和 `scripts/strip_md_ul.py`。
9. CI 用 Python 3.10 和 3.12 跑单元测试。
10. 行首超过 3 列的抑制指令不再开启抑制区。四格空格见 `fixtures/69_suppression_four_space`，一个 Tab 同样无效。
11. 核对模型正文的通过线加上「没有抑制区」。人工源文件仍可使用抑制区。脚本对抑制区的默认剥除不变。
12. docs: README 与 docs/install.md 用法定调——把 Skill 交给 AI 自适配；Discovery / 列 Skill 不作门槛。不承诺宿主强制执行。

## 3.1.0

`main` 上由 PR #1 交付的基线：`skills/no-markdown-bullets/SKILL.md`、`scripts/strip_md_ul.py`、`fixtures/` 和三份场景文档。该基线不再带旧的只读检查器。
