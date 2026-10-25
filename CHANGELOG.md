# Changelog

本项目从 0.2.0 起按语义化版本记录。判定规则的收紧、跳过范围的变化、退出码语义的调整都会影响下游集成，需要单独标注。

## 0.3.0

补齐 Word 侧验证与有效性度量。两项都是新增工具，不改变 Markdown 检查器的任何行为。

### 新增

1. `scripts/check_docx_numbering.py`，纯标准库解析 `.docx`，报告落到 `bullet` 编号的段落。编号来源解析三条路径：段落直接的 `w:numPr`、段落样式的 `w:numPr`、以及样式的 `w:basedOn` 继承链。`numId` 为 `0` 视为无编号跳过；`decimal` 等有序格式不报。退出码与 Markdown 检查器一致，支持 `--format json`。
2. `evals/`，八条固定提示的抽样度量。每条提示声明期望结构（`prose`、`ordered`、`table`、`table_or_ordered`、`ordered_or_prose`），支持两种输入：录制答案目录，或任何从 stdin 读提示的命令。`--compare` 输出逐条对比与总体 `bullet_rate` delta。
3. `evals/README.md`，写明度量能证明什么、不能证明什么。单次运行是基线不是结果；没有对照组就没有归因。
4. `_BlockScanner` 之外新增 `tests/test_check_docx_numbering.py` 与 `tests/test_run_eval.py`，共 47 项。

### 变更

1. 仓库文档一致性测试扩展到 `evals/README.md`，并新增断言：技能包对外宣称的两个脚本必须存在，防止包不再自洽。
2. `pyproject.toml` 的 mypy 检查范围加入两个新脚本，仍为 `strict`。

### 说明

`python-docx` 仅为可选测试依赖。装有时额外三项用真实库生成的文档验证解析器，未安装时自动跳过；运行时始终零第三方依赖。

度量默认不修改仓库：`evals/results/` 与 `evals/samples/` 已在 `.gitignore` 中。

## 0.2.1

判定修复、性能优化与工程化门槛。接口与 0.2.0 兼容。

### 修复

1. 列表被引用块打断后，缩进记录没有失效，导致紧随其后的缩进代码块被误报为嵌套列表项。现在按容器归属清理状态：顶层行结束所有引用块，引用行结束引用块之外的列表。
2. 同一状态问题还导致缩进 4 的行被当作列表续行，进而允许四格缩进的围栏开启代码块，把后面真实的列表吞掉。修复后不再发生。

这两个缺陷在 4000 份生成文档的差分对比中影响 29 份，全部为上述两类，无误报新增、无真实列表漏报。

### 性能

1. 目录遍历改为 `os.scandir` 并提前剪枝，不再进入忽略目录后再丢弃。含 `node_modules` 与虚拟环境的树，1200 份文档的枚举从 1235 ms 降到 294 ms。
2. 行内热路径在花正则之前先做字符级排除；缩进宽度改由已算出的 lstrip 结果推导。整体扫描吞吐从 11.6 MB/s 提升到 16.0 MB/s。
3. `IGNORED_DIRS` 增加 `.venv`、`venv`、`.tox`、`__pypackages__`。这是刻意的范围变化：此前会把已安装包里的 Markdown 一并扫描并报出大量无关命中。

### 变更

1. `--allow` 收紧为只接受单个路径，多路径以退出码 `2` 报错。0.2.0 已引入，此处首次写入变更记录。
2. 最低 Python 版本由 3.9 提高到 3.10。3.9 已于 2025 年 10 月停止维护，且 `mypy` 不再支持，原声明无法再验证。

### 工程化

1. 新增 `pyproject.toml`，配置 ruff（行宽 88）与 mypy 严格模式，两者在 CI 中独立成 job。
2. CI 单元测试矩阵覆盖 Python 3.10 与 3.12。
3. 新增 `benchmarks/bench_scan.py` 与 `benchmarks/bench_walk.py`，均支持 `--baseline` 对比历史版本。扫描基准交错测量以消除首次运行偏差；遍历基准在文件集异常变化时直接失败。
4. 新增 `tests/fixtures` 黄金基线与 `tools/regenerate_fixtures.py`，覆盖 frontmatter、围栏、嵌套、结构保留与抑制五类文档，防止判定行为静默漂移。

### 未变更

退出码语义仍为 `0` 通过、`1` 命中、`2` 输入错误或参数冲突。`text` 输出格式不变。检测范围仍只覆盖 Markdown 文本层的 `-`、`*`、`+`，不检测 raw HTML `<ul>`、粘贴字形与 `.mdx`。校验器仍只读、零运行时第三方依赖。

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
