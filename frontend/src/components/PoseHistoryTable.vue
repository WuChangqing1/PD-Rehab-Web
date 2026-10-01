<script setup lang="ts">
/**
 * Ballet training history table.
 *
 * Used by the movement training page. The exercise column takes its name from
 * the loaded definitions so a retired exercise key still renders a readable
 * label rather than a raw enum value.
 *
 * There is no provenance column. It used to name the source of every row
 * ("真人录制" / "脚本自检录制"), which is a note about how the software classifies
 * its own records and not something a doctor reading a history table acts on.
 * The classification still happens: non-measurement rows are excluded from the
 * trends by `followup/trends.ts`.
 */
import { presentationFor } from '@/pose/exercises'
import type { PoseSession } from '@/types'
import { NO_DATA, formatDateTime, formatNumber, formatPercent } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    sessions: PoseSession[]
    /** Exercise names come from the loaded definitions; fall back to the key. */
    nameFor?: (key: string) => string | undefined
    /** `name` shows the Chinese exercise name, `area` shows "部位 · 动作键". */
    exerciseDisplay?: 'name' | 'area'
    emptyText?: string
  }>(),
  { exerciseDisplay: 'name', emptyText: '暂无芭蕾动作训练记录' },
)

function exerciseCell(session: PoseSession): string {
  if (props.exerciseDisplay === 'area') {
    const area = presentationFor(session.exercise_type).area
    return `${area} · ${session.exercise_type.replace(/_/g, ' ').toLowerCase()}`
  }
  return props.nameFor?.(session.exercise_type) ?? session.exercise_type
}
</script>

<template>
  <el-table :data="sessions" size="small" :empty-text="emptyText">
    <el-table-column label="动作" min-width="160">
      <template #default="{ row }">{{ exerciseCell(row) }}</template>
    </el-table-column>
    <el-table-column label="完成次数" width="100" align="right">
      <template #default="{ row }">{{ row.repetition_count ?? NO_DATA }}</template>
    </el-table-column>
    <el-table-column label="保持时间" width="110" align="right">
      <template #default="{ row }">
        {{ row.hold_time_sec === null ? NO_DATA : `${formatNumber(row.hold_time_sec, 2)} s` }}
      </template>
    </el-table-column>
    <el-table-column label="有效帧比例" width="120" align="right">
      <template #default="{ row }">
        {{
          row.valid_pose_frame_ratio === null
            ? NO_DATA
            : formatPercent(row.valid_pose_frame_ratio)
        }}
      </template>
    </el-table-column>
    <el-table-column label="开始时间" width="170">
      <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="110">
      <template #default="{ row }">
        <el-tag v-if="row.completed_at" type="success" size="small">已通过</el-tag>
        <el-tag v-else type="info" size="small">未通过 / 未分析</el-tag>
      </template>
    </el-table-column>
  </el-table>
</template>
