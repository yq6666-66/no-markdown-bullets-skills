# fixtures

每个用例是一个目录，里面固定三份文件。

| 文件 | 作用 |
| --- | --- |
| `input.md` | 输入原文，按字节保留换行 |
| `expected.md` | 跑一遍 `scripts/strip_md_ul.py` 后的正文 |
| `meta.json` | `description`、`expect_exit`、`skip_reason` |

`expect_exit` 与脚本退出码相同：`0` 表示结果里没有残留 UL，`2` 表示处理中有跳过，`1` 表示失败。`skip_reason` 说明本例为什么有些标记没有剥，或者为什么判定失败；没有特殊跳过时写「无」，并补一句这个例子在钉什么行为。

`23_crlf` 与 `25_no_final_newline` 在 `.gitattributes` 里标成不按文本换行转换，避免 CRLF 和无末尾换行被改掉。

新增用例时沿用两位数字前缀，让排序稳定。仓库根目录的 `python -m unittest discover -s tests -v` 会读取这里的全部目录。

`42` 起是移植进来的边界：front matter 空行和长度窗口、TOML 头部、引用打断列表或围栏、抑制区，以及从检查器黄金样例改写成剥除期望的 `59` 到 `63`。`66` 和 `67` 是引用回归，移植前在现有剥除器上已经得到同样的正文。`68` 钉住抑制区内的空行不清外侧列表。`69` 钉住行首四格的抑制指令不开启抑制区。
