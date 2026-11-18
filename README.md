# 有序观测湖

轨检资料组用这个本地归档保存巡检仪日批、归档勘误和复核交班。源位置可以回查仪器记录。固定日表上的复核选区随原选行的延续交给下一班，交班件可以逐行复算行数和缺测数。

## 运行

在项目根目录使用 Python 3.11。标准库自带的 SQLite 管理单文件归档。

```sh
python3 -B verify.py
python3 -B demo.py
python3 -B -m unittest discover -s tests -t . -v
```

`verify.py` 发现并运行整套业务回归，测试失败时退出码为非零。`demo.py` 读取 `samples/observations.json`，在临时目录创建归档，重新打开后按四个固定请求计算交班件。两条入口结束时由临时目录上下文清理各自生成的归档。

## 一天的工作

1. 值班员登记一份有序仪器日批，随后可按批号及批内位置核对原始读数。
2. 归档员按原序冻结同日的初版日表，得到独立的修订号。
3. 资料组可重开归档，按修订号核对固定的行位置、来源与值。
4. 质控员在一个固定修订上标记一个非空半开区间。
5. 归档员从指定父版开始，依次移动、复制或删除行，得到新修订。
6. 资料组按号分别读取父版和后继，核对更正及原标记。
7. 接班人员在指定修订领取原选区中仍存续的行。
8. 离线终端读取同次领取的交班件，核对来源、坐标、读值及摘要。

## Python 接口

```python
from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from delivery.export import export
from intake.batches import read_batch, register_batch
from review.claims import claim
from review.tickets import mark, read_ticket
from revision.coordinates import Copy, Delete, Move
from revision.publish import edit_day, seal_day

archive = open_archive('track.sqlite3')
register_batch(archive, 'run-a', '2026-11-18', [11, 22, None, 44])
raw = read_batch(archive, 'run-a')
base = seal_day(archive, '2026-11-18', 'run-a')
ticket = mark(archive, base, 1, 3)
corrected = edit_day(archive, base, [Copy(1, 4), Move(1, 0)])
withdrawn = edit_day(archive, corrected, [Delete(0)])
old_view = read_revision(archive, base)
frozen_ticket = read_ticket(archive, ticket)
claim_rows = claim(archive, ticket, corrected).rows
payload = export(archive, ticket, withdrawn)
```

- `open_archive(path)` 初始化或打开本地文件。父目录应已存在。重复初始化保留已经登记的原批、修订和标记。
- `register_batch(archive, batch_id, day_id, readings)` 返回批号。标识是非空 UTF-8 文本，读数是有序输入中的 `int` 或 `None`。同批号的日号和有序内容均相同才视作重试。`read_batch` 返回包含日号和有序源行的不可变对象。
- `seal_day(archive, day_id, batch_id)` 按同日原批生成初版。`edit_day(archive, parent_revision, operations)` 生成指定父版的一个后继。两者返回已提交的整数修订号。`read_revision` 返回不可变修订视图，含父号、日号、批号和按位置排列的行。每行提供 `position`、`source` 和 `value`，来源提供 `batch_id` 和 `position`。
- `mark(archive, revision_id, start, stop)` 返回整数标记号。要求 `0 <= start < stop <= 行数`。`read_ticket` 返回原修订号和原区间。
- `claim(archive, ticket_id, target_revision)` 返回不可变领取结果，含标记号、目标修订号和有序明细。每行提供 `marked_position`、`target_position`、`source` 和 `value`。目标须为同版或实际后继。一个标记可多次领取。
- `export(archive, ticket_id, target_revision)` 返回完整的 UTF-8 JSON 字节，含 `ticket_id`、`target_revision`、`rows` 和 `totals`。摘要字段为 `row_count` 和 `missing_count`。交班件可以在没有 SQLite 归档的终端解析。

## 顺序、精度与错误

行号从零起算。`Copy(source, gap)` 和 `Move(source, gap)` 的第二个参数是该步起始列表的插入缝，取值从 0 到该步行数。`Delete(position)` 的位置也相对于该步开始时的列表。举例，从 `[A,B,C,D]` 复制 B 到末尾，再以 `Move(0, 3)` 移动 A，得到 `[B,C,A,D,B′]`。移动保留原出现，副本有自己的出现，删除仅移除被指定的出现。空批及空日表可存档，空日表不能登记选区，空编辑序列会冻结父版原序的后继。

读值沿用仪器整数刻度，SQLite 中保存精确整数文本。`None` 对应 JSON 的 `null`。零和负整数均为有效读数。对超过 Python 默认十进制转换长度的读值，可用 `json.loads(payload, parse_int=decimal.Decimal)` 在 Python 中精确读取交班件。明细按目标行位置排列，可非连续或为空。

参数形式、坐标、区间、批冲突和关系错误引发 `ValueError`。查找未知的有效编号或批号引发 `LookupError`。整数标记和修订编号须是 SQLite 正整数范围内的 `int`。SQLite 或提交前钩子引发的异常向调用方传播。编辑及其完整行序一起提交，失败调用无可见后继。非法领取直接抛出异常。修订与标记编号只在成功后交给调用方。

## 回归

`tests/test_intake.py` 核对原序、来源、重试和重复初始化。`tests/test_revision.py` 核对编辑与标记坐标以及提交失败后的恢复。`tests/test_review.py` 核对固定选择、同源行的独立存续和目标顺序。`tests/test_delivery.py` 从实际明细独立复算交班摘要，核对固定目标、坐标、空结果和精确读值。
