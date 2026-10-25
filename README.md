# no-markdown-bullets-skills

一个可迁移的 Markdown 格式约束 Skill：在内容生成源头避免无序列表，保留编号列表和表格，并用只读脚本验证结果。

它解决的是 `-`、`*`、`+` 形成的 `<ul>` 被渲染为 `disc` 黑色圆点的问题，不是“人味”润稿，也不修改 GitHub 全局 CSS。

## 仓库内容

```text
no-markdown-bullets/
  SKILL.md                       # 可直接放入 Skills 目录的完整约定
  references/scenarios.md        # GitHub、聊天、Word 的分场景规则
  scripts/check_markdown_bullets.py
  examples/good.md
  examples/bad.md                # 故意违规，供负例验证
  examples/suppression.md        # 作用域抑制的端到端示例
tests/test_check_markdown_bullets.py
docs/design.md                   # 根因、方案取舍与判定边界
CHANGELOG.md
.github/workflows/validate.yml
```

## 安装与迁移

整个 `no-markdown-bullets` 目录就是独立 Skill 包，不依赖本仓库的其他文件。将它复制到目标工具读取的 Skills 目录即可；包内只使用相对路径，校验器仅依赖 Python 3.10+ 标准库。

以 WorkBuddy 为例，单个项目可复制到 `<项目>/.workbuddy/skills/no-markdown-bullets`，跨项目复用可复制到 `~/.workbuddy/skills/no-markdown-bullets`。其他支持 `SKILL.md` 的 Agent 工具也可按各自的 Skills 目录约定放置。

迁移后保留 `SKILL.md`、`references` 和 `scripts` 的相对结构。`examples` 可省略，不影响执行。

## 默认行为

生成用于 GitHub、聊天或 Word 的内容时，连续叙述用段落，步骤和需要逐项引用的内容用编号列表，同构字段用表格。不要先生成无序列表再替换符号。

以下输入都会被识别为无序列表，包括任务列表、嵌套列表和引用块中的列表：

```markdown
- 普通项目
* 星号项目
+ 加号项目
- [ ] 任务项目
> - 引用中的项目
```

以下内容保留，不会被误判：

```markdown
1. 编号列表

| 字段 | 含义 |
| --- | --- |
| format | 格式约束 |

---

行内 *强调* 不是列表。

    - 缩进代码示例
```

闭合的 YAML 或 TOML frontmatter 内部整段跳过，因此 `tags:` 下的缩进条目不会被误报。未闭合的 frontmatter 不启用跳过，仍按正文检查，避免吞掉正文造成漏报。

## 检测边界

检测只覆盖 Markdown 文本层。以下形态不在检测范围，不要因为返回 `0` 就认为没有问题来源：

| 形态 | 是否检测 | 说明 |
| --- | --- | --- |
| 行首 `-`、`*`、`+`，含任务列表、嵌套、引用块内 | 检测 | 核心目标 |
| 闭合的 `---` 或 `+++` frontmatter 内部 | 跳过 | 配置数据不是正文 |
| raw HTML `<ul>`、`<li>` | 不检测 | 需要 HTML 解析，超出单文件脚本职责 |
| 粘贴产生的 `•`、`·`、`◦` | 不检测 | 字形不是 Markdown 语法 |
| `.mdx`、`.markdown` | 不扫描 | 仅处理 `.md` |

## 例外治理

用户对某次输出的明确要求可以覆写默认约定，但例外不自动延续到其他内容。单个文件整体放行使用 `--allow`，它只接受一个路径：

```bash
python scripts/check_markdown_bullets.py --allow approved-exception.md
```

传入多个路径并带 `--allow` 会以退出码 `2` 报错，因为多文件放行等于关掉检查。

文件内部需要局部例外时，用成对的行内指令并写明理由：

```markdown
<!-- no-markdown-bullets: off reason="兼容旧版模板，2026Q4 移除" -->
- 这一行被豁免
<!-- no-markdown-bullets: on reason="恢复检查" -->
```

缺少 `reason` 或理由为空时指令不生效，区域照常检查。未闭合的 `off` 会作为违规报到该行。写在代码块内的指令无效，因此示例不会被自身豁免。豁免行数计入统计，便于发现例外堆积。

## 校验

在 Skill 目录中校验文件或目录：

```bash
python scripts/check_markdown_bullets.py examples/good.md
python scripts/check_markdown_bullets.py /path/to/docs
```

检查标准输入：

```bash
python scripts/check_markdown_bullets.py - < draft.md
```

输出格式为 `路径:行号: 说明`。退出码 `0` 表示通过，`1` 表示发现无序列表，`2` 表示路径、读取错误或参数冲突。

供 CI 消费时改为 JSON：

```bash
python scripts/check_markdown_bullets.py --format json /path/to/docs
```

顶层字段为 `tool`、`version`、`files`、`summary`。`summary` 给出 `files`、`findings`、`suppressed_lines`、`suppression_ratio`；每个文件的 `findings` 项含 `line`、`code`、`message`，`code` 当前为 `unordered-list` 或 `unclosed-suppression`。退出码语义不随输出格式变化，`text` 格式保持不变。

脚本只读，不自动改写。自动替换无法可靠地区分步骤、对比和叙述，因此修复应依据 `references/scenarios.md` 选择语义结构。

## 开发验证

在仓库根目录运行：

```bash
python -m unittest discover -s tests -v
python no-markdown-bullets/scripts/check_markdown_bullets.py no-markdown-bullets/examples/good.md
python no-markdown-bullets/scripts/check_markdown_bullets.py no-markdown-bullets/examples/suppression.md
python no-markdown-bullets/scripts/check_markdown_bullets.py no-markdown-bullets/examples/bad.md
```

前三条返回退出码 `0`，最后一条应返回 `1`，因为 `bad.md` 是故意保留的违规样本。测试套件同时校验仓库自身文档符合本规则，避免文档与实现漂移。

静态检查与性能基准：

```bash
python -m ruff check .
python -m mypy
python benchmarks/bench_scan.py --baseline <old-checker.py>
python benchmarks/bench_walk.py  --baseline <old-checker.py>
```

两个基准都接受 `--baseline` 参数以对比历史版本。扫描基准交错测量两次实现，避免首次运行更凉快带来的系统性偏差；遍历基准在文件集与基线不一致时直接失败，只有落在 `IGNORED_DIRS` 内的差异才算合理。

## 范围

此项目只约束 Markdown 无序列表。它不禁用编号列表或表格，不修改语言风格，不检查事实，不替代文档排版工具，也不保证所有聊天客户端都支持表格。

本仓库对自身 Skill 包负责，不含与外部插件、其他 Agent 生态的组合约定，也不提供安装到特定平台之外的适配。
