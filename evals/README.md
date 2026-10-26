# 抽样度量

这个目录回答一个此前没有证据的问题：这条规则到底有没有改变模型的输出。

`scripts/strip_md_ul.py` 只能证明剥除器自己是对的。它剥得准，不等于模型会因为装了 Skill 就少写圆点。度量要做的就是把这两件事分开。

子弹数使用剥除器的 `stripped_lines`。front matter 和抑制区里保留下来的标记不会计入。这和剥除器的通过线一致。

## 能证明什么

在两个条件之间做对照时，条件 A 的答案里有相当比例包含无序列表，条件 B 明显更少，同时编号列表和表格没有一起消失，解释型问题的答案仍然是段落而不是一堆编号。

这就是规则有效的全部含义。反过来，如果 B 的圆点比例没降，规则无效。如果圆点降了但 `explain-why` 和 `anti-bait-prose` 变成了编号列表，那就是过度矫正，同样是失败。

## 不能证明什么

单次运行只是基线，不是结果。没有对照组就没有归因，工具会在结果末尾打印这句话。

即使两次都对，也不能排除混淆因素：模型版本、温度、系统提示、工具版本任何一项不同，delta 都不可信。要下结论，两次运行必须同模型、同温度、同提示文本。

八条提示也不足以支撑统计显著性。它测的是方向，不是效应量。

## 和 CI 的关系

默认 CI 只做离线校验：单元测试会检查 `prompts.json` 的条数、id 和期望结构，`python evals/run_eval.py --dry-run` 只打印提示集。CI 不调用模型，也没有 eval-harness 任务。

真正的对照要在本机手动跑，并自己保存结果。

## 提示集

`prompts.json` 有八条，每条声明一个期望结构。其中两条是诱饵，一条是反诱饵。

诱饵是 `bait-list` 和 `bait-bullet-points`。列一下、用 bullet points 这类措辞比任何别的说法都更容易把模型推向圆点。反诱饵是 `anti-bait-prose`。用户明确要求不分条，用来抓过度矫正。

期望结构取值：`prose`、`ordered`、`table`、`table_or_ordered`、`ordered_or_prose`。

## 两种输入方式

### 已有答案

按 `<目录>/<条件>/<提示 id>.md` 存放，或者直接放在 `<目录>/<提示 id>.md` 下：

```bash
python evals/run_eval.py --samples evals/samples --condition baseline
```

缺某条提示的答案会打印警告并跳过，不会静默当成零分。

### 现跑

`--command` 接受任何从 stdin 读提示、向 stdout 写答案的命令。这一步会执行你给的命令。不要把它放进默认 CI。

```bash
python evals/run_eval.py --command "my-agent --print" --condition with-skill
```

命令退出码非零会直接报错终止，不会把空答案算成合规。

## 对比

```bash
python evals/run_eval.py --compare evals/results/a.json evals/results/b.json
```

输出逐条对比表和总体 delta。负的 `bullet_rate` delta 是期望方向。

## 指标

每条答案记录：`bullets`、`ordered`、`tables`、`paragraphs`、`chars`、`longest_block`、`expectation_met`。

`longest_block` 是单个段落块的最大字符数，用来盯把所有内容压成一大段这类反向退化。段落变长、结构全无，圆点确实少了，但可读性更差。这个字段就是为这种情况留的。

## 结果文件

`evals/results/` 已在 `.gitignore` 中。结果依赖具体模型和日期，不适合入库。需要留档时把 JSON 附在 issue 或 PR 里，并注明确切条件。
