# 集成说明

这份说明写给后面要把本仓库接到助手、校验或文档流水线里的人。按下面的接口复制 Skill、调用脚本、阅读 fixtures 即可，不必从提交记录里反推行为。

## 1. 本次完成内容与核心变更

本分支交付方案 v3.1 的 M0 和 M1，不合并，也不发布 Release。

已经写入仓库的内容：

1. 诚实状态的 `README.md`、三份可执行文档、MIT `LICENSE`。
2. `skills/no-markdown-bullets/SKILL.md`，含宿主加载字段。
3. `scripts/strip_md_ul.py`，按块状态机剥 UL，而不是逐行替换字符。
4. `fixtures/` 与 `tests/test_strip_md_ul.py`。每个例子都有输入、预期和跳过理由。

相对本仓库原先的只读检查器，核心变更是：

| 原先 | 现在 |
| --- | --- |
| `no-markdown-bullets/scripts/check_markdown_bullets.py` 只报告 UL，退出码 `1` 表示「发现了 UL」 | 该检查器已删除。`scripts/strip_md_ul.py` 把改写结果写到 stdout，退出码 `0` 表示「结果里没有残留 UL」 |
| Skill 放在仓库根下的 `no-markdown-bullets/SKILL.md` | 改为 `skills/no-markdown-bullets/SKILL.md`，并写明手工放置路径、不强制生效、以及怎么验证 |
| 旧设计说明放在 `docs/design.md` | 该文件已删除。本分支只描述自己的约定和脚本 |

两套退出码不能混用。旧检查器的 `1` 是「有 UL」，新脚本的 `1` 是「失败」。新脚本的 `0` 也不等于「源文件本来就没有 UL」。

## 2. 关键模块与接口

### Skill 约定

文件：`skills/no-markdown-bullets/SKILL.md`。

| 字段 | 集成时怎么用 |
| --- | --- |
| `name` | 固定为 `no-markdown-bullets`。宿主若靠 front matter 发现 Skill，用这个名字 |
| `description` | 说明何时启用：生成或改写面向读者的正文，且需要分点、步骤或对照 |
| 放置路径 | 复制整个目录，不要只复制正文进系统提示后就把原文件扔掉。Cursor 与 Codex 的路径写在 Skill 正文和 README 里，发现结果都是待验证 |
| 强制声明 | 集成方不能把「文件已复制」写成「宿主已强制执行」 |
| 验证 | 先看宿主的 Skill 名单，再显式调用，再用脚本的 `stripped=0` 作通过线 |
| 例外 | 只允许用户当次明确要求的普通 UL。任务列表没有例外 |

Skill 不管 HTML `<ul>`，不管网站 CSS，也不做文风润色。

### 脚本 CLI

程序：`scripts/strip_md_ul.py`。只接受一个可选路径；省略或写成 `-` 时读 stdin。不扫描目录。

| 调用 | 标准输出 | 源文件 |
| --- | --- | --- |
| 默认 | 改写后的全文 | 不写 |
| `--check` | 空 | 不写。退出码与默认改写相同 |
| `--dry-run` | 与默认相同的全文 | 不写，并在 stderr 追加 `info: dry-run source-not-modified` |

`--check` 和 `--dry-run` 不能同时用。脚本没有把结果写回文件的参数，也没有保留 bullet 或保留任务列表的参数。

退出码：

| 码 | 含义 | 调用方 |
| --- | --- | --- |
| 0 | 结果没有残留 UL | 可以采用 stdout。若还要证明源文件本来就干净，必须同时看到 `stripped=0` |
| 2 | 有跳过，且结果没有残留 UL | 先补上未闭合的围栏或 HTML 原始块，再决定要不要采用 stdout |
| 1 | 失败 | 丢弃 stdout。不要把它当成功结果写回 |

诊断都在 stderr，正文都在 stdout。用管道时不要把二者混在一起。stdout 按 UTF-8 字节写出，是为了保住输入里的 CRLF；不要再包一层会把 `\n` 翻译成 `\r\n` 的文本模式。

稳定诊断行：

| 行 | 含义 |
| --- | --- |
| `info: stripped=<N> lines=<行号或 ->` | 从输入剥掉的 UL 行，行号从 1 计 |
| `warning: unclosed fence at line <N>; skipping through EOF` | 未闭合围栏，开栏之后直到 EOF 都跳过 |
| `warning: unclosed html block at line <N>; skipping through EOF` | 未闭合的 `pre` / `script` / `style` / `textarea` 等 |
| `error: residual unordered list at output line <N>` | 输出里仍有 UL |
| `error: strip created a skipped region; result is unfinished` | 剥完后新产生了跳过区 |
| `info: dry-run source-not-modified` | 只在 `--dry-run` 时出现 |

### Python 接口

库函数是 `strip_text(text: str) -> StripResult`。`StripResult` 的字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `text` | `str` | 改写结果，保留原换行 |
| `exit_code` | `int` | `0` / `1` / `2` |
| `diagnostics` | `list[str]` | 与 CLI stderr 相同的诊断，不含 dry-run 那一行 |
| `stripped_lines` | `list[int]` | 输入中被剥的行号 |
| `warnings` | `list[str]` | 跳过类告警 |

用文件路径加载时，要先把模块放进 `sys.modules`，再执行加载。否则 dataclass 在导入时会失败。

```python
import importlib.util
import sys
from pathlib import Path

path = Path("scripts/strip_md_ul.py")
spec = importlib.util.spec_from_file_location("strip_md_ul", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

result = module.strip_text(source_text)
if result.exit_code != 0:
    raise SystemExit(result.exit_code)
```

`strip_text` 不读文件，也不写文件。

### fixtures 约定

每个用例是 `fixtures/<编号>_<名字>/` 目录：

| 文件 | 约定 |
| --- | --- |
| `input.md` | 原始字节。CRLF 和无末尾换行必须保住 |
| `expected.md` | 跑一遍之后的正文，不是「再跑到幂等为止」的正文 |
| `meta.json` | `description`、`expect_exit`、`skip_reason` 三个字段都必填 |

`skip_reason` 在没有特殊跳过时写「无」，并说明这个例子钉住的行为。`expect_exit` 为 `1` 的例子不要求幂等；`0` 和 `2` 要求再跑一次正文不变、退出码不变。

`fixtures/23_crlf` 和 `fixtures/25_no_final_newline` 在 `.gitattributes` 里标成不做换行转换。新增同类用例时要同样处理。

块规则的文字说明在 `docs/规则与边界.md`。实现顺序是：front matter、围栏、HTML 原始块、表格、分隔线、列表续行与缩进代码、其余 UL。

## 3. 集成依赖

| 依赖 | 要求 |
| --- | --- |
| Python | 3.10 及以上标准库。用到 `argparse`、`re`、`pathlib`、`dataclasses`，没有第三方包 |
| 安装 | 不需要 `pip install`，也不发布 npm 包 |
| 网络 | 运行脚本和单元测试都不访问网络 |
| 系统 | 无。stdin / stdout 使用二进制读写以保住 CRLF |
| 已验证版本 | 本交付在 Python 3.12 上跑通 `python -m unittest discover -s tests -v`。CI 同样使用 3.12。3.10 与 3.11 没有在本交付里逐一复跑 |

宿主是否能发现 Skill，不是 Python 依赖，本仓库也没有把它标成已验证。

## 4. 调用方式

复制 Skill：

```text
skills/no-markdown-bullets/   →   <项目>/.cursor/skills/no-markdown-bullets/
```

用户级 Cursor 目录是 `~/.cursor/skills/no-markdown-bullets/`。Codex 的对应目录是 `<项目>/.codex/skills/no-markdown-bullets/` 和 `~/.codex/skills/no-markdown-bullets/`。复制后按 README 的三步做发现和显式调用。发现没有做完时，集成记录里写待验证。

命令在仓库根目录执行：

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --check input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py < input.md
python scripts/strip_md_ul.py - < input.md
python -m unittest discover -s tests -v
```

把剥过的正文存到新文件，而不是覆盖源文件：

```bash
python scripts/strip_md_ul.py input.md > input.stripped.md
echo $?
```

只有退出码是 `0` 时，才把 `input.stripped.md` 当作可用正文。退出码是 `2` 时先看 stderr 里的未闭合位置。退出码是 `1` 时删除这个输出。

## 5. 注意事项

1. 宿主不强制。复制 Skill 只是让支持该机制的工具有机会读到约定。集成完成的标志是 Skill 名单里出现名字，加上一次显式调用后 `stripped=0`，不是文件已经存在。
2. 任务列表没有例外，也没有保留开关。即使用户说保留 bullet，`- [ ]` 和 `- [x]` 仍要改成纯文本，并且不能宣称勾选还在。这种「当次保留普通 UL」的输出不要送进脚本，脚本会把普通 UL 也剥掉。
3. 例外只覆盖用户当次明确提出的那一份普通 UL，不写成全局偏好，也不要做成配置文件里的默认项。
4. 退出码 `0` 表示结果干净，不表示输入干净。`--check` 同样如此，它只是不把正文打出来。
5. 未闭合围栏会跳过开栏之后的全部文本，后面的正文 UL 也不会剥，退出码为 `2`。调用方应先补闭合围栏，不要把跳过当成已检查通过。
6. 空行会打断列表的紧邻续行。空行之后、缩进大于等于 4、形如列表的行会当作缩进代码保留。这是 fixture 钉死的规则，不是「凡是看起来像 `- item` 的行都剥」。
7. 不保证语义等价。`- # 标题` 会变成标题。失败结果不保证再跑一次还相同，例如 `- - still`。
8. HTML `<ul>` 不转换。块级 HTML 要遇到空行才结束，`</div>` 下一行如果没有空行，仍算在原始块里面。
9. 不要把本仓库的文件改写进其他既有插件仓库，也不要让本脚本去依赖那些仓库。本交付的范围只到这个仓库。
10. 不要在本仓库上加文风润色、npm 包、浏览器插件、Word 插件，或去改 GitHub 的 CSS。
11. 密钥和讨论过程的原始接口记录不要放进本仓库。fixtures 只放 Markdown 样例。

## 6. 验收

在仓库根目录执行：

```bash
python -m unittest discover -s tests -v
```

全部通过才算脚本和 fixtures 的验收通过。Skill 的宿主发现不在这条命令里，状态保持待验证。
