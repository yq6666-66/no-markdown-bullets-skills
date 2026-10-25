# Changelog

本项目从 0.2.0 起按语义化版本记录。判定规则的收紧、跳过范围的变化、退出码语义的调整都会影响下游集成，需要单独标注。

## 0.2.0

新增判定跳过、例外治理与机器可读输出。所有既有行为保持兼容，`--allow` 的入参约束除外。

### 新增

1. `scan_document()` 返回 `ScanResult`，含 `findings`、`suppressed_lines`、`suppression_blocks`；`scan_text()` 保留并只返回 `findings`，旧调用不受影响。
2. 闭合的 YAML `---` 或 TOML `+++` frontmatter 整段跳过，修正 `tags:` 下缩进条目被误报的问题。
3. 作用域抑制指令 `<!-- no-markdown-bullets: off reason="..." -->` 与 `on`，强制理由、未闭合即报错、代码块内无效。
4. `--format {text,json}`，JSON 含 `tool`、`version`、`files`、`summary`，`summary` 给出 `suppressed_lines` 与 `suppression_ratio`。
5. `--version` 输出脚本版本。
6. `Finding` 新增 `code` 字段，取值 `unordered-list` 与 `unclosed-suppression`，供下游按类型分流。

### 变更

1. `--allow` 只接受单个路径。传入多个路径时以退出码 `2` 报错，原因是多文件放行等于关闭检查。既有“单文件加 `--allow`”的用法不受影响。
2. `text` 输出格式逐字节不变，仅 `code` 字段不参与文本渲染。

### 未变更

退出码语义仍为 `0` 通过、`1` 命中、`2` 输入或读取错误。检测范围仍只覆盖 Markdown 文本层的 `-`、`*`、`+`，不检测 raw HTML `<ul>`、粘贴字形与 `.mdx`。校验器仍只读、零运行时第三方依赖。

### 迁移

若调用方解析 `text` 输出，无需改动。若调用方依赖 `--allow` 一次放行多个文件，改为在文件内使用作用域抑制，或逐个文件调用。

## 0.1.0

首个版本：`SKILL.md` 约定、三场景规则文档、只读校验脚本、正负示例、单元测试与 CI 校验。
