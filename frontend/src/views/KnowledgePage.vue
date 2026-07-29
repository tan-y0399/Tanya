<template>
  <div class="knowledge-garden">
    <div class="ambient ambient-a" aria-hidden="true"></div>
    <div class="ambient ambient-b" aria-hidden="true"></div>
    <div class="ambient ambient-c" aria-hidden="true"></div>

    <div class="knowledge-layout">
    <!-- 移动端分类抽屉按钮 -->
    <button class="mobile-cat-toggle" @click="showMobileSidebar = !showMobileSidebar">
      <span>{{ activeCategoryLabel }}</span>
      <svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
    </button>

    <!-- 遮罩 -->
    <div class="sidebar-overlay" v-if="showMobileSidebar" @click="showMobileSidebar = false" />

    <!-- ===== 左侧分类边栏 ===== -->
    <aside class="knowledge-sidebar" :class="{ 'mobile-open': showMobileSidebar }">
      <div class="sidebar-header">
        <span class="sidebar-tag">MOD-KB</span>
        <h3 class="sidebar-title">知识分类</h3>
        <span class="sidebar-total">共 {{ totalArticles }} 篇</span>
      </div>

      <nav class="category-nav">
        <button
          class="cat-item"
          :class="{ active: !activeCategory }"
          @click="activeCategory = ''; page = 1; search(); showMobileSidebar = false"
        >
          <KnowledgeCategoryIcon name="" :active="!activeCategory" />
          <span class="cat-label">全部文章</span>
          <span class="cat-badge">{{ totalArticles }}</span>
        </button>
      </nav>

      <!-- 运维知识库分组（可折叠） -->
      <div class="cat-group" v-if="opsCategories.length">
        <button class="cat-group-title" @click="opsCollapsed = !opsCollapsed">
          <KnowledgeCategoryIcon icon-key="service" color="#38BDF8" sm />
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
            <KnowledgeCategoryIcon :name="c.name" :active="activeCategory === c.name" />
            <span class="cat-label">{{ c.name }}</span>
            <span class="cat-badge">{{ c.count }}</span>
          </button>
        </nav>
      </div>

      <!-- 常见问题FAQ分组（可折叠） -->
      <div class="cat-group" v-if="faqCategories.length">
        <button class="cat-group-title" @click="faqCollapsed = !faqCollapsed">
          <KnowledgeCategoryIcon icon-key="manual" color="#84CC16" sm />
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
            <KnowledgeCategoryIcon :name="c.name" :active="activeCategory === c.name" />
            <span class="cat-label">{{ c.label }}</span>
            <span class="cat-badge">{{ c.count }}</span>
          </button>
        </nav>
      </div>
    </aside>

    <!-- ===== 右侧主内容 ===== -->
    <main class="knowledge-main">
      <header class="page-hero">
        <span class="hero-tag">KB · GARDEN</span>
        <h2 class="hero-title">{{ activeCategoryLabel }}</h2>
        <p class="hero-desc">在清新整洁的知识花园中慢读细查 · 共 {{ totalArticles }} 篇运维智慧</p>
      </header>

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

      <!-- 最近浏览 + 标签 -->
      <div class="meta-split">
        <section class="meta-pane meta-recent">
          <div class="meta-pane-head">
            <span class="meta-pane-tag">RECENT</span>
            <span class="meta-pane-title">最近浏览</span>
          </div>
          <div class="meta-pane-body">
            <button
              v-for="ra in recentArticles"
              :key="ra.id"
              type="button"
              class="recent-chip"
              @click="openArticle(ra)"
            >
              <span class="recent-dot" />
              <span class="recent-label">{{ ra.title }}</span>
            </button>
            <p v-if="!recentArticles.length" class="meta-empty">暂无浏览记录，开始探索吧</p>
          </div>
        </section>
        <section class="meta-pane meta-tags">
          <div class="meta-pane-head">
            <span class="meta-pane-tag">TAGS</span>
            <span class="meta-pane-title">热门标签</span>
            <button
              v-if="activeTags.length"
              type="button"
              class="meta-clear"
              @click="activeTags = []; page = 1; search()"
            >清空筛选</button>
          </div>
          <div class="meta-pane-body">
            <button
              v-for="t in hotTags"
              :key="t"
              type="button"
              class="hot-tag"
              :class="{ selected: activeTags.includes(t) }"
              @click="toggleTag(t)"
            >{{ t }}</button>
            <span
              v-for="t in activeTags.filter(tag => !hotTags.includes(tag))"
              :key="'active-' + t"
              class="chip active-only"
            >
              {{ t }}
              <button type="button" class="chip-remove" @click="toggleTag(t)">&times;</button>
            </span>
            <p v-if="!hotTags.length && !activeTags.length" class="meta-empty">暂无标签</p>
          </div>
        </section>
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
          :class="[
            `sev-${a.severity}`,
            titleEffectClass(a),
            { 'card-active': isCardHighlighted(a.id) },
          ]"
          v-for="a in sortedArticles"
          :key="a.id"
          @mouseenter="hoveredCardId = a.id"
          @mouseleave="hoveredCardId = null"
          @click="openArticle(a)"
        >
          <div class="card-top">
            <span class="severity-badge" :class="`sev-${a.severity}`">
              {{ severityLabel(a.severity) }}
            </span>
            <span class="card-category">{{ a.category }}</span>
            <span class="new-badge" v-if="isNewArticle(a)">NEW</span>
          </div>
          <div class="card-body">
            <h4 class="card-title" :class="titleEffectClass(a)" v-html="highlightText(a.title, keyword)" />
            <ul v-if="getKeyPoints(a).length" class="card-keypoints">
              <li v-for="(pt, i) in getKeyPoints(a)" :key="i" v-html="highlightText(pt, keyword)" />
            </ul>
            <p v-else class="card-excerpt" v-html="highlightText(getExcerpt(a), keyword)" />
          </div>
          <div class="card-tags" :class="{ 'is-empty': !a.tags.length }">
            <span
              v-for="t in a.tags.slice(0, 4)"
              :key="t"
              class="tag"
              :title="t"
              v-html="highlightText(t, keyword)"
            />
          </div>
          <div class="card-footer">
            <div class="card-stats">
              <span class="stat-chip views" title="阅读量">
                <span class="stat-icon" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 16 16"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" stroke="currentColor" fill="none" stroke-width="1.2"/><circle cx="8" cy="8" r="2" stroke="currentColor" fill="none" stroke-width="1.2"/></svg>
                </span>
                <span class="stat-num">{{ a.viewCount || 0 }}</span>
              </span>
              <span class="stat-chip likes" :class="{ 'is-active': isLiked(a) }" title="点赞">
                <span class="stat-icon" aria-hidden="true">
                  <svg v-if="isLiked(a)" width="13" height="13" viewBox="0 0 24 24"><path fill="currentColor" d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/></svg>
                  <svg v-else width="13" height="13" viewBox="0 0 16 16"><path d="M5 6h-.5C3.6 6 3 6.6 3 7.5v5c0 .9.6 1.5 1.5 1.5H5m0-7v7m0-7l2.5-3.5c.3-.4.8-.5 1.2-.3.4.2.5.6.3 1l-.8 2.8H13c.6 0 1 .4 1 1 0 .2 0 .4-.2.6l-1.5 5c-.2.5-.7.9-1.3.9H5" stroke="currentColor" stroke-width="1.1" fill="none"/></svg>
                </span>
                <span class="stat-num">{{ a.likeCount || 0 }}</span>
              </span>
              <span class="stat-chip favs" :class="{ 'is-active': isFavorited(a) }" title="收藏">
                <span class="stat-icon" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 16 16"><path d="M8 1.5l1.8 4.8 5.2.4-4 3.5 1.3 5-4.3-3-4.3 3 1.3-5-4-3.5 5.2-.4L8 1.5z" stroke="currentColor" stroke-width="1" :fill="isFavorited(a) ? 'currentColor' : 'none'"/></svg>
                </span>
                <span class="stat-num">{{ a.favoriteCount || 0 }}</span>
              </span>
            </div>
            <time class="card-time">{{ formatTime(a.updatedAt) }}</time>
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
    </div>

    <!-- ===== 详情弹窗 ===== -->
    <teleport to="body">
      <div class="modal-overlay" v-if="currentArticle" @click.self="closeModal">
        <div class="modal-card" :class="`modal-sev-${currentArticle.severity}`" @click.stop>
          <div class="modal-sticky-top">
            <div class="modal-breadcrumb">
              <span class="crumb" @click="closeModal">全部</span>
              <span class="crumb-sep">›</span>
              <span class="crumb">{{ currentArticle.category }}</span>
              <span class="crumb-sep">›</span>
              <span class="crumb active">{{ currentArticle.title }}</span>
            </div>
            <button class="modal-close" type="button" aria-label="关闭" @click="closeModal">&times;</button>
          </div>

          <div class="modal-scroll-body" ref="modalScrollRef">
          <div class="modal-hero">
            <div class="modal-header">
              <span class="severity-badge" :class="`sev-${currentArticle.severity}`">
                {{ severityLabel(currentArticle.severity) }}
              </span>
              <span class="card-category">{{ currentArticle.category }}</span>
            </div>
            <h2 class="modal-title" :class="titleEffectClass(currentArticle)">{{ currentArticle.title }}</h2>
            <div class="card-tags" v-if="currentArticle.tags.length">
              <span class="tag" v-for="t in currentArticle.tags" :key="t">{{ t }}</span>
            </div>
            <div class="modal-stats-bar">
              <span class="hero-stat"><strong>{{ currentArticle.viewCount || 0 }}</strong> 阅读</span>
              <span class="hero-stat likes"><strong>{{ currentArticle.likeCount || 0 }}</strong> 点赞</span>
              <span class="hero-stat favs"><strong>{{ currentArticle.favoriteCount || 0 }}</strong> 收藏</span>
            </div>
          </div>

          <div class="modal-layout">
            <div class="modal-body" ref="modalBodyRef">
              <div class="modal-actions">
                <button class="act-btn" @click="copyContent">
                  <svg width="14" height="14" viewBox="0 0 16 16"><rect x="5" y="1" width="9" height="13" rx="1.5" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M2 4h-.5A1.5 1.5 0 000 5.5v9A1.5 1.5 0 001.5 16h7a1.5 1.5 0 001.5-1.5V14" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
                  {{ copied ? '已复制' : '复制全文' }}
                </button>
                <button
                  class="act-btn fav-btn"
                  :class="{ active: isFavorited(currentArticle), pop: favPop }"
                  @click="handleToggleFavorite(currentArticle)"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 1.5l1.8 4.8 5.2.4-4 3.5 1.3 5-4.3-3-4.3 3 1.3-5-4-3.5 5.2-.4L8 1.5z" :fill="isFavorited(currentArticle) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1"/></svg>
                  {{ isFavorited(currentArticle) ? '已收藏' : '收藏' }}
                  <span class="act-count">{{ currentArticle.favoriteCount || 0 }}</span>
                </button>
                <button
                  class="act-btn like-btn"
                  :class="{ active: isLiked(currentArticle), pop: likePop }"
                  @click="handleToggleLike(currentArticle)"
                >
                  <svg v-if="isLiked(currentArticle)" width="14" height="14" viewBox="0 0 24 24"><path fill="currentColor" d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/></svg>
                  <svg v-else width="14" height="14" viewBox="0 0 16 16"><path d="M5 6h-.5C3.6 6 3 6.6 3 7.5v5c0 .9.6 1.5 1.5 1.5H5m0-7v7m0-7l2.5-3.5c.3-.4.8-.5 1.2-.3.4.2.5.6.3 1l-.8 2.8H13c.6 0 1 .4 1 1 0 .2 0 .4-.2.6l-1.5 5c-.2.5-.7.9-1.3.9H5" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
                  {{ isLiked(currentArticle) ? '已点赞' : '有用' }}
                  <span class="act-count">{{ currentArticle.likeCount || 0 }}</span>
                </button>
              </div>

              <div v-if="detailKeyPoints.length" class="detail-highlights">
                <h5 class="highlights-title">核心要点</h5>
                <ul>
                  <li v-for="(pt, i) in detailKeyPoints" :key="i">{{ pt }}</li>
                </ul>
              </div>

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
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import {
  fetchArticles,
  fetchArticle,
  fetchCategories,
  fetchEngagement,
  toggleLike,
  toggleFavorite,
  resetKnowledge as resetKnowledgeApi,
} from '@/api/knowledge'
import { formatTime } from '@/utils'
import KnowledgeCategoryIcon from '@/components/knowledge/KnowledgeCategoryIcon.vue'

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
const likePop = ref(false)
const favPop = ref(false)
const engagementMap = ref<Record<string, { liked: boolean; favorited: boolean }>>({})
const hoveredCardId = ref<string | null>(null)
const flowHighlightIds = ref<string[]>([])
let flowTimer: ReturnType<typeof setInterval> | null = null
const modalBodyRef = ref<HTMLElement | null>(null)
const modalScrollRef = ref<HTMLElement | null>(null)
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

const activeCategoryLabel = computed(() => {
  if (!activeCategory.value) return '全部文章'
  const faq = faqCategories.value.find((c: any) => c.name === activeCategory.value)
  if (faq) return faq.label
  return activeCategory.value
})

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
  const raw = refineArticleContent(currentArticle.value.content || '', currentArticle.value.title)
  const html = md.render(raw)
  return addHeadingIds(html)
})

const detailKeyPoints = computed(() => {
  if (!currentArticle.value) return []
  return getKeyPoints(currentArticle.value)
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

function isCardHighlighted(id: string) {
  if (hoveredCardId.value) return hoveredCardId.value === id
  return flowHighlightIds.value.includes(id)
}

function pickRandomFlowCards() {
  const list = sortedArticles.value
  if (!list.length) {
    flowHighlightIds.value = []
    return
  }
  const count = Math.min(5, list.length)
  const shuffled = [...list].sort(() => Math.random() - 0.5)
  flowHighlightIds.value = shuffled.slice(0, count).map((a: any) => a.id)
}

function startFlowAnimation() {
  stopFlowAnimation()
  pickRandomFlowCards()
  flowTimer = setInterval(() => {
    if (hoveredCardId.value) return
    pickRandomFlowCards()
  }, 1500)
}

function stopFlowAnimation() {
  if (flowTimer) {
    clearInterval(flowTimer)
    flowTimer = null
  }
}

watch(sortedArticles, (list) => {
  if (!list.length) {
    flowHighlightIds.value = []
    return
  }
  flowHighlightIds.value = flowHighlightIds.value.filter(id => list.some((a: any) => a.id === id))
  if (flowHighlightIds.value.length === 0) pickRandomFlowCards()
  if (!flowTimer && !listLoading.value) startFlowAnimation()
})

watch(listLoading, (loading) => {
  if (loading) stopFlowAnimation()
  else if (sortedArticles.value.length) startFlowAnimation()
})

// ============ 内容提炼 ============
function addHeadingIds(html: string) {
  return html.replace(/<h([23])>([^<]+)<\/h\1>/g, (_, level: string, text: string) => {
    const id = 'h-' + text.replace(/[^\w\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)
    return `<h${level} id="${id}">${text}</h${level}>`
  })
}

function refineArticleContent(raw: string, title: string) {
  let text = (raw || '').trim()
  if (!text) return ''

  // 去掉与标题重复的 ### 行
  const titleEsc = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  text = text.replace(new RegExp(`^#{1,3}\\s*${titleEsc}\\s*$`, 'm'), '')

  // 清理 HTML 残留
  text = text.replace(/<[^>]+>/g, '')

  // FAQ 纯文本 → 结构化 Markdown
  if (!text.includes('|') && !text.match(/^#{2,3}\s/m)) {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
    const parts: string[] = []
    for (const line of lines) {
      if (/^分类[：:]/.test(line)) {
        parts.push(`> **${line}**`)
      } else if (line.length > 4) {
        parts.push(`**解决方案：** ${line}`)
      }
    }
    if (parts.length) return parts.join('\n\n')
  }

  return text.trim()
}

function cleanKeyPointText(text: string): string {
  return (text || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function getKeyPoints(a: any): string[] {
  const content = a.content || ''
  const points: string[] = []

  const accidentMatch = content.match(/\*\*经典事故\*\*[：:]\s*(.+?)(?:\n|$)/i)
    || content.match(/\|\s*\*\*经典事故\*\*\s*\|\s*(.+?)\s*\|/i)
  if (accidentMatch?.[1]) {
    const val = cleanKeyPointText(accidentMatch[1]).slice(0, 120)
    if (val.length > 4) points.push(`经典事故：${val}`)
  }

  const tableLabels = ['问题现象', '问题原因', '排查步骤', '解决方案', '修复建议', '处理建议', '核心步骤', '预防措施']
  for (const label of tableLabels) {
    const re = new RegExp(`\\*\\*${label}\\*\\*\\s*\\|\\s*(.+?)(?:\\n|$)`, 'i')
    const m = content.match(re)
    if (m?.[1]) {
      const val = cleanKeyPointText(m[1].replace(/\|.*$/, '')).slice(0, 72)
      if (val.length > 4) points.push(`${label}：${val}`)
    }
  }

  if (points.length === 0) {
    const lines = content.split('\n').map((l: string) => l.trim()).filter(Boolean)
    for (const line of lines) {
      if (/^#{1,3}\s/.test(line) || line.startsWith('|') || /^分类[：:]/.test(line)) continue
      const cleaned = cleanKeyPointText(line)
      if (cleaned.length > 6) points.push(cleaned.slice(0, 120))
      if (points.length >= 3) break
    }
  }

  return points.slice(0, 3)
}

function isLiked(a: any) {
  if (a?.liked) return true
  return engagementMap.value[a?.id]?.liked || false
}

function isFavorited(a: any) {
  if (a?.favorited) return true
  return engagementMap.value[a?.id]?.favorited || false
}

function titleEffectClass(a: any) {
  if (!a) return ''
  const liked = isLiked(a)
  const fav = isFavorited(a)
  if (liked && fav) return 'title-rainbow'
  if (liked) return 'title-liked'
  if (fav) return 'title-favorited'
  return ''
}

function applyEngagement(id: string, data: { liked?: boolean; favorited?: boolean; likeCount?: number; favoriteCount?: number }) {
  engagementMap.value[id] = {
    liked: !!data.liked,
    favorited: !!data.favorited,
  }
  const idx = articles.value.findIndex((x: any) => x.id === id)
  if (idx >= 0) {
    articles.value[idx] = {
      ...articles.value[idx],
      liked: data.liked,
      favorited: data.favorited,
      likeCount: data.likeCount,
      favoriteCount: data.favoriteCount,
    }
  }
  if (currentArticle.value?.id === id) {
    currentArticle.value = {
      ...currentArticle.value,
      liked: data.liked,
      favorited: data.favorited,
      likeCount: data.likeCount,
      favoriteCount: data.favoriteCount,
    }
  }
}

async function handleToggleLike(article: any) {
  try {
    const data = await toggleLike(article.id)
    applyEngagement(article.id, data)
    likePop.value = true
    setTimeout(() => { likePop.value = false }, 400)
  } catch { /* ignore */ }
}

async function handleToggleFavorite(article: any) {
  try {
    const data = await toggleFavorite(article.id)
    applyEngagement(article.id, data)
    favPop.value = true
    setTimeout(() => { favPop.value = false }, 400)
  } catch { /* ignore */ }
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

function saveRecent(article: any) {
  try {
    const raw = localStorage.getItem('kb_recent')
    const list: any[] = raw ? JSON.parse(raw) : []
    const filtered = list.filter((a: any) => a.id !== article.id)
    filtered.unshift({ id: article.id, title: article.title, category: article.category })
    localStorage.setItem('kb_recent', JSON.stringify(filtered.slice(0, 10)))
  } catch {}
}

async function loadEngagement() {
  try {
    engagementMap.value = await fetchEngagement()
  } catch {
    engagementMap.value = {}
  }
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

    const data = await fetchArticles(params)
    articles.value = data.items || []
    totalArticles.value = data.total || 0
    for (const a of articles.value) {
      if (a.liked || a.favorited) {
        engagementMap.value[a.id] = { liked: !!a.liked, favorited: !!a.favorited }
      }
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
    const data = await fetchArticle(a.id)
    currentArticle.value = data
    applyEngagement(a.id, data)
    document.body.style.overflow = 'hidden'
    await nextTick()
    observeTocScroll()
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
  const root = modalScrollRef.value
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
    { root: root || null, rootMargin: '-12% 0px -70% 0px' }
  )
  headings.forEach(h => tocObserver!.observe(h))
}

async function resetKnowledge() {
  if (!confirm('确定要清空旧知识库并从文件重新导入吗？此操作不可撤销。')) return
  resetting.value = true
  try {
    const data = await resetKnowledgeApi()
    if (data.code === 0) {
      alert(`知识库已重置！共导入 ${data.data.total} 篇文章`)
      categories.value = await fetchCategories()
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
    categories.value = await fetchCategories()
  } catch (e) {
    console.error('分类加载失败:', e)
  }
  await loadEngagement()
  await search()
  startFlowAnimation()
})

onUnmounted(() => {
  stopFlowAnimation()
})
</script>

<style lang="scss" scoped>
/* ===== 知识花园 · 全页背景 ===== */
.knowledge-garden {
  position: relative;
  min-height: calc(100vh - 56px);
  padding: 28px 28px 40px;
  /* 不可设 overflow:hidden，否则左侧分类栏 position:sticky 失效 */
  overflow: visible;
  background:
    radial-gradient(ellipse 80% 60% at 10% 0%, rgba(167, 243, 208, 0.35), transparent 55%),
    radial-gradient(ellipse 70% 50% at 90% 10%, rgba(186, 230, 253, 0.4), transparent 50%),
    radial-gradient(ellipse 60% 40% at 50% 100%, rgba(221, 214, 254, 0.25), transparent 55%),
    linear-gradient(165deg, #f0fdf4 0%, #f0f9ff 45%, #faf5ff 100%);
}

.ambient {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
  opacity: 0.55;
  animation: ambient-drift 22s ease-in-out infinite alternate;
}
.ambient-a {
  width: 420px; height: 420px;
  top: -80px; left: -60px;
  background: rgba(52, 211, 153, 0.28);
  animation-duration: 26s;
}
.ambient-b {
  width: 360px; height: 360px;
  top: 30%; right: -80px;
  background: rgba(56, 189, 248, 0.22);
  animation-duration: 30s;
  animation-delay: -8s;
}
.ambient-c {
  width: 300px; height: 300px;
  bottom: -40px; left: 35%;
  background: rgba(167, 139, 250, 0.18);
  animation-duration: 24s;
  animation-delay: -14s;
}

.knowledge-layout {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 22px;
  max-width: 1440px;
  margin: 0 auto;
  min-height: calc(100vh - 140px);
}

/* ===== 左侧边栏 · 玻璃态 ===== */
.knowledge-sidebar {
  width: 258px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 8px 32px rgba(15, 118, 110, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  padding: 18px 0;
  position: sticky;
  top: 16px;
  z-index: 2;
  align-self: flex-start;
  max-height: calc(100vh - 56px - 32px);
  overflow-y: auto;
  overscroll-behavior: contain;
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.35); border-radius: 4px; }
}
.sidebar-header {
  padding: 0 16px 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 8px;
}
.sidebar-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #0d9488;
  background: rgba(20, 184, 166, 0.12);
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(20, 184, 166, 0.2);
}
.sidebar-title { font-size: 14px; font-weight: 700; color: #1e293b; flex: 1; }
.sidebar-total { font-size: 11px; color: #94a3b8; width: 100%; margin-top: 2px; }

/* 分类导航 */
.category-nav { padding: 6px 10px; display: flex; flex-direction: column; gap: 3px; }

.cat-group { margin-top: 4px; }
.cat-group-title {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 16px 6px; font-size: 11px; font-weight: 700;
  color: #64748b; letter-spacing: 0.3px;
  border: none; background: none; cursor: pointer; width: 100%; text-align: left;
  &:hover { color: #334155; }
}
.group-count { font-size: 10px; color: #cbd5e1; margin-left: auto; font-weight: 400; }
.collapse-arrow { transition: transform 0.2s; color: #94a3b8; flex-shrink: 0; &.rotated { transform: rotate(90deg); } }

.cat-item {
  display: flex; align-items: center; gap: 10px;
  width: 100%; padding: 9px 10px; border: none; border-radius: 10px;
  background: transparent; cursor: pointer; transition: all 0.2s ease;
  text-align: left; font-size: 13px; color: #475569;
  &:hover { background: rgba(240, 253, 250, 0.85); color: #0f766e; }
  &.active {
    background: linear-gradient(135deg, rgba(204, 251, 241, 0.9), rgba(224, 242, 254, 0.85));
    color: #0d9488; font-weight: 600;
    box-shadow: inset 0 0 0 1px rgba(20, 184, 166, 0.15);
  }
}
.cat-label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-badge {
  font-size: 11px; color: #94a3b8; background: rgba(241, 245, 249, 0.9);
  padding: 2px 8px; border-radius: 10px; flex-shrink: 0;
  .cat-item.active & { background: rgba(20, 184, 166, 0.15); color: #0d9488; }
}

/* 移动端 */
.mobile-cat-toggle { display: none; }
.sidebar-overlay { display: none; }

/* ===== 右侧主内容 ===== */
.knowledge-main {
  flex: 1;
  min-width: 0;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 40px rgba(14, 116, 144, 0.05);
  padding: 24px 26px 28px;
}

.page-hero {
  position: sticky;
  top: 0;
  z-index: 12;
  margin: -24px -26px 16px;
  padding: 20px 26px 16px;
  background:
    linear-gradient(180deg, rgba(240, 253, 250, 0.96) 0%, rgba(255, 255, 255, 0.92) 100%);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.65);
  box-shadow: 0 4px 20px rgba(20, 184, 166, 0.06);
}
.hero-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #0891b2;
  background: rgba(6, 182, 212, 0.1);
  padding: 3px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
}
.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 6px;
  letter-spacing: -0.02em;
}
.hero-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

/* 最近浏览 + 标签 各占一半 */
.meta-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 18px;
  min-height: 148px;
}
.meta-pane {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(226, 232, 240, 0.65);
  border-radius: 14px;
  overflow: hidden;
  transition: box-shadow 0.25s ease;
  &:hover { box-shadow: 0 4px 20px rgba(20, 184, 166, 0.06); }
}
.meta-pane-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.6), transparent);
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}
.meta-pane-tag {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #14b8a6;
  background: rgba(20, 184, 166, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}
.meta-pane-title { font-size: 12px; font-weight: 600; color: #334155; }
.meta-clear {
  margin-left: auto;
  border: none;
  background: none;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  &:hover { color: #0d9488; }
}
.meta-pane-body {
  flex: 1;
  padding: 10px 12px;
  overflow-y: auto;
  max-height: 110px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.3); border-radius: 3px; }
}
.meta-tags .meta-pane-body {
  flex-direction: row;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 6px;
}
.meta-empty {
  font-size: 12px;
  color: #cbd5e1;
  margin: 4px 0;
  font-style: italic;
}
.recent-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 6px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: 12px;
  color: #64748b;
  transition: all 0.15s ease;
  &:hover {
    background: rgba(204, 251, 241, 0.5);
    color: #0d9488;
    .recent-dot { background: #14b8a6; transform: scale(1.3); }
  }
}
.recent-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
  transition: all 0.2s ease;
}
.recent-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.search-row { margin-bottom: 14px; display: flex; align-items: center; gap: 12px; }
.search-box {
  display: flex; align-items: center; gap: 10px; flex: 1;
  background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(226, 232, 240, 0.8); border-radius: 14px;
  padding: 12px 16px; position: relative;
  transition: border-color 0.2s, box-shadow 0.2s;
  &:focus-within { border-color: #14b8a6; box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.1); }
}
.search-input { flex: 1; border: none; outline: none; font-size: 14px; color: #1e293b; &::placeholder { color: #cbd5e1; } }
.search-spinner {
  width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #14b8a6;
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
  &:hover { background: rgba(240, 253, 250, 0.8); color: #0d9488; }
}

/* 工具栏 */
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.sort-group { display: flex; gap: 2px; background: rgba(241, 245, 249, 0.8); border-radius: 10px; padding: 3px; }
.sort-btn {
  padding: 6px 13px; border: none; border-radius: 8px;
  background: transparent; font-size: 12px; color: #64748b; cursor: pointer;
  transition: all 0.15s ease;
  &.active { background: #fff; color: #0d9488; font-weight: 600; box-shadow: 0 1px 4px rgba(20, 184, 166, 0.08); }
}
.result-hint { font-size: 13px; color: #64748b; }

/* 标签（meta-pane 内） */
.hot-tag {
  padding: 4px 11px; border-radius: 14px; border: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.7); font-size: 12px; color: #64748b; cursor: pointer;
  transition: all 0.15s ease;
  &:hover { border-color: #5eead4; color: #0d9488; background: rgba(204, 251, 241, 0.4); }
  &.selected { background: linear-gradient(135deg, #14b8a6, #06b6d4); border-color: transparent; color: #fff; }
}
.chip.active-only {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 14px; background: rgba(204, 251, 241, 0.6); color: #0d9488;
  font-size: 12px; font-weight: 500;
}
.chip-remove { background: none; border: none; font-size: 14px; color: #0d9488; cursor: pointer; padding: 0 2px; }

/* 筛选芯片（保留兼容） */
.filter-chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.chip {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 12px; background: rgba(204, 251, 241, 0.5); color: #0d9488;
  font-size: 12px; font-weight: 500;
}
.chip-clear { background: none; border: none; font-size: 12px; color: #94a3b8; cursor: pointer; }

/* ===== 文章卡片 ===== */
.article-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
  align-items: stretch;
}
.article-card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(226, 232, 240, 0.75);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 248px;
  &::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    opacity: 0; transition: opacity 0.4s ease, height 0.3s ease;
  }
  &.sev-info::before { background: linear-gradient(90deg, #2563eb, #7c3aed, #2563eb); background-size: 200% 100%; }
  &.sev-warning::before { background: linear-gradient(90deg, #f59e0b, #eab308, #f59e0b); background-size: 200% 100%; }
  &.sev-critical::before { background: linear-gradient(90deg, #ef4444, #f97316, #ef4444); background-size: 200% 100%; }

  &.card-active {
    transform: translateY(-2px);
    &::before {
      opacity: 1; height: 4px;
      animation: border-flow 2.4s linear infinite;
    }
  }
  &.card-active.sev-info {
    border-color: rgba(94, 234, 212, 0.6);
    box-shadow: 0 8px 28px rgba(20, 184, 166, 0.12);
  }
  &.card-active.sev-warning {
    border-color: #fcd34d;
    box-shadow: 0 8px 28px rgba(245, 158, 11, 0.14);
  }
  &.card-active.sev-critical {
    border-color: #fca5a5;
    box-shadow: 0 8px 28px rgba(239, 68, 68, 0.14);
  }
}
.card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.card-category { font-size: 11px; color: #94a3b8; }
.new-badge {
  font-size: 10px; font-weight: 700; color: #fff; background: linear-gradient(135deg, #2563eb, #7c3aed);
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
  font-size: 15px; font-weight: 700; color: #1e293b; margin: 0 0 8px;
  line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; transition: color 0.3s;
  min-height: calc(1.45em * 2);
  &.title-liked { color: #f97316; }
  &.title-favorited { color: #eab308; }
  &.title-rainbow {
    background: linear-gradient(90deg, #f97316, #eab308, #22c55e, #3b82f6, #a855f7, #ec4899, #f97316);
    background-size: 300% auto;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: rainbow-shift 4s linear infinite;
  }
}

.card-body {
  flex-shrink: 0;
  height: 118px;
  overflow: hidden;
  margin-bottom: 10px;
}

.card-keypoints {
  margin: 0; padding: 0 0 0 16px; list-style: none;
  max-height: 72px;
  overflow: hidden;
  li {
    position: relative; font-size: 12px; color: #64748b; line-height: 1.55; margin-bottom: 4px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    &::before {
      content: ''; position: absolute; left: -12px; top: 7px;
      width: 5px; height: 5px; border-radius: 50%; background: #93c5fd;
    }
    &:last-child { margin-bottom: 0; }
  }
}

.card-excerpt {
  font-size: 13px; color: #64748b; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden; margin: 0;
  max-height: calc(1.5em * 3);
}

.card-tags {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  min-height: 26px;
  margin-bottom: 10px;
  overflow: hidden;
  &.is-empty { visibility: hidden; }
}

.tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  min-width: 44px;
  max-width: 72px;
  padding: 0 8px;
  box-sizing: border-box;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  border-radius: 6px;
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e8edf3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 0;
}

.card-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  min-height: 34px;
}

.card-stats {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 52px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  &.views { color: #64748b; }
  &.likes { color: #f97316; }
  &.favs { color: #eab308; }
  &.likes.is-active svg, &.favs.is-active svg { filter: drop-shadow(0 0 2px currentColor); }
}

.stat-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  svg { display: block; }
}

.stat-num {
  min-width: 18px;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.card-time {
  flex-shrink: 0;
  margin-left: auto;
  font-size: 11px;
  color: #cbd5e1;
  white-space: nowrap;
  text-align: right;
}
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
  position: fixed; inset: 0; background: rgba(15,23,42,0.5);
  backdrop-filter: blur(6px); z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.modal-card {
  background: #fff; border-radius: 20px;
  width: 920px; max-height: 92vh;
  display: flex; flex-direction: column; overflow: hidden;
  position: relative; box-shadow: 0 25px 80px rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.8);
  &.modal-sev-critical { border-top: 4px solid #ef4444; }
  &.modal-sev-warning { border-top: 4px solid #f59e0b; }
  &.modal-sev-info { border-top: 4px solid #2563eb; }
}

.modal-sticky-top {
  position: sticky; top: 0; z-index: 20; flex-shrink: 0;
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 14px 32px 12px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #f1f5f9;
  border-radius: 20px 20px 0 0;
}

.modal-scroll-body {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 16px 32px 28px;
}

.modal-close {
  flex-shrink: 0;
  background: #f8fafc; border: 1px solid #e2e8f0;
  font-size: 22px; color: #64748b; cursor: pointer; width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center; border-radius: 10px;
  &:hover { color: #1e293b; background: #f1f5f9; }
}

.modal-breadcrumb {
  flex: 1; min-width: 0;
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; flex-wrap: wrap; padding-right: 8px;
}
.crumb { color: #2563eb; cursor: pointer; &:hover { text-decoration: underline; } &.active { color: #94a3b8; cursor: default; &:hover { text-decoration: none; } } }
.crumb-sep { color: #cbd5e1; }

.modal-hero {
  padding: 16px 18px; border-radius: 14px; margin-bottom: 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #faf5ff 50%, #fff7ed 100%);
  border: 1px solid #e0e7ff;
}
.modal-layout { display: flex; gap: 24px; }
.modal-body { flex: 1; min-width: 0; }
.modal-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.modal-title {
  font-size: 22px; font-weight: 800; color: #1e293b; margin: 4px 0 10px; line-height: 1.4;
  transition: all 0.35s;
  &.title-liked { color: #f97316; }
  &.title-favorited { color: #eab308; }
  &.title-rainbow {
    background: linear-gradient(90deg, #f97316, #eab308, #22c55e, #3b82f6, #a855f7, #ec4899, #f97316);
    background-size: 300% auto;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: rainbow-shift 4s linear infinite;
  }
}

.modal-stats-bar {
  display: flex; gap: 16px; margin-top: 10px;
}
.hero-stat {
  font-size: 12px; color: #64748b;
  strong { font-size: 16px; font-weight: 800; color: #1e293b; margin-right: 2px; }
  &.likes strong { color: #f97316; }
  &.favs strong { color: #eab308; }
}

.modal-actions { display: flex; gap: 8px; margin: 0 0 14px; flex-wrap: wrap; }
.act-btn {
  display: flex; align-items: center; gap: 5px; padding: 7px 14px;
  border: 1px solid #e2e8f0; border-radius: 10px; background: #fff;
  font-size: 12px; font-weight: 600; color: #64748b; cursor: pointer;
  transition: all 0.2s;
  &:hover { border-color: #2563eb; color: #2563eb; background: #f8faff; }
  &.like-btn.active {
    color: #fff; background: linear-gradient(135deg, #f97316, #fb923c);
    border-color: #f97316; box-shadow: 0 4px 14px rgba(249,115,22,0.35);
  }
  &.fav-btn.active {
    color: #fff; background: linear-gradient(135deg, #eab308, #fbbf24);
    border-color: #eab308; box-shadow: 0 4px 14px rgba(234,179,8,0.35);
  }
  &.pop { animation: btn-pop 0.35s ease; }
}
.act-count {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  background: rgba(0,0,0,0.06); margin-left: 2px;
  .active & { background: rgba(255,255,255,0.25); }
}

.detail-highlights {
  margin-bottom: 16px; padding: 14px 16px; border-radius: 12px;
  background: linear-gradient(135deg, #f0fdf4, #eff6ff);
  border: 1px solid #bbf7d0;
}
.highlights-title {
  margin: 0 0 8px; font-size: 12px; font-weight: 700; color: #059669;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.detail-highlights ul {
  margin: 0; padding: 0; list-style: none;
  li {
    position: relative; font-size: 13px; color: #334155; line-height: 1.65;
    margin-bottom: 8px; padding-left: 14px;
    &::before {
      content: ''; position: absolute; left: 0; top: 8px;
      width: 6px; height: 6px; border-radius: 50%;
      background: linear-gradient(135deg, #059669, #2563eb);
    }
  }
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
  margin-top: 8px; font-size: 14px; color: #334155; line-height: 1.85;
  :deep(h2) {
    font-size: 17px; margin: 22px 0 10px; color: #1e293b;
    border-bottom: 2px solid transparent;
    border-image: linear-gradient(90deg, #2563eb, #7c3aed, transparent) 1;
    padding-bottom: 6px; scroll-margin-top: 20px;
  }
  :deep(h3) { font-size: 15px; margin: 16px 0 8px; color: #4338ca; scroll-margin-top: 20px; }
  :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
  :deep(th) { background: linear-gradient(135deg, #eff6ff, #ede9fe); padding: 10px 14px; text-align: left; font-weight: 700; border: 1px solid #e2e8f0; color: #4338ca; }
  :deep(td) { padding: 10px 14px; border: 1px solid #e2e8f0; vertical-align: top; }
  :deep(tr:nth-child(even) td) { background: #fafbfc; }
  :deep(tr:hover td) { background: #f0f9ff; }
  :deep(ul) { padding-left: 20px; }
  :deep(li) { margin: 4px 0; }
  :deep(li::marker) { color: #2563eb; }
  :deep(code) { font-family: 'JetBrains Mono', monospace; background: #eff6ff; padding: 2px 7px; border-radius: 5px; font-size: 12px; color: #2563eb; border: 1px solid #dbeafe; }
  :deep(pre) { background: linear-gradient(135deg, #0f172a, #1e293b); color: #e2e8f0; padding: 14px 18px; border-radius: 10px; overflow-x: auto; font-size: 13px; border: none; }
  :deep(pre code) { background: none; border: none; color: inherit; padding: 0; }
  :deep(strong) { color: #1e293b; font-weight: 700; }
  :deep(blockquote) {
    border-left: 4px solid #2563eb; padding: 10px 16px; margin: 12px 0;
    background: linear-gradient(90deg, #eff6ff, transparent); color: #475569; border-radius: 0 8px 8px 0;
  }
  :deep(p) { margin: 8px 0; }
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
@keyframes ambient-drift {
  0% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(24px, -18px) scale(1.05); }
  100% { transform: translate(-16px, 12px) scale(0.98); }
}
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
@keyframes border-flow {
  0% { background-position: 0% center; }
  100% { background-position: 200% center; }
}
@keyframes rainbow-shift {
  0% { background-position: 0% center; }
  100% { background-position: 300% center; }
}
@keyframes btn-pop {
  0% { transform: scale(1); }
  40% { transform: scale(1.12); }
  100% { transform: scale(1); }
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .knowledge-garden { padding: 16px 14px 28px; }
  .knowledge-main { padding: 18px 16px 22px; border-radius: 16px; }
  .page-hero {
    margin: -18px -16px 14px;
    padding: 16px 16px 14px;
  }
  .meta-split { grid-template-columns: 1fr; min-height: auto; }
  .meta-pane-body { max-height: 96px; }
  .knowledge-layout { flex-direction: column; gap: 0; }
  .knowledge-sidebar {
    position: fixed; left: -280px; top: 0; bottom: 0; z-index: 200;
    width: 270px; border-radius: 0; max-height: 100vh;
    transition: left 0.3s ease;
    &.mobile-open { left: 0; }
  }
  .sidebar-overlay {
    display: block; position: fixed; inset: 0; z-index: 199;
    background: rgba(15, 23, 42, 0.25);
    backdrop-filter: blur(2px);
  }
  .mobile-cat-toggle {
    display: flex; align-items: center; justify-content: space-between;
    width: 100%; padding: 10px 16px;
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.85);
    font-size: 14px; color: #1e293b;
    margin-bottom: 12px;
  }

  .article-grid { grid-template-columns: 1fr; }
  .modal-layout { flex-direction: column; }
  .modal-toc { display: none; }
  .modal-card { width: 100%; border-radius: 0; max-height: 100vh; }
  .modal-sticky-top { border-radius: 0; padding: 12px 16px 10px; }
  .modal-scroll-body { padding: 12px 16px 20px; }
  .modal-breadcrumb { flex-wrap: wrap; }
  .toolbar-left { flex-wrap: wrap; gap: 8px; }
  .search-row { flex-wrap: wrap; }
  .modal-footer-nav { flex-direction: column; }
  .nav-article-btn { max-width: 100%; }
}

@media (max-width: 640px) {
  .modal-sticky-top { padding: 10px 12px 8px; }
  .modal-scroll-body { padding: 10px 12px 16px; }
  .modal-title { font-size: 17px; }
  .sort-group { width: 100%; justify-content: space-between; }
}
</style>
