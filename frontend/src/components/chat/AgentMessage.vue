<template>
  <div class="agent-msg" :class="{ 'agent-msg--continuation': continuation }">
    <div v-if="!continuation" class="msg-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="5" stroke="#2563eb" stroke-width="1.5"/>
        <circle cx="9" cy="10" r="2" stroke="#2563eb" stroke-width="1.2"/>
        <circle cx="15" cy="10" r="2" stroke="#2563eb" stroke-width="1.2"/>
        <path d="M8 16c2 2 6 2 8 0" stroke="#2563eb" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="msg-body">
      <div v-if="!continuation" class="msg-meta">
        <span class="msg-role">KylinOps Agent</span>
        <span v-if="maxRiskLevel && maxRiskLevel !== 'L1'" class="risk-badge" :class="'risk-' + maxRiskLevel.toLowerCase()">{{ maxRiskLevel }}</span>
        <span class="msg-time">{{ formattedTime }}</span>
      </div>
      <div
        v-if="content?.trim()"
        class="msg-content"
        :class="{ 'is-streaming': streaming }"
        v-html="renderedContent"
        @click="handleContentClick"
        @error.capture="handleContentImageError"
      ></div>
      <div v-if="media?.length" class="answer-media" aria-live="polite">
        <figure v-for="item in media" :key="item.id" class="answer-media-item" :class="`media-${item.status}`">
          <div v-if="item.status === 'pending'" class="media-skeleton">
            <Loading class="spin" />
            <span>{{ item.kind === 'diagram' ? '流程图生成中' : '图片准备中' }}</span>
          </div>
          <button
            v-else-if="item.status === 'ready' && item.url && !brokenMediaIds.has(item.id)"
            type="button"
            class="media-preview-button"
            :title="`打开查看：${item.title}`"
            @click="openPreview(item.url)"
          >
            <img :src="item.url" :alt="item.alt || item.title" loading="lazy" @error="markMediaBroken(item.id)" />
            <span class="media-zoom-hint"><ZoomIn /> 点击查看大图</span>
          </button>
          <div v-else class="media-failed-summary">
            <PictureFilled />
            <span>{{ item.fallback || '图片暂时无法展示，正文内容不受影响。' }}</span>
          </div>
          <figcaption>
            <strong>{{ item.title }}</strong>
            <span v-if="item.caption">{{ item.caption }}</span>
          </figcaption>
        </figure>
      </div>
      <div v-if="content?.trim()" class="msg-actions">
        <button type="button" class="msg-action-btn" title="复制回答" @click="$emit('copy', content)">
          <CopyDocument />
          <span>复制</span>
        </button>
        <button type="button" class="msg-action-btn" title="重新生成" @click="$emit('regenerate')">
          <RefreshRight />
          <span>重新生成</span>
        </button>
        <button
          type="button"
          class="msg-action-btn voice-btn"
          :class="'voice-' + speechState"
          :title="speechButtonTitle"
          :disabled="speechState === 'generating'"
          @click="$emit('speak', content)"
        >
          <Loading v-if="speechState === 'generating'" class="spin" />
          <VideoPause v-else-if="speechState === 'playing'" class="pulse" />
          <VideoPlay v-else-if="speechState === 'paused'" />
          <Headset v-else />
          <span>{{ speechLabel }}</span>
        </button>
        <span v-if="speechError" class="speech-error" role="status">{{ speechError }}</span>
      </div>
      <div class="msg-trace" v-if="traceId && !hideTrace" @click="$emit('viewTrace', traceId)">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1"/>
          <path d="M6 3v3l2 2" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        </svg>
        <span>推理链路 · {{ shortTraceId }}</span>
      </div>
    </div>
    <ElImageViewer
      v-if="previewSrc"
      :url-list="[previewSrc]"
      :initial-index="0"
      hide-on-click-modal
      @close="previewSrc = ''"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElImageViewer } from 'element-plus'
import { CopyDocument, Headset, Loading, PictureFilled, RefreshRight, VideoPause, VideoPlay, ZoomIn } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { formatTime } from '@/utils'
import type { AnswerMedia } from '@/stores/chat'

const props = withDefaults(defineProps<{
  content: string
  traceId?: string
  createdAt: string
  maxRiskLevel?: string
  /** 续接正文：不重复头像与元信息，与首段左对齐 */
  continuation?: boolean
  /** 正文在下方单独展示时，头部不重复显示推理链路 */
  hideTrace?: boolean
  speechState?: 'idle' | 'generating' | 'playing' | 'paused'
  speechError?: string
  media?: AnswerMedia[]
  streaming?: boolean
}>(), {
  speechState: 'idle',
})

defineEmits<{
  viewTrace: [traceId: string]
  copy: [content: string]
  regenerate: []
  speak: [content: string]
  stopSpeak: []
}>()

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
  html: false,
  typographer: true,
})

function enhanceRenderedHtml(html: string): string {
  return html.replace(/<img /g, '<img loading="lazy" data-answer-image="true" ')
}

function stripDiagramSourceBlocks(text: string): string {
  if (!text) return text
  const mermaidBlocks: string[] = []
  const protectedText = text.replace(/```mermaid\s*[\s\S]*?```/gi, (block) => {
    const token = `@@KYLIN_MERMAID_FALLBACK_${mermaidBlocks.length}@@`
    mermaidBlocks.push(block)
    return token
  })
  const cleaned = protectedText
    .replace(/(?:^|\n)(?:#{2,4}\s*)?(?:解决流程图|处理流程图|流程图)\s*\n+\s*(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?=\n#{2,4}\s|\n(?:详细步骤|处理建议|总结|风险提示|参考来源)\b|$)/gi, '\n')
    .replace(/(?:^|\n)\s*(?:graph|flowchart)\s+(?:TD|LR|BT|RL)[\s\S]*?(?=\n#{2,4}\s|\n(?:详细步骤|处理建议|总结|风险提示|参考来源)\b|$)/gi, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  return mermaidBlocks.reduce(
    (result, block, index) => result.replace(`@@KYLIN_MERMAID_FALLBACK_${index}@@`, block),
    cleaned,
  )
}

function normalizeImageMarkdownUrls(text: string): string {
  if (!text) return text
  return text.replace(/!\[([^\]]*)\]\(([^)\n]+)\)/g, (_match, alt: string, rawUrl: string) => {
    const url = String(rawUrl || '').trim()
    if (!/^https?:\/\//i.test(url) && !url.startsWith('/api/') && !url.startsWith('data:image/')) {
      return `![${alt}](${url})`
    }
    try {
      return `![${alt}](${encodeURI(url).replace(/\(/g, '%28').replace(/\)/g, '%29')})`
    } catch {
      return `![${alt}](${url.replace(/\s+/g, '%20')})`
    }
  })
}

const renderedContent = computed(() => {
  const cleaned = stripDiagramSourceBlocks(props.content)
  return enhanceRenderedHtml(md.render(normalizeImageMarkdownUrls(cleaned)))
})
const formattedTime = computed(() => formatTime(props.createdAt))
const shortTraceId = computed(() => props.traceId ? props.traceId.slice(0, 28) + '...' : '')
const previewSrc = ref('')
const brokenMediaIds = ref(new Set<string>())

function openPreview(src: string) {
  previewSrc.value = src
}

function handleContentClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (target instanceof HTMLImageElement && target.src) openPreview(target.currentSrc || target.src)
}

function handleContentImageError(event: Event) {
  const image = event.target as HTMLImageElement | null
  if (!image || image.classList.contains('img-broken')) return
  image.classList.add('img-broken')
  const fallback = document.createElement('span')
  fallback.className = 'img-fallback'
  fallback.textContent = '图片暂时不可访问，已保留文字说明。'
  image.insertAdjacentElement('afterend', fallback)
}

function markMediaBroken(id: string) {
  brokenMediaIds.value = new Set([...brokenMediaIds.value, id])
}

const speechLabel = computed(() => {
  if (props.speechState === 'generating') return '生成中'
  if (props.speechState === 'playing') return '暂停播放'
  if (props.speechState === 'paused') return '继续播放'
  return '语音播报'
})
const speechButtonTitle = computed(() => {
  if (props.speechState === 'generating') return '正在准备语音'
  if (props.speechState === 'playing') return '暂停播放'
  if (props.speechState === 'paused') return '继续播放'
  return '语音播报'
})
</script>

<style lang="scss" scoped>
.agent-msg {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  animation: fadeIn 0.25s ease;

  &--continuation {
    padding-top: 0;
    margin-left: 46px;
  }
}

.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg-body {
  flex: 1;
  min-width: 0;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  .msg-role {
    font-size: 12px;
    font-weight: 600;
    color: #2563eb;
  }
  .msg-time {
    font-size: 11px;
    color: #94a3b8;
  }
}

.msg-content {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.75;

  &.is-streaming::after {
    content: '';
    display: inline-block;
    width: 2px;
    height: 1.05em;
    margin-left: 3px;
    vertical-align: -0.15em;
    border-radius: 1px;
    background: #2563eb;
    animation: cursorBlink 0.9s steps(1) infinite;
  }

  // 段落
  :deep(p) { margin: 8px 0; }

  // 行内代码
  :deep(code) {
    font-family: 'JetBrains Mono', Consolas, monospace;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    color: #2563eb;
  }

  // 代码块
  :deep(pre) {
    font-family: 'JetBrains Mono', Consolas, monospace;
    background: #1e293b;
    color: #e2e8f0;
    padding: 14px 18px;
    border-radius: 10px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 1.6;
    margin: 12px 0;
    code { background: none; padding: 0; color: inherit; font-size: inherit; }
  }

  // 标题
  :deep(h1) { font-size: 19px; font-weight: 700; color: #0f172a; margin: 20px 0 10px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; }
  :deep(h2) { font-size: 17px; font-weight: 700; color: #1e293b; margin: 18px 0 8px; }
  :deep(h3) { font-size: 15px; font-weight: 600; color: #334155; margin: 14px 0 6px; }
  :deep(h4) { font-size: 14px; font-weight: 600; color: #475569; margin: 10px 0 4px; }

  // 粗体高亮
  :deep(strong) {
    color: #0f172a;
    font-weight: 700;
  }

  // 表格
  :deep(table) {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    margin: 12px 0;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;

    thead th {
      background: #f1f5f9;
      color: #475569;
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 10px 14px;
      text-align: left;
      border-bottom: 2px solid #e2e8f0;
    }

    tbody {
      tr {
        transition: background 0.1s;
        &:nth-child(even) { background: #f8fafc; }
        &:hover { background: #eff6ff; }
      }
      td {
        padding: 9px 14px;
        font-size: 13px;
        color: #334155;
        border-bottom: 1px solid #f1f5f9;
        vertical-align: middle;
        code { font-size: 12px; }
      }
    }
  }

  // 列表
  :deep(ul), :deep(ol) {
    padding-left: 20px;
    margin: 8px 0;
    li {
      margin: 4px 0;
      padding-left: 4px;
      &::marker { color: #2563eb; }
    }
  }

  // 引用
  :deep(blockquote) {
    border-left: 3px solid #2563eb;
    margin: 10px 0;
    padding: 8px 16px;
    background: #f8fafc;
    border-radius: 0 8px 8px 0;
    color: #64748b;
    font-size: 13px;
    p { margin: 4px 0; }
  }

  // 水平线
  :deep(hr) {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 16px 0;
  }

  // 链接
  :deep(a) {
    color: #2563eb;
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }

  :deep(img) {
    display: block;
    max-width: min(100%, 860px);
    max-height: 520px;
    object-fit: contain;
    margin: 12px 0 6px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #f8fafc;
    box-shadow: 0 1px 6px rgba(15, 23, 42, 0.08);
    cursor: zoom-in;
    transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;

    &:hover {
      border-color: #93c5fd;
      box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
      transform: translateY(-1px);
    }
  }

  :deep(img.img-broken) {
    display: none;
  }

  :deep(.img-fallback) {
    display: inline-flex;
    align-items: center;
    margin: 8px 0;
    padding: 8px 12px;
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
    background: #f8fafc;
    color: #64748b;
    font-size: 13px;
  }
}

.answer-media {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: 14px;
  margin: 18px 0 8px;
}

.answer-media-item {
  min-width: 0;
  margin: 0;

  &.media-pending,
  &:has(.media-failed-summary) {
    grid-column: 1 / -1;
  }

  figcaption {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding-top: 7px;
    color: #64748b;
    font-size: 12px;
    line-height: 1.5;

    strong {
      color: #334155;
      font-size: 13px;
    }
  }
}

.media-preview-button {
  position: relative;
  display: block;
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #f8fafc;
  cursor: zoom-in;

  img {
    display: block;
    width: 100%;
    max-height: 520px;
    aspect-ratio: 16 / 10;
    object-fit: contain;
    background: #f8fafc;
  }

  &:hover .media-zoom-hint,
  &:focus-visible .media-zoom-hint {
    opacity: 1;
    transform: translateY(0);
  }
}

.media-zoom-hint {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.82);
  color: #fff;
  font-size: 11px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.16s ease, transform 0.16s ease;

  svg { width: 14px; height: 14px; }
}

.media-skeleton {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  width: 100%;
  min-height: 180px;
  aspect-ratio: 16 / 6;
  border: 1px dashed #bfdbfe;
  border-radius: 8px;
  background: linear-gradient(90deg, #f8fafc 25%, #eff6ff 50%, #f8fafc 75%);
  background-size: 220% 100%;
  color: #2563eb;
  font-size: 13px;
  animation: mediaShimmer 1.6s ease-in-out infinite;

  svg { width: 18px; height: 18px; }
}

.media-failed-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;

  svg { width: 16px; height: 16px; flex: 0 0 16px; }
}

.msg-trace {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    color: #2563eb;
    border-color: #bfdbfe;
    background: #eff6ff;
  }
}

.msg-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;

  .msg-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 32px;
    border: 1px solid #dbe3ef;
    background: linear-gradient(180deg, #fff 0%, #f8fafc 100%);
    color: #475569;
    border-radius: 7px;
    padding: 6px 11px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: border-color 0.16s ease, color 0.16s ease, background 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;

    svg {
      width: 15px;
      height: 15px;
      flex: 0 0 15px;
    }

    &:hover {
      border-color: #93c5fd;
      color: #2563eb;
      background: #eff6ff;
      transform: translateY(-1px);
      box-shadow: 0 5px 14px rgba(37, 99, 235, 0.12);
    }

    &:active {
      transform: translateY(0);
      box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }
  }

  .voice-btn {
    &.voice-generating {
      color: #7c3aed;
      border-color: #ddd6fe;
      background: #f5f3ff;
    }

    &.voice-playing {
      color: #047857;
      border-color: #a7f3d0;
      background: #ecfdf5;
    }

    &.voice-paused {
      color: #b45309;
      border-color: #fde68a;
      background: #fffbeb;
    }

    &:disabled {
      cursor: wait;
      transform: none;
      opacity: 0.78;
    }

    .spin {
      animation: spin 0.85s linear infinite;
    }

    .pulse {
      animation: voicePulse 1.1s ease-in-out infinite;
    }
  }

  .speech-error {
    align-self: center;
    color: #b91c1c;
    font-size: 12px;
    line-height: 1.4;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes voicePulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.12); opacity: 1; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes mediaShimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

@keyframes cursorBlink {
  0%, 48% { opacity: 1; }
  49%, 100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .agent-msg,
  .spin,
  .pulse,
  .media-skeleton {
    animation: none !important;
  }

  .msg-action-btn,
  .msg-content :deep(img) {
    transition: none !important;
  }
}

.risk-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  margin-left: 6px;

  &.risk-l1 { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
  &.risk-l2 { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
  &.risk-l3 { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  &.risk-l4 { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; }
  &.risk-l5 { background: #fef2f2; color: #7f1d1d; border: 1px solid #fca5a5; }
}
</style>
