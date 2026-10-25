# no-markdown-bullets

去掉面向读者的正文里，由 Markdown 无序列表渲染出来的大黑点，并把这条约束做成可以复制的 Skill。

本仓库是独立的文档加 Skill 交付。它不修改、也不依赖其他插件仓库。

## 状态

M0 文档和 M1 的 Skill、剥除脚本、fixtures 都已经在本仓库里。下面说的「能用」只指这些文件，以及本仓库测试能够跑通。它不表示某个宿主已经强制执行了这条 Skill。

| 部分 | 状态 |
| --- | --- |
| `skills/no-markdown-bullets/SKILL.md` | 已写入，可以手工复制到宿主 |
| `scripts/strip_md_ul.py` 与 `fixtures/` | 已写入。验收以本仓库单元测试通过为准 |
| 宿主发现与强制执行 | 待验证。放置路径写在下面，本仓库没有某次发现实验的记录 |
| 消除一切可见黑点 | 不承诺。黑点不一定是 `disc`，Word 还受粘贴方式影响 |

一次输出里没有黑点，不能证明 Skill 已经被加载。

## 问题是什么

模型常在可见回复里使用 Markdown 无序列表：行首的 `-`、`*`、`+` 后面跟空格或 Tab，也包括只有标记的空列表项。GitHub 预览、不少聊天气泡会把这种列表画成圆点，浏览器里常见的是 `list-style: disc`。这不是缺字。

`•` 和 `·` 是普通字符，不是这种列表语法。任务列表同样是无序列表，本仓库禁止，并且不保留勾选框。

## 为什么用 Skill

同一现象会出现在 GitHub、聊天和 Word / WPS。只改一篇文案，下一次生成还会出现。只改网站 CSS 管不到聊天和 Word。Skill 把「禁什么、留什么、例外何时成立」收成一份可复制的约定。脚本用来处理已经写出来的标记，不代替生成时的约束。

本仓库不做文风润色，不做浏览器或 Word 插件，也不发布 npm 命令行包。

## 关键

要禁的是无序列表语法，不是一切列表。编号列表和表格留下。围栏、缩进代码、成对的 YAML front matter、分隔线和行内 `*强调*` 留下。

三个场景的做法不同：

1. GitHub：改源码结构，不改网站 CSS。
2. 聊天：手工放置 Skill，生成时用段落或编号；必要时对模型输出全文跑脚本。
3. Word / WPS：粘贴时只保留文本，或在软件里取消项目符号。

正面要求优先于一句「不要用列表」。用户当次明确要求保留 bullet 时，这一次普通无序列表可以例外。任务列表不在例外里。细节见 `docs/规则与边界.md`。

## 如何使用

依赖只有 Python 3.10 及以上的标准库，不需要安装第三方包。本仓库 CI 使用 Python 3.12。语法按 3.10+ 编写；本交付实际跑通测试的解释器版本，以验收记录为准。

### 放置 Skill

把目录 `skills/no-markdown-bullets/` 整份复制到宿主的 Skills 目录，其中要有 `SKILL.md`。

| 宿主 | 路径 | 状态 |
| --- | --- | --- |
| Cursor 项目 | `<项目>/.cursor/skills/no-markdown-bullets/SKILL.md` | 待验证 |
| Cursor 用户目录 | `~/.cursor/skills/no-markdown-bullets/SKILL.md` | 待验证 |
| Codex 项目 | `<项目>/.codex/skills/no-markdown-bullets/SKILL.md` | 待验证 |
| Codex 用户目录 | `~/.codex/skills/no-markdown-bullets/SKILL.md` | 待验证 |

放置之后：

1. 新开对话，请宿主列出当前能发现的 Skill，确认有 `no-markdown-bullets`。
2. 用 `docs/三场景实操.md` 里的固定提示词显式调用。
3. 把模型可见正文存成文件，执行 `python scripts/strip_md_ul.py --check 输出.md`。通过线是退出码 `0` 且 stderr 含 `stripped=0`。

### 运行脚本

在仓库根目录：

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --check input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py < input.md
```

默认把改写结果写到标准输出，不修改源文件。诊断写到 stderr。把结果保存到新文件时使用重定向，看完退出码再决定是否替换。

| 退出码 | 含义 |
| --- | --- |
| 0 | 结果里没有残留 UL。源文件里原来有 UL，只要剥干净，仍然是 0 |
| 2 | 有跳过，例如未闭合围栏。开栏之后直到文件末尾都不会剥 |
| 1 | 失败。剥后仍有 UL、文件打不开或参数错误。这时的标准输出不能当终稿 |

`--check` 不输出正文，退出码与默认改写相同。因此源文件里有 UL 时，`--check` 仍可能返回 0。确认「源文件本来就干净」要同时看到 `stripped=0`。

## 成功标准

文案上，读者应能分清黑点从哪来、禁什么、留什么，以及三个场景怎么做。这里的「短时间能看懂」不是计时测试。

| 项 | 取值 |
| --- | --- |
| 宿主 | Cursor。路径见上，发现与强制执行待验证 |
| 模型 | 待验证 |
| 版本 | 待验证 |
| 固定提示词 | 与 `docs/三场景实操.md` 文末三句相同，验收时不要改写 |
| 计数 | 解析后的待剥 UL 节点数，不是截图里的圆点 |
| 通过线 | `python scripts/strip_md_ul.py --check 输出.md` 的退出码为 `0`，且 stderr 含 `stripped=0` |
| 不计入 | 围栏、front matter、表格、缩进代码内部的标记 |
| 上限 | 不承诺任意助手或任意模型达到 100% |

固定提示词：

1. 请用普通段落说明 Markdown 无序列表为什么会在预览里变成圆点。不要使用项目符号。
2. 请写出把这段文字粘贴到 Word 之前的三步操作，使用编号列表。
3. 请用表格对比段落、编号列表、表格这三种写法。列：场景、写法、会不会变成 disc 圆点。

## 仓库内容

```text
README.md
LICENSE
INTEGRATION.md
skills/no-markdown-bullets/SKILL.md
docs/排查结论.md
docs/三场景实操.md
docs/规则与边界.md
scripts/strip_md_ul.py
fixtures/
tests/test_strip_md_ul.py
```

给后续集成的接口、依赖和调用方式写在 `INTEGRATION.md`。

## 验收

在仓库根目录执行：

```bash
python -m unittest discover -s tests -v
```

测试会核对每个 fixture 的输入、预期和退出码，检查幂等、CRLF、标准输出不覆盖源文件，并确认本仓库交付文档自身没有待剥 UL。本次交付在 Python 3.12.3 上跑通了这条命令。3.10 与 3.11 没有在本次交付里逐一复跑。

## 许可

MIT，见 `LICENSE`。
