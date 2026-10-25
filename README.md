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
tests/test_check_markdown_bullets.py
docs/design.md                   # 根因、竞品结论与取舍
.github/workflows/validate.yml
```

## 安装与迁移

整个 `no-markdown-bullets` 目录就是独立 Skill 包，不依赖本仓库的其他文件。将它复制到目标工具读取的 Skills 目录即可；包内只使用相对路径，校验器仅依赖 Python 3.9+ 标准库。

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

用户对某次输出的明确要求可以覆写默认约定，但例外不自动延续到其他内容。`--allow` 用于这种已知例外：仍报告命中，只把违规退出码改为成功。

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

输出格式为 `路径:行号: 说明`。退出码 `0` 表示通过，`1` 表示发现无序列表，`2` 表示路径或读取错误。明确覆写时使用：

```bash
python scripts/check_markdown_bullets.py --allow approved-exception.md
```

脚本只读，不自动改写。自动替换无法可靠地区分步骤、对比和叙述，因此修复应依据 `references/scenarios.md` 选择语义结构。

## 开发验证

在仓库根目录运行：

```bash
python -m unittest discover -s tests -v
python no-markdown-bullets/scripts/check_markdown_bullets.py no-markdown-bullets/examples/good.md
python no-markdown-bullets/scripts/check_markdown_bullets.py no-markdown-bullets/examples/bad.md
```

最后一条应返回退出码 `1`，因为 `bad.md` 是故意保留的违规样本。

## 范围

此项目只约束 Markdown 无序列表。它不禁用编号列表或表格，不修改语言风格，不检查事实，不替代文档排版工具，也不保证所有聊天客户端都支持表格。
