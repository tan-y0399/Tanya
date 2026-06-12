import { ref, onMounted, watch, type Ref } from 'vue'

export type PlanRevealSection =
  | 'head'
  | 'meta'
  | 'phenomenon'
  | 'analysis'
  | 'causes'
  | 'rag'
  | 'env'
  | 'steps'
  | 'note'
  | 'actions'

/** 诊断方案区块依次显现（流动式展示） */
export function usePlanStreamReveal(
  enabled: Ref<boolean>,
  hasActions: Ref<boolean>,
) {
  const allKeys: PlanRevealSection[] = [
    'head', 'meta', 'phenomenon', 'analysis', 'causes', 'rag', 'env', 'steps', 'note', 'actions',
  ]

  const visible = ref<Record<PlanRevealSection, boolean>>({
    head: false,
    meta: false,
    phenomenon: false,
    analysis: false,
    causes: false,
    rag: false,
    env: false,
    steps: false,
    note: false,
    actions: false,
  })

  function revealAll() {
    allKeys.forEach(k => { visible.value[k] = true })
  }

  async function runSequence() {
    const delay = (ms: number) => new Promise(r => setTimeout(r, ms))
    const seq: [PlanRevealSection, number][] = [
      ['head', 80],
      ['meta', 100],
      ['phenomenon', 160],
      ['analysis', 180],
      ['causes', 200],
      ['rag', 160],
      ['env', 140],
      ['steps', 220],
      ['note', 160],
      ['actions', 140],
    ]
    for (const [key, ms] of seq) {
      if (key === 'actions' && !hasActions.value) continue
      visible.value[key] = true
      await delay(ms)
    }
  }

  onMounted(() => {
    if (!enabled.value) {
      revealAll()
      return
    }
    void runSequence()
  })

  watch(enabled, (v) => {
    if (!v) revealAll()
  })

  return { visible, revealAll }
}
