<script setup lang="ts">
/**
 * Pose training history table.
 *
 * Used by both the training entry page and the movement training page. The two
 * copies had identical columns and empty text and differed only in how the
 * exercise column was rendered, so that difference is the one prop.
 *
 * The provenance column goes through the shared, context-aware label helper: the
 * previous local copies rendered the piano wording ("真人键盘输入") against rows
 * that were recorded on a camera.
 */
import { presentationFor } from '@/pose/exercises'
import type { PoseSession } from '@/types'
import { isHumanSource, nonHumanSourceLabel } from '@/utils/source'
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
  { exerciseDisplay: 'name', emptyText: '暂无动作训练记录' },
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
    <el-table-column label="来源" width="160">
      <template #default="{ row }">
        <el-tag
          v-if="!isHumanSource(row.input_source)"
          type="warning"
          size="small"
        >
          {{ nonHumanSourceLabel(row.input_source, 'pose') }}
        </el-tag>
        <span v-else class="pd-muted">真人录制</span>
      </template>
    </el-table-column>
  </el-table>
</template>
