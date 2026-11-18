# 复核交班同源行错领：根因与核验说明

## 根因

修复前 `revision_rows` 只保存 `(revision_id, position, batch_id, source_position)`，
即行的身份仅由来源批号与源位决定。`Copy` 虽在内存中新建了 `Occurrence`，
但冻结到 SQLite 后，原行与副本的列完全相同，重开归档后无法区分。
`review/projection.py` 又按 `(batch_id, source_position)` 把标记选区与目标行做匹配：

- 删除同源行中的任一条，会让所有指向该来源的旧标记一起失效或一起误领；
- 因而 `INCIDENT.md` 中删除原行与删除副本两个目标修订里，三张标记都领到同一条缺测行。

移动、删除、空编辑本身的行序计算是正确的，缺陷只在“出现（occurrence）”缺少持久身份。

## 修复

只改日表勘误到复核交班链路，公开接口、JSON 格式、坐标语义和异常约定均不变：

1. 新增 `occurrence_registry` 表发放全局正整数出现号；`revision_rows` 增加
   `occurrence_id` 列，并对同一修订内的出现号加唯一约束。
2. `seal_day` 为每个初始行发放出现号；`Move` 沿用原出现号；`Copy` 发放新出现号，
   副本因此可独立编辑、独立标记；`Delete` 只结束被删出现号的延续。
3. 标记仍只记录修订号与原区间（旧日表与标记不可变）；领取时把选区绑定到
   标记修订各行的出现号，仅在目标修订中匹配仍存续的同一出现号，按目标行序交付，
   保留原位、现位、来源与读值，结果可非连续或为空。
4. 旧格式归档在 `open_archive` 时自动迁移：为已冻结的每条出现补登互不相同的
   出现号，使历史副本重开后同样独立；非法编辑或提交钩子失败仍整体回滚，
   不产生新修订，也不残留出现号。

## 回归

新增 `tests/test_occurrences.py`，覆盖：成对撤回事故、离线交班件与领取明细
及摘要复算、移动保身份而副本独立、副本再复制的多次独立撤回、空编辑链上的
身份延续与删空、旧格式归档迁移及迁移后的继续编辑。

## 实际核验（项目根目录，Python 3.11）

```sh
python3 -B verify.py     # 22 个用例全部通过（原 16 个全部保留并通过，新增 6 个）
python3 -B incident.py   # 退出 0，actual 与 expected 完全一致，不再输出 OBS_LAKE_REVIEW_OCCURRENCE_MISMATCH
python3 -B demo.py       # 退出 0，四个固定请求的领取与交班件与手算一致
```
