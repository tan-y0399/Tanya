<template>
  <div class="knowledge-layout">
    <!-- 移动端分类抽屉按钮 -->
    <button class="mobile-cat-toggle" @click="showMobileSidebar = !showMobileSidebar">
      <span>{{ activeCategory ? activeCategory.replace('常见-','') : '全部分类' }}</span>
      <svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
    </button>

    <!-- 遮罩 -->
    <div class="sidebar-overlay" v-if="showMobileSidebar" @click="showMobileSidebar = false" />

    <!-- ===== 左侧分类边栏 ===== -->
    <aside class="knowledge-sidebar" :class="{ 'mobile-open': showMobileSidebar }">
      <div class="sidebar-header">
        <h3 class="sidebar-title">知识分类</h3>
        <span class="sidebar-total">共 {{ totalArticles }} 篇</span>
      </div>

      <!-- 最近浏览 -->
      <div class="recent-section" v-if="recentArticles.length">
        <div class="recent-title">最近浏览</div>
        <button
          v-for="ra in recentArticles"
          :key="ra.id"
          class="recent-item"
          @click="openArticle(ra); showMobileSidebar = false"
        >
          <span class="recent-dot" />
          <span class="recent-label">{{ ra.title }}</span>
        </button>
      </div>

      <nav class="category-nav">
        <button
          class="cat-item"
          :class="{ active: !activeCategory }"
          @click="activeCategory = ''; page = 1; search(); showMobileSidebar = false"
        >
          <span class="cat-icon">📚</span>
          <span class="cat-label">全部文章</span>
          <span class="cat-badge">{{ totalArticles }}</span>
        </button>
      </nav>

      <!-- 运维知识库分组（可折叠） -->
      <div class="cat-group" v-if="opsCategories.length">
        <button class="cat-group-title" @click="opsCollapsed = !opsCollapsed">
          <svg :class="{ rotated: !opsCollapsed }" class="collapse-arrow" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" fill="none"/>
          </svg>
          运维知识库
          <span class="group-count">{{ opsCategories.reduce((s,c) => s + c.count, 0) }}</span>
        </button>
        <nav class="category-nav" v-show="!opsCollapsed">
          <button
            v-for="c in opsCategories"
            :key="c.name"
            class="cat-item"
            :class="{ active: activeCategory === c.name }"
            @click="activeCategory = c.name; page = 1; search(); showMobileSidebar = false"
          >
            <span class="cat-icon">{{ categoryIcon(c.name) }}</span>
            <span class="cat-label">{{ c.name }}</span>
            <span class="cat-badge">{{ c.count }}</span>
          </button>
        </nav>
      </div>

      <!-- 常见问题FAQ分组（可折叠） -->
      <div class="cat-group" v-if="faqCategories.length">
        <button class="cat-group-title" @click="faqCollapsed = !faqCollapsed">
          <svg :class="{ rotated: !faqCollapsed }" class="collapse-arrow" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" fill="none"/>
          </svg>
          常见问题FAQ
          <span class="group-count">{{ faqCategories.reduce((s,c) => s + c.count, 0) }}</span>
        </button>
        <nav class="category-nav" v-show="!faqCollapsed">
          <button
            v-for="c in faqCategories"
            :key="c.name"
            class="cat-item"
            :class="{ active: activeCategory === c.name }"
            @click="activeCategory = c.name; page = 1; search(); showMobileSidebar = false"
          >
            <span class="cat-icon">{{ categoryIcon(c.name) }}</span>
            <span class="cat-label">{{ c.label }}</span>
            <span class="cat-badge">{{ c.count }}</span>
          </button>
        </nav>
      </div>
    </aside>

    <!-- ===== 右侧主内容 ===== -->
    <main class="knowledge-main">
      <!-- 搜索栏 -->
      <div class="search-row">
        <div class="search-box">
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="#94a3b8" stroke-width="1.5"/>
            <path d="M11 11l4 4" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <input
            v-model="keyword"
            class="search-input"
            placeholder="搜索知识库标题、内容、标签..."
            @input="onSearchInput"
            @keyup.enter="page = 1; search()"
          />
          <span v-if="searching" class="search-spinner" />
          <button v-if="keyword" class="search-clear" @click="keyword = ''; page = 1; search()">&times;</button>
        </div>
        <button v-if="isAdmin" class="reset-btn" @click="resetKnowledge" :disabled="resetting">
          {{ resetting ? '导入中...' : '重置知识库' }}
        </button>
      </div>

      <!-- 搜索建议下拉 -->
      <div class="search-suggestions" v-if="searchSuggestions.length && keyword && !searching">
        <button
          v-for="s in searchSuggestions"
          :key="s"
          class="suggestion-item"
          @click="keyword = s; page = 1; search()"
        >{{ s }}</button>
      </div>

      <!-- 排序与筛选工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <!-- 排序 -->
          <div class="sort-group">
            <button
              v-for="opt in sortOptions"
              :key="opt.value"
              class="sort-btn"
              :class="{ active: sortBy === opt.value }"
              @click="sortBy = opt.value; page = 1; search()"
            >{{ opt.label }}</button>
          </div>
          <!-- 结果统计 -->
          <span class="result-hint" v-if="activeCategory || keyword || activeTags.length">
            找到 {{ totalArticles }} 篇
          </span>
        </div>
      </div>

      <!-- 热门标签云 + 已选滤镜 -->
      <div class="tag-toolbar" v-if="hotTags.length">
        <span class="tag-label">热门标签：</span>
        <button
          v-for="t in hotTags"
          :key="t"
          class="hot-tag"
          :class="{ selected: activeTags.includes(t) }"
          @click="toggleTag(t)"
        >{{ t }}</button>
      </div>
      <div class="filter-chips" v-if="activeTags.length">
        <span class="chip" v-for="t in activeTags" :key="t">
          {{ t }}
          <button class="chip-remove" @click="toggleTag(t)">&times;</button>
        </span>
        <button class="chip-clear" @click="activeTags = []; page = 1; search()">清空筛选</button>
      </div>

      <!-- 骨架屏 -->
      <div class="article-grid" v-if="listLoading">
        <div class="article-card skeleton" v-for="n in 6" :key="'sk-'+n">
          <div class="sk-line sk-title" />
          <div class="sk-line sk-text" />
          <div class="sk-line sk-text short" />
          <div class="sk-line sk-tags" />
        </div>
      </div>

      <!-- 文章列表 (带过渡动画) -->
      <TransitionGroup name="card-list" tag="div" class="article-grid" v-else-if="articles.length">
        <div
          class="article-card"
          v-for="a in sortedArticles"
          :key="a.id"
          @click="openArticle(a)"
        >
          <div class="card-top">
            <span class="severity-badge" :class="`sev-${a.severity}`">
              {{ severityLabel(a.severity) }}
            </span>
            <span class="card-category">{{ a.category }}</span>
            <span class="new-badge" v-if="isNewArticle(a)">NEW</span>
          </div>
          <h4 class="card-title" v-html="highlightText(a.title, keyword)" />
          <p class="card-excerpt" v-html="highlightText(getExcerpt(a), keyword)" />
          <div class="card-tags" v-if="a.tags.length">
            <span class="tag" v-for="t in a.tags.slice(0, 4)" :key="t" v-html="highlightText(t, keyword)" />
          </div>
          <div class="card-meta">
            <span>{{ a.viewCount }} 次查看</span>
            <span>{{ formatTime(a.updatedAt) }}</span>
          </div>
        </div>
      </TransitionGroup>

      <!-- 空状态 -->
      <div class="empty" v-else-if="!listLoading">
        <!-- 搜索无匹配 -->
        <template v-if="keyword || activeTags.length">
          <div class="empty-icon">🔍</div>
          <p>未找到包含「{{ keyword }}」的文章</p>
          <p class="empty-hint">请尝试更换关键词或清除筛选条件</p>
          <div class="empty-actions">
            <button class="empty-btn" @click="keyword = ''; activeTags = []; page = 1; search()">清除搜索条件</button>
          </div>
          <div class="hot-suggest" v-if="topViewed.length">
            <p class="hot-suggest-title">热门文章推荐</p>
            <button v-for="a in topViewed" :key="a.id" class="hot-suggest-item" @click="openArticle(a)">
              {{ a.title }}
            </button>
          </div>
        </template>
        <!-- 分类为空 -->
        <template v-else-if="activeCategory">
          <div class="empty-icon">📂</div>
          <p>「{{ activeCategory }}」分类暂无文章</p>
          <button class="empty-btn" @click="activeCategory = ''; search()">查看全部文章</button>
        </template>
        <!-- 首次进入无数据 -->
        <template v-else>
          <div class="empty-icon">📖</div>
          <p>知识库尚未导入</p>
          <p class="empty-hint">请管理员点击右上角「重置知识库」按钮导入数据</p>
          <div class="empty-steps">
            <div class="step"><span class="step-num">1</span> 准备知识库 Markdown 文件</div>
            <div class="step"><span class="step-num">2</span> 点击「重置知识库」导入</div>
            <div class="step"><span class="step-num">3</span> 开始智能搜索与浏览</div>
          </div>
        </template>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="totalPages > 1 && !listLoading">
        <div class="page-numbers">
          <button class="page-btn nav" :disabled="page <= 1" @click="page--; search()">«</button>
          <button
            v-for="p in visiblePages"
            :key="p"
            class="page-btn"
            :class="{ current: p === page, ellipsis: p === '...' }"
            :disabled="p === '...'"
            @click="goToPage(p)"
          >{{ p }}</button>
          <button class="page-btn nav" :disabled="page >= totalPages" @click="page++; search()">»</button>
        </div>
        <span class="page-stat">{{ pageRangeText }}</span>
      </div>
    </main>

    <!-- ===== 详情弹窗 ===== -->
    <teleport to="body">
      <div class="modal-overlay" v-if="currentArticle" @click.self="closeModal">
        <div class="modal-card" @click.stop>
          <button class="modal-close" @click="closeModal">&times;</button>

          <!-- 面包屑 -->
          <div class="modal-breadcrumb">
            <span class="crumb" @click="closeModal">全部</span>
            <span class="crumb-sep">›</span>
            <span class="crumb">{{ currentArticle.category }}</span>
            <span class="crumb-sep">›</span>
            <span class="crumb active">{{ currentArticle.title }}</span>
          </div>

          <div class="modal-layout">
            <!-- 正文区域 -->
            <div class="modal-body" ref="modalBodyRef">
              <div class="modal-header">
                <span class="severity-badge" :class="`sev-${currentArticle.severity}`">
                  {{ severityLabel(currentArticle.severity) }}
                </span>
                <span class="card-category">{{ currentArticle.category }}</span>
              </div>
              <h2 class="modal-title">{{ currentArticle.title }}</h2>
              <div class="card-tags" v-if="currentArticle.tags.length">
                <span class="tag" v-for="t in currentArticle.tags" :key="t">{{ t }}</span>
              </div>

              <!-- 操作按钮行 -->
              <div class="modal-actions">
                <button class="act-btn" @click="copyContent">
                  <svg width="14" height="14" viewBox="0 0 16 16"><rect x="5" y="1" width="9" height="13" rx="1.5" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M2 4h-.5A1.5 1.5 0 000 5.5v9A1.5 1.5 0 001.5 16h7a1.5 1.5 0 001.5-1.5V14" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
                  {{ copied ? '已复制' : '复制全文' }}
                </button>
                <button class="act-btn" @click="toggleFavorite(currentArticle)">
                  <svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 1.5l1.8 4.8 5.2.4-4 3.5 1.3 5-4.3-3-4.3 3 1.3-5-4-3.5 5.2-.4L8 1.5z" :fill="isFavorited(currentArticle.id) ? '#f59e0b' : 'none'" stroke="currentColor" stroke-width="1"/></svg>
                  {{ isFavorited(currentArticle.id) ? '已收藏' : '收藏' }}
                </button>
                <button class="act-btn" @click="feedbackArticle('useful')">
                  <svg width="14" height="14" viewBox="0 0 16 16"><path d="M5 6h-.5C3.6 6 3 6.6 3 7.5v5c0 .9.6 1.5 1.5 1.5H5m0-7v7m0-7l2.5-3.5c.3-.4.8-.5 1.2-.3.4.2.5.6.3 1l-.8 2.8H13c.6 0 1 .4 1 1 0 .2 0 .4-.2.6l-1.5 5c-.2.5-.7.9-1.3.9H5" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
                  有用
                </button>
              </div>

              <!-- 正文 -->
              <div class="shimmer-target" :class="{ loading: detailLoading }">
                <div class="article-content markdown-body" v-html="renderedContent" />
                <div class="detail-shimmer" v-if="detailLoading" />
              </div>
            </div>

            <!-- TOC 悬浮目录 -->
            <aside class="modal-toc" v-if="tocItems.length">
              <h5 class="toc-title">目录</h5>
              <nav class="toc-nav">
                <a
                  v-for="item in tocItems"
                  :key="item.id"
                  :class="['toc-link', { active: item.id === activeTocId }]"
                  :style="{ paddingLeft: (item.level - 1) * 12 + 8 + 'px' }"
                  @click.prevent="scrollToToc(item.id)"
                >{{ item.text }}</a>
              </nav>
            </aside>
          </div>

          <!-- 上下篇导航 -->
          <div class="modal-footer-nav">
            <button class="nav-article-btn" v-if="prevArticle" @click="openArticle(prevArticle)">
              ← {{ prevArticle.title }}
            </button>
            <span v-else class="nav-article-btn empty" />
            <button class="nav-article-btn" v-if="nextArticle" @click="openArticle(nextArticle)">
              {{ nextArticle.title }} →
            </button>
            <span v-else class="nav-article-btn empty" />
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import api from '@/api/index'
import { formatTime } from '@/utils'

const md = new MarkdownIt({ breaks: true, html: true })

// ============ State ============
const keyword = ref('')
const activeCategory = ref('')
const articles = ref([] as any[])
const categories = ref([] as any[])
const currentArticle = ref(null as any)
const page = ref(1)
const totalArticles = ref(0)
const pageSize = 24
const resetting = ref(false)
const listLoading = ref(true)
const detailLoading = ref(false)
const searching = ref(false)
const sortBy = ref('latest')
const activeTags = ref([] as string[])
const opsCollapsed = ref(false)
const faqCollapsed = ref(false)
const showMobileSidebar = ref(false)
const copied = ref(false)
const modalBodyRef = ref<HTMLElement | null>(null)
const activeTocId = ref('')

// ============ Computed ============
const isAdmin = computed(() => localStorage.getItem('role') === 'admin')
const totalPages = computed(() => Math.max(1, Math.ceil(totalArticles.value / pageSize)))

const opsCategories = computed(() =>
  categories.value.filter((c: any) => !c.name.startsWith('常见-'))
)
const faqCategories = computed(() =>
  categories.value
    .filter((c: any) => c.name.startsWith('常见-'))
    .map((c: any) => ({ ...c, label: c.name.replace('常见-', '') }))
)

const pageRangeText = computed(() => {
  const start = (page.value - 1) * pageSize + 1
  const end = Math.min(page.value * pageSize, totalArticles.value)
  return `显示 ${start}-${end}，共 ${totalArticles.value} 条`
})

const visiblePages = computed(() => {
  const total = totalPages.value
  const current = page.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = [1]
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

const sortedArticles = computed(() => {
  const list = [...articles.value]
  if (sortBy.value === 'views') {
    list.sort((a, b) => (b.viewCount || 0) - (a.viewCount || 0))
  } else if (sortBy.value === 'alpha') {
    list.sort((a, b) => a.title.localeCompare(b.title, 'zh'))
  }
  return list
})

const hotTags = computed(() => {
  const freq: Record<string, number> = {}
  articles.value.forEach(a => {
    (a.tags || []).forEach((t: string) => {
      if (activeTags.value.includes(t)) return
      freq[t] = (freq[t] || 0) + 1
    })
  })
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([k]) => k)
})

const topViewed = computed(() =>
  [...articles.value].sort((a, b) => (b.viewCount || 0) - (a.viewCount || 0)).slice(0, 4)
)

const renderedContent = computed(() => {
  if (!currentArticle.value) return ''
  const raw = currentArticle.value.content || ''
  // 为 h2/h3 注入 id 供 TOC 锚点
  return md.render(
    raw.replace(/^(#{2,3})\s+(.+)$/gm, (_, hashes: string, text: string) => {
      const id = 'h-' + text.replace(/[^\w一-鿿]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)
      return `<${hashes} id="${id}">${text}</${hashes}>`
    })
  )
})

const tocItems = computed(() => {
  if (!currentArticle.value) return []
  const items: { id: string; text: string; level: number }[] = []
  const content = currentArticle.value.content || ''
  const re = /^(#{2,3})\s+(.+)$/gm
  let m: RegExpExecArray | null
  while ((m = re.exec(content)) !== null) {
    const id = 'h-' + m[2].replace(/[^\w一-鿿]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)
    items.push({ id, text: m[2], level: m[1].length })
  }
  return items
})

const prevArticle = computed(() => {
  if (!currentArticle.value) return null
  const idx = sortedArticles.value.findIndex((a: any) => a.id === currentArticle.value.id)
  return idx > 0 ? sortedArticles.value[idx - 1] : null
})

const nextArticle = computed(() => {
  if (!currentArticle.value) return null
  const idx = sortedArticles.value.findIndex((a: any) => a.id === currentArticle.value.id)
  return idx < sortedArticles.value.length - 1 ? sortedArticles.value[idx + 1] : null
})

const sortOptions = [
  { label: '最新更新', value: 'latest' },
  { label: '最多查看', value: 'views' },
  { label: '标题排序', value: 'alpha' },
]

// 最近浏览 (localStorage)
const recentArticles = computed(() => {
  try {
    const raw = localStorage.getItem('kb_recent')
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
})

// 收藏列表 (localStorage)
const favorites = computed(() => {
  try {
    const raw = localStorage.getItem('kb_favorites')
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
})

// 搜索联想
const searchSuggestions = computed(() => {
  if (!keyword.value || keyword.value.length < 2) return []
  const kw = keyword.value.toLowerCase()
  const seen = new Set<string>()
  const result: string[] = []
  for (const a of articles.value) {
    if (a.title.toLowerCase().includes(kw) && !seen.has(a.title)) {
      seen.add(a.title)
      result.push(a.title)
    }
    if (result.length >= 5) break
  }
  return result
})

// ============ Debounce ============
let debounceTimer: ReturnType<typeof setTimeout> | null = null
function onSearchInput() {
  searching.value = true
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    searching.value = false
    page.value = 1
    search()
  }, 350)
}

// ============ Methods ============
function getExcerpt(a: any) {
  const content = (a.content || '').replace(/[#*|>\-\n]+/g, ' ').replace(/\s+/g, ' ').trim()
  return content.slice(0, 100) + (content.length > 100 ? '…' : '')
}

function highlightText(text: string, kw: string) {
  if (!kw || !text) return text
  const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  return text.replace(re, '<mark class="hl">$1</mark>')
}

function isNewArticle(a: any) {
  if (!a.createdAt) return false
  const created = new Date(a.createdAt).getTime()
  return Date.now() - created < 7 * 24 * 3600 * 1000
}

function severityLabel(s: string) {
  return s === 'critical' ? '严重' : s === 'warning' ? '注意' : '参考'
}

function categoryIcon(name: string) {
  const map: Record<string, string> = {
    '磁盘与文件系统问题': '💾',
    '进程与内存问题': '⚙️',
    '网络问题': '🌐',
    '服务管理问题': '🔧',
    '系统启动与内核问题': '🖥️',
    '安全与权限问题': '🔒',
    '配置漂移与系统管理问题': '📋',
    '日志系统问题': '📝',
    '国产化平台特有问题': '🏭',
    '常见-安装问题': '💿', '常见-启动问题': '🚀', '常见-登录问题': '🔑',
    '常见-激活问题': '✅', '常见-权限问题': '🛡️', '常见-版本问题': '📦',
    '常见-软件安装': '📥', '常见-外设使用': '🖨️', '常见-手册问题': '📖',
    '常见-显示问题': '🖼️', '常见-网络问题': '📡', '常见-输入问题': '⌨️',
    '常见-挂卸载问题': '💽', '常见-应用问题': '🧩', '常见-其他问题': '📌',
  }
  return map[name] || '📄'
}

function saveRecent(article: any) {
  try {
    const raw = localStorage.getItem('kb_recent')
    const list: any[] = raw ? JSON.parse(raw) : []
    const filtered = list.filter((a: any) => a.id !== article.id)
    filtered.unshift({ id: article.id, title: article.title, category: article.category })
    localStorage.setItem('kb_recent', JSON.stringify(filtered.slice(0, 10)))
  } catch {}
}

function isFavorited(id: string) {
  return favorites.value.some((a: any) => a.id === id)
}

function toggleFavorite(article: any) {
  try {
    const raw = localStorage.getItem('kb_favorites')
    const list: any[] = raw ? JSON.parse(raw) : []
    const idx = list.findIndex((a: any) => a.id === article.id)
    if (idx >= 0) {
      list.splice(idx, 1)
    } else {
      list.unshift({ id: article.id, title: article.title, category: article.category })
    }
    localStorage.setItem('kb_favorites', JSON.stringify(list))
  } catch {}
}

function feedbackArticle(_type: string) {
  // 可选：调用后端埋点
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(currentArticle.value?.content || '')
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = currentArticle.value?.content || ''
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

function goToPage(p: number | string) {
  if (p === '...') return
  page.value = p as number
  search()
}

function scrollToToc(id: string) {
  activeTocId.value = id
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function closeModal() {
  currentArticle.value = null
  activeTocId.value = ''
  document.body.style.overflow = ''
}

function toggleTag(tag: string) {
  const idx = activeTags.value.indexOf(tag)
  if (idx >= 0) {
    activeTags.value.splice(idx, 1)
  } else {
    activeTags.value.push(tag)
  }
  page.value = 1
  search()
}

async function search() {
  listLoading.value = true
  try {
    const params: any = { page: page.value, size: pageSize }
    if (activeCategory.value) params.category = activeCategory.value
    if (keyword.value) params.keyword = keyword.value
    if (sortBy.value === 'views') params.sort = 'views'
    if (sortBy.value === 'alpha') params.sort = 'title'
    if (activeTags.value.length) params.tags = activeTags.value.join(',')

    const { data } = await api.get('/knowledge/articles', { params })
    if (data.code === 0) {
      articles.value = data.data.items || []
      totalArticles.value = data.data.total || 0
    }
  } catch (e) {
    console.error('知识库加载失败:', e)
  } finally {
    listLoading.value = false
  }
}

async function openArticle(a: any) {
  saveRecent(a)
  detailLoading.value = true
  try {
    const { data } = await api.get(`/knowledge/articles/${a.id}`)
    if (data.code === 0) {
      currentArticle.value = data.data
      document.body.style.overflow = 'hidden'
      await nextTick()
      // 监听滚动高亮 TOC
      observeTocScroll()
    }
  } catch (e) {
    currentArticle.value = a
    document.body.style.overflow = 'hidden'
  } finally {
    detailLoading.value = false
  }
}

let tocObserver: IntersectionObserver | null = null
function observeTocScroll() {
  if (tocObserver) tocObserver.disconnect()
  const headings = document.querySelectorAll('.article-content h2[id], .article-content h3[id]')
  tocObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeTocId.value = entry.target.id
          break
        }
      }
    },
    { rootMargin: '-20% 0px -70% 0px' }
  )
  headings.forEach(h => tocObserver!.observe(h))
}

async function resetKnowledge() {
  if (!confirm('确定要清空旧知识库并从文件重新导入吗？此操作不可撤销。')) return
  resetting.value = true
  try {
    const { data } = await api.post('/knowledge/reset')
    if (data.code === 0) {
      alert(`知识库已重置！共导入 ${data.data.total} 篇文章`)
      const catResp = await api.get('/knowledge/categories')
      if (catResp.data.code === 0) categories.value = catResp.data.data
      page.value = 1
      activeCategory.value = ''
      keyword.value = ''
      activeTags.value = []
      await search()
    }
  } catch (e: any) {
    alert('重置失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    resetting.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await api.get('/knowledge/categories')
    if (data.code === 0) categories.value = data.data
  } catch (e) {
    console.error('分类加载失败:', e)
  }
  await search()
})
</script>

<style lang="scss" scoped>
.knowledge-layout {
  display: flex; gap: 24px; max-width: 1400px; margin: 0 auto;
  min-height: calc(100vh - 140px);
}

/* ===== 左侧边栏 ===== */
.knowledge-sidebar {
  width: 250px; flex-shrink: 0;
  background: #fff; border-radius: 14px; border: 1px solid #e2e8f0;
  padding: 20px 0; position: sticky; top: 20px; align-self: flex-start;
  max-height: calc(100vh - 160px); overflow-y: auto;
}
.sidebar-header {
  padding: 0 18px 14px; border-bottom: 1px solid #f1f5f9;
  display: flex; justify-content: space-between; align-items: baseline;
}
.sidebar-title { font-size: 14px; font-weight: 700; color: #1e293b; }
.sidebar-total { font-size: 12px; color: #94a3b8; }

/* 最近浏览 */
.recent-section { padding: 8px 18px 4px; }
.recent-title { font-size: 10px; font-weight: 700; color: #c0c8d4; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.recent-item {
  display: flex; align-items: center; gap: 6px; width: 100%; padding: 4px 0;
  border: none; background: none; cursor: pointer; text-align: left;
  font-size: 12px; color: #64748b;
  &:hover { color: #2563eb; }
}
.recent-dot { width: 4px; height: 4px; border-radius: 50%; background: #cbd5e1; flex-shrink: 0; }
.recent-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 分类导航 */
.category-nav { padding: 4px 10px; display: flex; flex-direction: column; gap: 2px; }

.cat-group { margin-top: 2px; }
.cat-group-title {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 18px 4px; font-size: 11px; font-weight: 700;
  color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;
  border: none; background: none; cursor: pointer; width: 100%; text-align: left;
  &:hover { color: #64748b; }
}
.group-count { font-size: 10px; color: #cbd5e1; margin-left: auto; font-weight: 400; }
.collapse-arrow { transition: transform 0.2s; color: #94a3b8; &.rotated { transform: rotate(90deg); } }

.cat-item {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 9px 10px; border: none; border-radius: 8px;
  background: transparent; cursor: pointer; transition: all 0.15s;
  text-align: left; font-size: 13px; color: #475569;
  &:hover { background: #f8fafc; color: #1e293b; }
  &.active { background: #eff6ff; color: #2563eb; font-weight: 600; }
}
.cat-icon { font-size: 15px; flex-shrink: 0; }
.cat-label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-badge {
  font-size: 11px; color: #94a3b8; background: #f1f5f9;
  padding: 1px 7px; border-radius: 10px; flex-shrink: 0;
  .cat-item.active & { background: #dbeafe; color: #2563eb; }
}

/* 移动端 */
.mobile-cat-toggle { display: none; }
.sidebar-overlay { display: none; }

/* ===== 右侧主内容 ===== */
.knowledge-main { flex: 1; min-width: 0; }

.search-row { margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
.search-box {
  display: flex; align-items: center; gap: 10px; flex: 1;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 11px 16px; position: relative;
  &:focus-within { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.06); }
}
.search-input { flex: 1; border: none; outline: none; font-size: 14px; color: #1e293b; &::placeholder { color: #cbd5e1; } }
.search-spinner {
  width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #2563eb;
  border-radius: 50%; animation: spin 0.6s linear infinite;
}
.search-clear { background: none; border: none; font-size: 18px; color: #94a3b8; cursor: pointer; }
.reset-btn {
  padding: 9px 18px; border: 1px solid #fecaca; border-radius: 10px;
  background: #fff; font-size: 13px; color: #dc2626; cursor: pointer; white-space: nowrap;
  &:hover:not(:disabled) { background: #fef2f2; border-color: #dc2626; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

/* 搜索建议 */
.search-suggestions {
  position: relative; z-index: 10;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  margin-top: -4px; margin-bottom: 10px; overflow: hidden;
}
.suggestion-item {
  display: block; width: 100%; padding: 8px 16px; border: none; background: none;
  cursor: pointer; text-align: left; font-size: 13px; color: #475569;
  &:hover { background: #f8fafc; color: #2563eb; }
}

/* 工具栏 */
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.sort-group { display: flex; gap: 2px; background: #f1f5f9; border-radius: 8px; padding: 2px; }
.sort-btn {
  padding: 5px 12px; border: none; border-radius: 6px;
  background: transparent; font-size: 12px; color: #64748b; cursor: pointer;
  &.active { background: #fff; color: #1e293b; font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
}
.result-hint { font-size: 13px; color: #64748b; }

/* 标签云 */
.tag-toolbar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 2px; }
.tag-label { font-size: 12px; color: #94a3b8; flex-shrink: 0; }
.hot-tag {
  padding: 3px 10px; border-radius: 12px; border: 1px solid #e2e8f0;
  background: #fff; font-size: 12px; color: #64748b; cursor: pointer;
  &:hover { border-color: #2563eb; color: #2563eb; }
  &.selected { background: #2563eb; border-color: #2563eb; color: #fff; }
}

/* 筛选芯片 */
.filter-chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.chip {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 12px; background: #eff6ff; color: #2563eb;
  font-size: 12px; font-weight: 500;
}
.chip-remove { background: none; border: none; font-size: 14px; color: #2563eb; cursor: pointer; padding: 0 2px; }
.chip-clear { background: none; border: none; font-size: 12px; color: #94a3b8; cursor: pointer; }

/* ===== 文章卡片 ===== */
.article-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.article-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px;
  cursor: pointer; transition: all 0.2s;
  &:hover { border-color: #2563eb; box-shadow: 0 6px 20px rgba(0,0,0,0.05); transform: translateY(-1px); }
  &:active { transform: translateY(0); box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
}
.card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.card-category { font-size: 11px; color: #94a3b8; }
.new-badge {
  font-size: 10px; font-weight: 700; color: #fff; background: #2563eb;
  padding: 1px 6px; border-radius: 3px; letter-spacing: 0.5px;
  animation: newPulse 2s ease-in-out infinite;
}

.severity-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  &.sev-critical { background: #fef2f2; color: #dc2626; animation: pulse 2s ease-in-out infinite; }
  &.sev-warning { background: #fffbeb; color: #d97706; }
  &.sev-info { background: #eff6ff; color: #2563eb; }
}

.card-title {
  font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 6px;
  line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-excerpt {
  font-size: 13px; color: #64748b; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-bottom: 8px;
}

.card-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 5px; background: #f1f5f9; color: #64748b; }
.card-meta { display: flex; gap: 14px; font-size: 12px; color: #c0c8d4; }

/* 关键词高亮 */
:deep(.hl) { background: #fef08a; color: #854d0e; border-radius: 2px; padding: 0 2px; }

/* 骨架屏 */
.skeleton { pointer-events: none; padding: 20px; }
.sk-line { background: #f1f5f9; border-radius: 6px; margin-bottom: 10px; animation: shimmer 1.5s infinite; }
.sk-title { height: 18px; width: 70%; }
.sk-text { height: 14px; width: 100%; &.short { width: 50%; } }
.sk-tags { height: 22px; width: 40%; margin-bottom: 0; }

/* 卡片列表过渡 */
.card-list-enter-active { transition: all 0.3s ease; }
.card-list-leave-active { transition: all 0.2s ease; }
.card-list-enter-from { opacity: 0; transform: translateY(8px); }
.card-list-leave-to { opacity: 0; transform: translateY(-4px); }
.card-list-move { transition: transform 0.3s ease; }

/* ===== 空状态 ===== */
.empty { text-align: center; padding: 80px 20px; color: #94a3b8; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-hint { font-size: 12px; color: #cbd5e1; margin-top: 4px; }
.empty-actions { margin-top: 16px; }
.empty-btn {
  padding: 8px 20px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; font-size: 13px; color: #2563eb; cursor: pointer;
  &:hover { background: #eff6ff; border-color: #2563eb; }
}
.empty-steps { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; text-align: left; max-width: 280px; margin-inline: auto; }
.step { font-size: 13px; color: #64748b; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 700; margin-right: 8px; }
.hot-suggest { margin-top: 20px; }
.hot-suggest-title { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }
.hot-suggest-item {
  display: block; margin: 0 auto 4px; padding: 6px 12px; border: 1px solid #f1f5f9;
  border-radius: 6px; background: #fafafa; font-size: 13px; color: #475569; cursor: pointer;
  &:hover { color: #2563eb; border-color: #e2e8f0; }
}

/* ===== 分页 ===== */
.pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }
.page-numbers { display: flex; gap: 4px; }
.page-btn {
  min-width: 34px; height: 34px; padding: 0 8px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; font-size: 13px; color: #475569; cursor: pointer; display: flex; align-items: center; justify-content: center;
  &:hover:not(:disabled):not(.current):not(.ellipsis) { border-color: #2563eb; color: #2563eb; }
  &.current { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 600; }
  &.ellipsis { cursor: default; color: #c0c8d4; }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
  &.nav { font-size: 16px; }
}
.page-stat { font-size: 13px; color: #94a3b8; }

/* ===== 详情弹窗 ===== */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15,23,42,0.45);
  backdrop-filter: blur(4px); z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.modal-card {
  background: #fff; border-radius: 18px; padding: 32px 36px;
  width: 900px; max-height: 90vh; overflow-y: auto;
  position: relative; box-shadow: 0 25px 70px rgba(0,0,0,0.18);
}
.modal-close {
  position: absolute; top: 14px; right: 14px; background: none; border: none;
  font-size: 26px; color: #94a3b8; cursor: pointer; width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center; border-radius: 8px; z-index: 2;
  &:hover { color: #1e293b; background: #f1f5f9; }
}

/* 面包屑 */
.modal-breadcrumb { display: flex; align-items: center; gap: 6px; margin-bottom: 12px; font-size: 12px; }
.crumb { color: #2563eb; cursor: pointer; &:hover { text-decoration: underline; } &.active { color: #94a3b8; cursor: default; &:hover { text-decoration: none; } } }
.crumb-sep { color: #cbd5e1; }

/* 弹窗布局 */
.modal-layout { display: flex; gap: 24px; }
.modal-body { flex: 1; min-width: 0; }
.modal-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.modal-title { font-size: 21px; font-weight: 700; color: #1e293b; margin: 6px 0 8px; }

/* 操作按钮 */
.modal-actions { display: flex; gap: 8px; margin: 12px 0; }
.act-btn {
  display: flex; align-items: center; gap: 4px; padding: 5px 12px;
  border: 1px solid #e2e8f0; border-radius: 6px; background: #fff;
  font-size: 12px; color: #64748b; cursor: pointer;
  &:hover { border-color: #2563eb; color: #2563eb; background: #f8faff; }
}

/* TOC */
.modal-toc {
  width: 180px; flex-shrink: 0; position: sticky; top: 0; align-self: flex-start;
  max-height: 60vh; overflow-y: auto; border-left: 1px solid #f1f5f9; padding-left: 16px;
}
.toc-title { font-size: 12px; font-weight: 700; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
.toc-nav { display: flex; flex-direction: column; gap: 2px; }
.toc-link {
  font-size: 12px; color: #64748b; text-decoration: none; padding: 4px 8px;
  border-radius: 4px; cursor: pointer; display: block;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  &:hover { color: #2563eb; background: #f8fafc; }
  &.active { color: #2563eb; background: #eff6ff; font-weight: 500; }
}

/* 正文 */
.simmer-target { position: relative; }
.shimmer-target.loading .detail-shimmer {
  position: absolute; inset: 0; background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.8) 50%, transparent 100%);
  animation: shimmer 1.5s infinite; border-radius: 8px;
}

.article-content {
  margin-top: 16px; font-size: 14px; color: #334155; line-height: 1.8;
  :deep(h2) { font-size: 17px; margin: 22px 0 10px; color: #1e293b; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; scroll-margin-top: 20px; }
  :deep(h3) { font-size: 15px; margin: 16px 0 8px; color: #334155; scroll-margin-top: 20px; }
  :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
  :deep(th) { background: #f8fafc; padding: 8px 12px; text-align: left; font-weight: 600; border: 1px solid #e2e8f0; color: #475569; }
  :deep(td) { padding: 8px 12px; border: 1px solid #e2e8f0; vertical-align: top; }
  :deep(tr:hover td) { background: #f8fafc; }
  :deep(ul) { padding-left: 20px; }
  :deep(li) { margin: 3px 0; }
  :deep(code) { font-family: 'JetBrains Mono', monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #2563eb; }
  :deep(pre) { background: #f8fafc; padding: 12px 16px; border-radius: 8px; overflow-x: auto; font-size: 13px; border: 1px solid #e2e8f0; }
  :deep(strong) { color: #1e293b; font-weight: 600; }
  :deep(blockquote) { border-left: 3px solid #2563eb; padding-left: 14px; margin: 10px 0; color: #64748b; }
}

/* 底部导航 */
.modal-footer-nav { display: flex; justify-content: space-between; gap: 12px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #f1f5f9; }
.nav-article-btn {
  flex: 1; max-width: 48%; text-align: left; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 10px;
  background: #fff; font-size: 13px; color: #475569; cursor: pointer;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  &:hover { border-color: #2563eb; color: #2563eb; }
  &.empty { visibility: hidden; }
}

/* ===== 动画 ===== */
@keyframes shimmer {
  0% { background-position: -200px 0; }
  100% { background-position: 200px 0; }
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
@keyframes newPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .knowledge-layout { flex-direction: column; gap: 0; }
  .knowledge-sidebar {
    position: fixed; left: -280px; top: 0; bottom: 0; z-index: 200;
    width: 270px; border-radius: 0; max-height: 100vh;
    transition: left 0.3s ease;
    &.mobile-open { left: 0; }
  }
  .sidebar-overlay {
    display: block; position: fixed; inset: 0; z-index: 199;
    background: rgba(15,23,42,0.3);
  }
  .mobile-cat-toggle {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%; padding: 10px 16px; border: 1px solid #e2e8f0;
    border-radius: 10px; background: #fff; font-size: 14px; color: #1e293b;
    margin-bottom: 12px;
  }

  .article-grid { grid-template-columns: 1fr; }
  .modal-layout { flex-direction: column; }
  .modal-toc { display: none; }
  .modal-card { width: 100%; border-radius: 0; padding: 20px; max-height: 100vh; }
  .modal-breadcrumb { flex-wrap: wrap; }
  .toolbar-left { flex-wrap: wrap; gap: 8px; }
  .search-row { flex-wrap: wrap; }
  .modal-footer-nav { flex-direction: column; }
  .nav-article-btn { max-width: 100%; }
}

@media (max-width: 640px) {
  .modal-close { top: 8px; right: 8px; }
  .modal-card { padding: 16px; }
  .modal-title { font-size: 17px; }
  .sort-group { width: 100%; justify-content: space-between; }
}
</style>
