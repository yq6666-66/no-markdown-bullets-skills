# no-markdown-bullets

可复制的 Agent Skill：去掉面向读者正文里由 Markdown 无序列表渲染出的黑点；保留有序列表与表格。本仓独立交付，不修改、也不依赖其他插件仓库。版本以标签与 `CHANGELOG.md` 为准。

## 问题

模型常在可见回复里写行首 `-` / `*` / `+` 加空白的无序列表（含空项），以及任务列表。GitHub 预览和不少聊天气泡会把它画成圆点。`•` / `·` 是普通字符，不是列表语法。只改一篇文案或网站 CSS，管不到下次生成、聊天和 Word。

## 功能

1. **禁止**：面向读者的无序列表与任务列表（任务列表不能靠「保留 bullet」例外留下来）。
2. **保留**：有序列表、表格、代码块、分隔线、行内强调等。
3. **例外**：用户当次明确要求保留 bullet 时，该次普通无序列表可以例外；任务列表不例外。
4. **形态**：`skills/no-markdown-bullets/`（含 `SKILL.md`）+ `scripts/strip_md_ul.py`。不做文风润色、不做浏览器/Word 插件、不发 npm 包。**不承诺**宿主强制执行：文件放入 ≠ 已加载 ≠ 模型必遵守。

## 技术

1. Python 3.10+ 标准库即可跑脚本；CI 矩阵为 3.10 与 3.12。
2. 主路径是 Skill + `strip_md_ul.py`；`check_docx_numbering.py` / `evals/` / `python-docx` 为可选卫星。
3. 模型正文通过线：`--check` 退出码 `0`，报告 `stripped=0`，且 `summary.suppression_blocks == 0`。人工源文件仍可用抑制区。
4. 规则细节见 `docs/规则与边界.md`；安装路径见 `docs/install.md`。

## 用法

1. **推荐**：把 `skills/no-markdown-bullets/` 整目录交给对应 AI，说明按 `SKILL.md` 自适配。不以宿主 Skill 列表截图或 Discovery 为使用门槛。
2. （可选）也可复制到宿主 Skills 目录；常见路径见 `docs/install.md`。列不出也不妨碍使用。
3. （可选）把模型可见正文存成文件后检查：

```bash
python scripts/strip_md_ul.py --check --report - body.md
```

4. 脚本默认把改写结果写到标准输出，不修改源文件：

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --dry-run input.md
```

英文版见 [README.en.md](README.en.md)。许可见 `LICENSE`（MIT）。
