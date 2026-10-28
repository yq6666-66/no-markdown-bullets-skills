# 集成说明

这份说明写给后面要把本仓库接到助手、校验或文档流水线里的人。按下面的接口复制 Skill、调用脚本、阅读 fixtures 即可，不必从提交记录里反推行为。

## 1. 本次完成内容与核心变更

本分支交付方案 v3.1 的 M0 和 M1，不合并，也不发布 Release。

已经写入仓库的内容：

1. 诚实状态的 `README.md`、三份可执行文档、MIT `LICENSE`。
2. `skills/no-markdown-bullets/SKILL.md`，含宿主加载字段。
3. `scripts/strip_md_ul.py`，按块状态机剥 UL，而不是逐行替换字符。
4. `fixtures/` 与 `tests/test_strip_md_ul.py`。每个例子都有输入、预期和跳过理由。
5. 在这条基线上又补了抑制区、front matter 遮罩缺口、`--report`、`scripts/check_docx_numbering.py`、`evals/` 和 `docs/install.md`。本文件描述的是补完之后的接口。仍然不合并，也不发布 Release。

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
| 放置路径 | 复制整个目录，不要只复制正文进系统提示后就把原文件扔掉。建议放置是 `.agents/skills/no-markdown-bullets`。`.codex/skills` 是兼容与历史路径，是否读取以安装版本为准。发现结果待验证 |
| 强制声明 | 集成方不能把「文件已复制」写成「宿主已强制执行」 |
| 验证 | 先看宿主的 Skill 名单，再显式调用，再对模型正文跑 `--check`。通过线是退出码 `0`、`stripped=0`，且没有抑制区（`--report` 的 `summary.suppression_blocks` 为 `0`，或正文里没有 `no-markdown-bullets:`）。人工源文件仍可使用抑制区。docx、evals、`python-docx` 不在这条线里 |
| 例外 | 只允许用户当次明确要求的普通 UL。任务列表没有例外 |

本仓当前 frontmatter 仅使用 `name` 与 `description`；不要新增未经验证的 `display_name` 等键冒充列表中文名已支持。中文显示名属宿主能力，见 `docs/宿主适配-Muse与WorkBuddy.md`。

Skill 不管 HTML `<ul>`，不管网站 CSS，也不做文风润色。剥后语义、体裁判断、HTML / CSS / Word 自动编号属主路径**设计边界**（非脚本侧可修缺陷）；`stripped>0` 须人工改写再验。docx 检查器为卫星，退出码勿与主剥除器混读。

### 脚本 CLI

程序：`scripts/strip_md_ul.py`。只接受一个可选路径；省略或写成 `-` 时读 stdin。不扫描目录。

| 调用 | 标准输出 | 源文件 |
| --- | --- | --- |
| 默认 | 改写后的全文 | 不写 |
| `--check` | 空 | 不写。退出码与默认改写相同 |
| `--dry-run` | 与默认相同的全文 | 不写，并在 stderr 追加 `info: dry-run source-not-modified` |
| `--report PATH` | 与是否 `--check` 有关，规则同上 | 不写。JSON 写到 PATH |
| `--report -` | 与是否 `--check` 有关，规则同上 | 不写。JSON 写到 stderr，不再混入人类可读诊断 |
| `--version` | `strip_md_ul.py 3.3.1` 后以退出码 0 结束 | 不读、不写 |

`--check` 和 `--dry-run` 不能同时用。`--report` 可以和二者之一同用。`--version` 打印版本号后结束，不读取输入。脚本没有把结果写回文件的参数，也没有保留 bullet 或保留任务列表的参数。JSON 报告禁止写到 stdout。除 `--version` 的版本行外，stdout 只可能是改写正文或空。

这里的 `__version__` 和 `--version` 只属于 `strip_md_ul.py`。`check_docx_numbering.py` 的 `__version__` 单独演进，见「docx 检查器」。

退出码：

| 码 | 含义 | 调用方 |
| --- | --- | --- |
| 0 | 结果没有残留 UL | 可以采用 stdout。若还要证明源文件本来就干净，必须同时看到 `stripped=0` |
| 2 | 有跳过，且结果没有残留 UL | 先补上未闭合的围栏、抑制区或 HTML 原始块，再决定要不要采用 stdout |
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
| `warning: unclosed suppression at line <N>; keeping through EOF` | 未闭合抑制区。从该行到 EOF 原样保留 |

`--report` 的 JSON 对象字段：

| 字段 | 含义 |
| --- | --- |
| `tool` | 固定 `strip_md_ul` |
| `version` | 当前是 `3.3.1` |
| `source` | 输入路径；stdin 时为 `<stdin>` |
| `exit_code` | 与进程退出码相同，只可能是 `0`、`2`、`1` |
| `stripped_lines` | 被剥 UL 的输入行号 |
| `warnings` | 跳过类告警 |
| `diagnostics` | 与人类可读诊断相同的字符串，含 `info:` 行 |
| `regions` | 不改写区域。`kind` 为 `frontmatter` 或 `suppression` |
| `summary` | `exit_code`、`stripped`、`suppression_blocks`、`suppressed_lines` |
| `findings` | `line`、`code`、`exit_class` |

`code` 目前有 `stripped`、`unclosed-suppression`、`unclosed-fence`、`unclosed-html`、`residual-unordered-list`、`created-skip`。`exit_class` 分别对应 `0`、`2`、`2`、`2`、`1`、`1`。进程退出码不是把这些 class 相加，而是取更严重的一档：出现 `1` 则退出码为 `1`，否则出现 `2` 则退出码为 `2`，否则为 `0`。`stripped` 的 class 是 `0`，只表示发生过剥除。报告里没有改写后的正文。

### 抑制区

和 front matter 共用 `regions`。语义是范围内保持原样，不是「发现了但不报告」。

1. `off` 和 `on` 都必须带非空 `reason`，双引号或单引号均可。
2. 不嵌套。开启期间再次 `off` 不增加层数，第一个有效 `on` 结束整段。
3. 未闭合则保留到 EOF，告警，在没有更严重失败时退出码为 `2`。
4. 围栏、HTML 原始块、front matter、缩进代码里的指令无效。
5. 抑制区内的空行不清外侧列表。`suppressed_lines` 计区内被原样抄写的行，不含 `off` / `on` 两行本身。

Front matter 的缺口按遮罩补齐：TOML `+++`、中间空行则整段不算、闭合标记必须落在开标记之后 200 行内。YAML 仍允许 `...` 闭合。

### 卫星（可选，不进 Skill 验证主路径）

`scripts/check_docx_numbering.py`、`evals/` 和 `python-docx` 是**卫星（可选，不进 Skill 验证主路径）**。可进仓库、可手动用，集成时也可以不接。主路径仍是 Skill 加 `scripts/strip_md_ul.py`。下面两节只说明手动怎么用。

### docx 检查器

程序：`scripts/check_docx_numbering.py`。只读 `.docx`，报告 `numFmt` 为 `bullet` 的段落，decimal 不报。标准库实现，不依赖 `python-docx`。

它的退出码和剥除器不同：`0` 没有 bullet 编号，`1` 发现了 bullet 编号，`2` 读不了。集成时不要把这里的 `1` 当成剥除器的失败，也不要把它的 stdout 当成改写正文。`--format json` 是这个检查器自己的输出，因为这个工具本来就没有改写正文。

版本号也独立。真源是各脚本源码里的 `__version__`，不要用主剥除器的发版号推断本检查器。截至本 tip（`2e274e18`）：`scripts/strip_md_ul.py` 的 `__version__` 是 `3.3.1`，`scripts/check_docx_numbering.py` 的 `__version__` 是 `0.1.0`。两号不一致不是缺陷。下面两条只读核对不读正文、不改文件，并以退出码 0 结束：

```bash
python scripts/strip_md_ul.py --version
python scripts/check_docx_numbering.py --version
```

截至本 tip，前者打印 `strip_md_ul.py 3.3.1`，后者打印 `check_docx_numbering 0.1.0`。以后以 `__version__` 为准。退出码语义仍按上一段区分，不因为版本号不同而合并。

### evals

目录：`evals/`。八条固定提示在 `prompts.json`。子弹数来自 `strip_text` 的 `stripped_lines`，被保留的区域不计入。

CI 只执行 `python evals/run_eval.py --dry-run`，并靠单元测试检查提示集结构。不要往默认 CI 加会调用模型的任务。手动对照见 `evals/README.md`。

默认仓库 CI（单元测试 + `python evals/run_eval.py --dry-run`）不是宿主交付门禁。门禁示例见 §4，通过口径见 §5.1，不要在这里另写一套。

### 安装

宿主放置、更新、卸载和自测清单在 `docs/install.md`。复制到宿主的是 `skills/no-markdown-bullets/`。脚本留在本仓库的 `scripts/`。

### Python 接口

库函数是 `strip_text(text: str) -> StripResult`。`StripResult` 的字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `text` | `str` | 改写结果，保留原换行 |
| `exit_code` | `int` | `0` / `1` / `2` |
| `diagnostics` | `list[str]` | 与 CLI stderr 相同的诊断，不含 dry-run 那一行 |
| `stripped_lines` | `list[int]` | 输入中被剥的行号 |
| `warnings` | `list[str]` | 跳过类告警 |
| `regions` | `list[dict]` | front matter 与抑制区，字段见报告 |
| `suppressed_lines` | `int` | 抑制区内原样抄写的行数，不含指令行 |
| `suppression_blocks` | `int` | 成功开启的抑制区个数 |

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

块规则的文字说明在 `docs/规则与边界.md`。实现顺序是：front matter 与抑制区、围栏、HTML 原始块、表格、分隔线、列表续行与缩进代码、其余 UL。引用变浅会结束更深引用里的围栏和列表帧。

## 3. 集成依赖

| 依赖 | 要求 |
| --- | --- |
| Python | 3.10 及以上标准库。用到 `argparse`、`re`、`pathlib`、`dataclasses`、`json`，剥除器没有第三方包 |
| 安装 | 不需要 `pip install`，也不发布 npm 包。安装步骤见 `docs/install.md` |
| 可选测试 | `python-docx` 是**卫星（可选，不进 Skill 验证主路径）**。没装时 docx 真实文档测试跳过。CI 会安装它再跑全部测试 |
| 网络 | 运行脚本和单元测试都不访问网络。evals 的手动 `--command` 可能访问网络，那不在默认 CI 里 |
| 系统 | 无。stdin / stdout 使用二进制读写以保住 CRLF |
| 已验证版本 | CI 矩阵是 Python 3.10 和 3.12。本仓库不把 ruff / mypy 放进这轮 CI |

宿主是否能发现 Skill，不是 Python 依赖，本仓库也没有把它标成已验证。

## 4. 调用方式

复制 Skill：

```text
skills/no-markdown-bullets/   →   <项目>/.cursor/skills/no-markdown-bullets/
```

用户级 Cursor 目录是 `~/.cursor/skills/no-markdown-bullets/`。建议放置是 `<项目>/.agents/skills/no-markdown-bullets/` 和 `~/.agents/skills/no-markdown-bullets/`。`<项目>/.codex/skills/no-markdown-bullets/` 与 `~/.codex/skills/no-markdown-bullets/` 是兼容与历史路径，是否仍被读取以安装版本为准。发现结果待验证。

命令在仓库根目录执行：

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --check input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py --report report.json input.md
python scripts/strip_md_ul.py --report - --check input.md
python scripts/strip_md_ul.py < input.md
python scripts/strip_md_ul.py - < input.md
python scripts/check_docx_numbering.py report.docx
python evals/run_eval.py --dry-run
python -m unittest discover -s tests -v
```

把剥过的正文存到新文件，而不是覆盖源文件：

```bash
python scripts/strip_md_ul.py input.md > input.stripped.md
echo $?
```

只有退出码是 `0` 时，才把 `input.stripped.md` 当作可用正文。退出码是 `2` 时先看 stderr 里的未闭合位置。退出码是 `1` 时删除这个输出。上面这段只用于交互分诊，先看 `echo $?`。它不是交付门禁。

**交付 / 宿主门禁。** 通过口径不在这里重写，见 §5.1；退出码 `0` 不等于输入干净，见 §5.4。先把进程退出码记入 `rc`，再读 `--report` 里的 `summary.stripped` 与 `summary.suppression_blocks`，三项都要断言。不要用 `&&` 在非 0 时短路，以免看不到原来的 `rc`。不要用 `命令 | grep` 当门禁。`suppression_blocks` 必须为 `0`。

```bash
python scripts/strip_md_ul.py --check --report report.json body.md
rc=$?
echo "rc=$rc"
python - "$rc" report.json <<'PY'
import json
import sys

rc = int(sys.argv[1])
summary = json.load(open(sys.argv[2], encoding="utf-8"))["summary"]
stripped = summary["stripped"]
blocks = summary["suppression_blocks"]
print("rc=%s stripped=%s suppression_blocks=%s" % (rc, stripped, blocks))
ok = True
if rc != 0:
    ok = False
if stripped != 0:
    ok = False
if blocks != 0:
    ok = False
sys.exit(0 if ok else 1)
PY
```

若 `report.json` 没有写成，剥除器在写报告之前就退出了。以已经记下的 `rc` 为准，不要把随后的解析错误当成剥除器的退出码。

## 5. 注意事项

下面第 1 条是模型正文通过线（§5.1）。第 4 条只说明退出码 `0` 不等于输入干净（§5.4）。交付门禁示例见 §4，不要把那里的 `echo $?` 当成 §5.1。

1. 宿主不强制。复制 Skill 只是让支持该机制的工具有机会读到约定。集成完成的标志是 Skill 名单里出现名字，加上一次显式调用后模型正文满足 `--check` 退出码 `0`、`stripped=0`、且没有抑制区。不是文件已经存在。人工源文件仍可使用抑制区。`--report` 里要看的是 `summary.suppression_blocks == 0`，不能放宽。交互分诊的 `echo $?` 不是这条通过线。
2. 任务列表没有例外，也没有保留开关。即使用户说保留 bullet，`- [ ]` 和 `- [x]` 仍要改成纯文本，并且不能宣称勾选还在。这种「当次保留普通 UL」的输出不要送进脚本，脚本会把普通 UL 也剥掉。
3. 例外只覆盖用户当次明确提出的那一份普通 UL，不写成全局偏好，也不要做成配置文件里的默认项。
4. 退出码 `0` 表示结果干净，不表示输入干净。`--check` 同样如此，它只是不把正文打出来。宿主交付不能停在本条，完整口径是 §5.1，示例见 §4。
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

全部通过才算脚本和 fixtures 的验收通过。默认仓库 CI 还要加上 `python evals/run_eval.py --dry-run`。这两步都不是宿主交付门禁，见 §4 与 §5.1。Skill 的宿主发现不在这条命令里，状态保持待验证。
