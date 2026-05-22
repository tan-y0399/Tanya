<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2 class="page-title">知识库</h2>
      <p class="page-desc">运维知识沉淀 · 故障案例检索 · RAG 智能匹配</p>
    </div>

    <!-- 搜索 + 分类 -->
    <div class="search-row">
      <div class="search-box">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="5.5" stroke="#94a3b8" stroke-width="1.5"/>
          <path d="M11 11l4 4" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input v-model="keyword" class="search-input" placeholder="搜索知识库..." @keyup.enter="search"/>
      </div>
      <div class="category-tabs">
        <button class="cat-btn" :class="{ active: !category }" @click="category = ''; search()">全部</button>
        <button class="cat-btn" v-for="c in categories" :key="c.name" :class="{ active: category === c.name }" @click="category = c.name; search()">
          {{ c.name }} <span class="cat-count">{{ c.count }}</span>
        </button>
      </div>
    </div>

    <!-- 文章列表 -->
    <div class="article-grid">
      <div class="article-card" v-for="a in articles" :key="a.id" @click="openArticle(a)">
        <div class="article-head">
          <span class="risk-tag" :class="`l${a.severity === 'critical' ? '3' : a.severity === 'warning' ? '2' : '1'}`">
            {{ a.severity === 'critical' ? '紧急' : a.severity === 'warning' ? '注意' : '参考' }}
          </span>
          <span class="article-cat">{{ a.category }}</span>
        </div>
        <h5 class="article-title">{{ a.title }}</h5>
        <div class="article-tags">
          <span class="tag" v-for="t in a.tags" :key="t">{{ t }}</span>
        </div>
        <div class="article-foot">
          <span>{{ a.viewCount }} 次查看</span>
          <span>{{ formatTime(a.updatedAt) }}</span>
        </div>
      </div>
    </div>

    <div class="empty" v-if="!articles.length">暂无知识文章</div>

    <!-- 详情弹窗 -->
    <teleport to="body">
      <div class="modal-overlay" v-if="currentArticle" @click.self="currentArticle = null">
        <div class="modal-card" @click.stop>
          <button class="modal-close" @click="currentArticle = null">&times;</button>
          <div class="article-head">
            <span class="risk-tag" :class="`l${currentArticle.severity === 'critical' ? '3' : currentArticle.severity === 'warning' ? '2' : '1'}`">
              {{ currentArticle.severity === 'critical' ? '紧急' : currentArticle.severity === 'warning' ? '注意' : '参考' }}
            </span>
            <span class="article-cat">{{ currentArticle.category }}</span>
          </div>
          <h3 class="article-detail-title">{{ currentArticle.title }}</h3>
          <div class="article-tags">
            <span class="tag" v-for="t in currentArticle.tags" :key="t">{{ t }}</span>
          </div>
          <div class="article-content markdown-body" v-html="renderedContent"></div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import api from '@/api/index'
import { formatTime } from '@/utils'

const md = new MarkdownIt({ breaks: true })
const keyword = ref('')
const category = ref('')
const articles = ref([] as any[])
const categories = ref([] as any[])
const currentArticle = ref(null as any)

const renderedContent = computed(() => currentArticle.value ? md.render(currentArticle.value.content) : '')

async function search() {
  try {
    const params: any = { page: 1, size: 50 }
    if (category.value) params.category = category.value
    if (keyword.value) params.keyword = keyword.value
    const { data } = await api.get('/knowledge/articles', { params })
    if (data.code === 0) articles.value = data.data.items || []
  } catch {}
}

async function openArticle(a: any) {
  try {
    const { data } = await api.get(`/knowledge/articles/${a.id}`)
    if (data.code === 0) currentArticle.value = data.data
  } catch {}
}

onMounted(async () => {
  try {
    const { data } = await api.get('/knowledge/categories')
    if (data.code === 0) categories.value = data.data
  } catch {}
  await search()
})
</script>

<style lang="scss" scoped>
.knowledge-page { max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 20px; .page-title { font-size: 20px; font-weight: 700; color: #1e293b; } .page-desc { font-size: 13px; color: #94a3b8; } }

.search-row { margin-bottom: 16px; }
.search-box {
  display: flex; align-items: center; gap: 8px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 10px 16px; margin-bottom: 12px;
  &:focus-within { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.06); }
}
.search-input { flex: 1; border: none; outline: none; font-size: 14px; color: #1e293b; &::placeholder { color: #cbd5e1; } }

.category-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.cat-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid #e2e8f0;
  background: #fff; font-size: 12px; color: #64748b; cursor: pointer;
  transition: all 0.15s;
  &:hover { border-color: #2563eb; color: #2563eb; }
  &.active { background: #eff6ff; border-color: #2563eb; color: #2563eb; font-weight: 500; }
}
.cat-count { color: #94a3b8; margin-left: 2px; } .cat-btn.active .cat-count { color: #2563eb; }

.article-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.article-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px;
  cursor: pointer; transition: all 0.2s;
  &:hover { border-color: #2563eb; box-shadow: 0 4px 16px rgba(0,0,0,0.04); transform: translateY(-2px); }
}
.article-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.article-cat { font-size: 11px; color: #94a3b8; }
.article-title { font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 8px; line-height: 1.4; }
.article-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
.tag { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: #f1f5f9; color: #64748b; }
.article-foot { display: flex; gap: 12px; font-size: 11px; color: #94a3b8; }

.empty { text-align: center; padding: 60px; color: #94a3b8; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(15,23,42,0.4);
  backdrop-filter: blur(4px); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.modal-card {
  background: #fff; border-radius: 16px; padding: 32px;
  width: 700px; max-height: 80vh; overflow-y: auto;
  position: relative; box-shadow: 0 20px 60px rgba(0,0,0,0.12);
}
.modal-close {
  position: absolute; top: 12px; right: 12px; background: none; border: none;
  font-size: 24px; color: #94a3b8; cursor: pointer;
  &:hover { color: #1e293b; }
}
.article-detail-title { font-size: 22px; font-weight: 700; color: #1e293b; margin: 12px 0 10px; }
.article-content {
  margin-top: 16px; font-size: 14px; color: #1e293b; line-height: 1.8;
  :deep(h2) { font-size: 16px; margin: 16px 0 8px; color: #1e293b; }
  :deep(h3) { font-size: 14px; margin: 12px 0 6px; color: #334155; }
  :deep(ul) { padding-left: 20px; }
  :deep(li) { margin: 4px 0; }
  :deep(code) { font-family: 'JetBrains Mono', monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #2563eb; }
  :deep(strong) { color: #1e293b; }
}
</style>
