export const RECIPE_METRIC_ROWS: Record<string, Array<{ key: string; label: string; kind: 'ms' | 'ratio' | 'number' }>> = {
  TEMPO_RAMP: [0,1,2,3].flatMap(segment=>[
    {key:`tempo_segment_${segment}_accuracy`,label:`第 ${segment+1} 段准确率`,kind:'ratio' as const},
    {key:`tempo_segment_${segment}_mae_ms`,label:`第 ${segment+1} 段节拍绝对误差`,kind:'ms' as const},
  ]),
  HOLD_RELEASE: [{key:'hold_duration_mae_ms',label:'持续时间绝对误差',kind:'ms'}, {key:'hold_release_completion_rate',label:'释放完成率',kind:'ratio'}],
  BIMANUAL_OFFSET: [{key:'inter_hand_phase_mae_ms',label:'双手相位绝对误差',kind:'ms'}, {key:'offset_left_miss_rate',label:'左手漏击率',kind:'ratio'}, {key:'offset_right_miss_rate',label:'右手漏击率',kind:'ratio'}],
  REVERSE_SEQUENCE: [{key:'reverse_position_accuracy',label:'逆序位置准确率',kind:'ratio'}, {key:'reverse_completion_rate',label:'逆序完成率',kind:'ratio'}],
  GO_NO_GO: [{key:'go_commission_count',label:'等待提示误按次数',kind:'number'}, {key:'go_omission_count',label:'按键提示漏按次数',kind:'number'}, {key:'go_response_latency_ms',label:'按键反应延迟',kind:'ms'}],

  CFT_RHYTHM_HOLD: [
    { key: 'cued_phase_accuracy', label: '有提示阶段准确率', kind: 'ratio' },
    { key: 'free_phase_accuracy', label: '撤提示后准确率', kind: 'ratio' },
    { key: 'free_phase_timing_mae_ms', label: '撤提示后节拍误差（平均绝对值）', kind: 'ms' },
    { key: 'free_phase_interval_cv', label: '撤提示后间隔变异系数', kind: 'number' },
  ],
  BIMANUAL_SYNC: [
    { key: 'inter_hand_sync_mean_ms', label: '双手同步误差（平均）', kind: 'ms' },
    { key: 'inter_hand_sync_sd_ms', label: '双手同步误差（标准差）', kind: 'ms' },
  ],
  ACCENT_GROUPING: [{ key: 'accent_hit_rate', label: '强拍命中率', kind: 'ratio' }],
}

