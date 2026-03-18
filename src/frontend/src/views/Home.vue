<template>
  <div class="app-container">
    <!-- ========== 顶部导航栏 ========== -->
    <header class="app-header">
      <div class="header-inner">
        <div class="header-brand">
          <svg class="brand-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
            <line x1="7" y1="2" x2="7" y2="22" />
            <line x1="17" y1="2" x2="17" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <line x1="2" y1="7" x2="7" y2="7" />
            <line x1="2" y1="17" x2="7" y2="17" />
            <line x1="17" y1="7" x2="22" y2="7" />
            <line x1="17" y1="17" x2="22" y2="17" />
          </svg>
          <h1 class="brand-title">MovieRec</h1>
          <span class="brand-tag">NeuMF Engine</span>
        </div>

        <div class="header-controls">
          <div class="user-info">
            <span class="username">{{ userStore.user?.username }} (ID: {{ userId }})</span>
            <button @click="handleLogout" class="ml-4 text-sm text-[#9a9ab0] hover:text-white transition-colors underline">登出</button>
          </div>
        </div>
      </div>
    </header>

    <!-- ========== 主内容区域 ========== -->
    <main class="app-main">
      <!-- 错误提示 -->
      <div v-if="hasError" class="error-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <span>{{ errorMessage }}</span>
        <button @click="loadRecommendations">重试</button>
      </div>

      <!-- 当前选择的类型 -->
      <div v-if="selectedGenre" class="filter-status">
        <span>正在查看: <strong>{{ selectedGenre }}</strong> 推荐</span>
        <button @click="handleGenreSelect('')" class="clear-filter">清除筛选</button>
      </div>

      <!-- 骨架屏加载态 -->
      <div v-if="isLoading" class="movie-grid">
        <SkeletonCard v-for="i in 12" :key="'sk-' + i" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="displayMovies.length === 0 && !hasError" class="empty-state">
        <div class="empty-state-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
            <line x1="7" y1="2" x2="7" y2="22" />
            <line x1="17" y1="2" x2="17" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
          </svg>
        </div>
        <h2>暂无相关电影</h2>
        <p>尝试选择其他类型或刷新页面</p>
      </div>

      <!-- 电影卡片网格 -->
      <div v-else class="movie-grid">
        <transition-group name="card-enter">
          <MovieCard
            v-for="(movie, index) in displayMovies"
            :key="movie.movieId"
            :movie="movie"
            :style="{ animationDelay: `${index * 50}ms` }"
            @click="onMovieClick"
            @dislike="onMovieDislike"
          />
        </transition-group>
      </div>
    </main>

    <!-- ========== 底部信息栏 ========== -->
    <footer class="app-footer">
      <p>MovieRec-NNCF &middot; 基于 NeuMF 神经矩阵分解的工业级推荐引擎</p>
    </footer>

    <!-- ========== 底部类型挑选 Dock 栏 ========== -->
    <section class="dock-section" v-if="genreItems.length > 0">
      <div class="gallery-container">
        <CircularGallery
          :items="genreItems"
          :bend="3"
          text-color="#ffffff"
          :border-radius="0.05"
          font="bold 20px Figtree"
          :scroll-speed="2"
          :scroll-ease="0.05"
          @select="handleGenreSelect"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import MovieCard from '../components/MovieCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import CircularGallery from '../components/CircularGallery.vue'
import { useRecommendations } from '../composables/useRecommendations'
import { useDebounce } from '../composables/useDebounce'
import { useUserStore } from '../stores/user'
import { fetchWithAuth } from '../api/fetch'
import type { FeedbackPayload } from '../types'

const router = useRouter()
const userStore = useUserStore()
const userId = computed(() => userStore.userId)

const genres = ref<string[]>([])
const selectedGenre = ref('')

const {
  movies,
  isLoading,
  hasError,
  errorMessage,
  fetchRecommendations,
  sendFeedback,
} = useRecommendations()

const { debounce } = useDebounce()

const displayMovies = computed(() => {
  if (!selectedGenre.value) return movies.value
  return movies.value.filter(m => m.genres.includes(selectedGenre.value))
})

const genreItems = computed(() => {
  return genres.value.map((genre) => ({
    text: genre,
    image: `https://picsum.photos/seed/${genre}/800/600`
  }))
})

onMounted(async () => {
  // 获取所有类别
  try {
    const res = await fetchWithAuth('/api/movies/genres')
    if (res.code === 200) {
      genres.value = res.genres
    }
  } catch (err) {
    console.error('Failed to fetch genres:', err)
  }

  // 自动获取推荐
  loadRecommendations()
})

const loadRecommendations = () => {
  if (userId.value !== null) {
    fetchRecommendations(userId.value)
  }
}

// 监听用户变动自动刷新
watch(() => userId.value, (newId) => {
  if (newId !== null) {
    loadRecommendations()
  }
})

const handleGenreSelect = (genre: string) => {
  selectedGenre.value = genre
}

const buildPayload = (movieId: number, actionType: FeedbackPayload['actionType']): FeedbackPayload => ({
  userId: userId.value || 0,
  movieId,
  actionType,
  timestamp: Date.now(),
})

const debouncedFeedback = debounce((payload: FeedbackPayload) => {
  sendFeedback(payload)
}, 600)

const onMovieClick = (movieId: number) => {
  debouncedFeedback(buildPayload(movieId, 'click'))
}

const onMovieDislike = (movieId: number) => {
  debouncedFeedback(buildPayload(movieId, 'dislike'))
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
/* ========== 布局 ========== */
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--color-bg-primary);
  padding-bottom: 320px; /* 为增高的底部的 Dock 栏留出完美空间 */
}

/* ========== 顶部导航栏 ========== */
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(10, 10, 15, 0.82);
  backdrop-filter: blur(16px) saturate(180%);
}

.app-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(124, 92, 252, 0.3), transparent);
}

.header-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 14px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  color: var(--color-accent);
  transition: transform var(--transition-normal);
}

.header-brand:hover .brand-icon {
  transform: rotate(15deg) scale(1.1);
}

.brand-title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #fff 0%, #a463ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-tag {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-accent-light);
  background: var(--color-accent-glow);
  padding: 2px 10px;
  border-radius: 20px;
  letter-spacing: 0.03em;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.username {
  font-size: 14px;
  color: var(--color-text-secondary);
}

/* ========== 底部类型挑选 Dock 栏 ========== */
.dock-section {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100; /* 高于主体内容，创造抽屉感 */
  display: flex;
  justify-content: center;
  pointer-events: none; /* 让空白处可以点击到底部内容 */
  background: linear-gradient(to top, rgba(10, 10, 15, 0.95) 0%, rgba(10, 10, 15, 0) 100%);
  padding-bottom: 20px;
}

.dock-section .gallery-container {
  height: 280px; /* 显著提升容器高度以容纳文字和 3 弯曲度的布局 */
  width: 100%;
  max-width: 1440px;
  pointer-events: auto; /* 重新启用画廊的交互 */
  background: transparent;
  border: none;
  overflow: hidden;
}

/* ========== 筛选状态 ========== */
.filter-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding: 8px 16px;
  background: rgba(124, 92, 252, 0.1);
  border: 1px solid rgba(124, 92, 252, 0.2);
  border-radius: 20px;
  width: fit-content;
  font-size: 14px;
  color: var(--color-text-primary);
}

.clear-filter {
  color: var(--color-accent);
  text-decoration: underline;
  cursor: pointer;
  font-weight: 500;
}

/* ========== 主内容 ========== */
.app-main {
  flex: 1;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
  padding: 32px;
}

/* 卡片网格 */
.movie-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 24px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 120px 32px;
  color: var(--color-text-muted);
  position: relative;
}

.empty-state-icon {
  margin-bottom: 24px;
  color: var(--color-accent);
  opacity: 0.8;
}

.empty-state h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

/* 错误横幅 */
.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  margin-bottom: 24px;
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: var(--radius-md);
  color: var(--color-danger);
  font-size: 14px;
}

/* ========== 底部 ========== */
.app-footer {
  padding: 32px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-muted);
  position: relative;
}

/* ========== 动画 ========== */
.card-enter-enter-active {
  animation: cardIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ========== 响应式 ========== */
@media (max-width: 768px) {
  .header-inner {
    padding: 12px 16px;
  }

  .app-main {
    padding: 20px 16px;
  }

  .movie-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 16px;
  }
}
</style>
