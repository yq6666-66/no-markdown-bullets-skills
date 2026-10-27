# no-markdown-bullets

可复制的 Agent Skill：禁止面向读者正文里的 Markdown 无序列表（预览里常见的大黑点），保留有序列表与表格；附带标准库剥除/检查脚本。本仓库独立交付，不修改、也不依赖其他插件仓库。当前版本以仓库标签 **v3.2.0** 与 `CHANGELOG.md` 为准。

## 问题

模型常在可见回复里写行首 `-` / `*` / `+` 加空白的无序列表（含空项与任务列表）。GitHub 预览和不少聊天气泡会把它画成圆点（常见 `list-style: disc`）。只改一篇文案或只改网站 CSS，管不到下次生成、聊天和 Word。需要一份可复制的约定，说明禁什么、留什么、例外何时成立。

## 功能

1. **Skill 约定**：把「禁无序列表 / 留编号与表格 / 例外与抑制区」收成可整目录交给 AI 的 `skills/no-markdown-bullets/`（含 `SKILL.md`）。
2. **剥除与检查**：`scripts/strip_md_ul.py` 处理已写出的 UL 标记；`--check` / `--report` 给出通过线（退出码、`stripped`、抑制区计数）。
3. **三场景指引**：在 GitHub 上改源码结构；聊天交给 AI 按 Skill 生成并可选跑脚本；Word / WPS 粘贴纯文本或取消项目符号（详见 `docs/`）。
4. **不承诺**：不承诺宿主强制加载或任意模型 100% 遵守；文件放入目录 ≠ 已加载 ≠ 一定遵守。`check_docx_numbering.py`、`evals/`、`python-docx` 为可选卫星，不进主验证路径。

## 技术

1. **运行时**：Python 3.10+ 标准库即可跑主脚本；CI 矩阵为 3.10 与 3.12。
2. **主路径**：Skill + `scripts/strip_md_ul.py` + `fixtures/` / 单元测试。
3. **通过线（模型正文）**：`--check` 退出码 `0`，报告 `stripped=0`，且 `summary.suppression_blocks == 0`（或正文无 `no-markdown-bullets:` 抑制注释）。人工源文件仍可使用抑制区。
4. **接口说明**：后续集成见 `INTEGRATION.md`；规则细节见 `docs/规则与边界.md`。

## 用法

1. 把 `skills/no-markdown-bullets/` 整目录交给目标 AI，或复制到宿主 Skills 目录（常见路径示例见 `docs/install.md`）；说明按 `SKILL.md` 生成。
2. （可选）把模型可见正文存成文件后检查：

```bash
python scripts/strip_md_ul.py --check --report - 输出.md
```

3. 改写到标准输出、不覆盖源文件的常用命令：

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py --report report.json input.md
```

4. 仓库自测：

```bash
python -m unittest discover -s tests -v
```

英文版见 [README.en.md](README.en.md)。

## 许可

MIT，见 `LICENSE`。
