<template>
  <div class="app-container">
    <!-- ========== 顶部导航栏 ========== -->
    <CardNav
      :logo="logoSvg"
      logoAlt="MovieRec Logo"
      :items="navItems"
      baseColor="rgba(10, 10, 15, 0.82)"
      menuColor="#fff"
      buttonBgColor="#7c5cfc"
      buttonTextColor="#fff"
      ease="power3.out"
    >
      <template #button>
        <div class="user-info hidden md:flex items-center gap-4 h-full">
          <span class="username text-sm text-[#9a9ab0]">{{ userStore.user?.username }} (ID: {{ userId }})</span>
          <button @click="handleLogout" class="px-4 py-2 border-0 rounded-[calc(0.75rem-0.2rem)] h-full font-medium transition-colors duration-300 cursor-pointer hover:bg-[#6a4ae0]" style="background-color: #7c5cfc; color: #fff;">登出</button>
        </div>
      </template>
    </CardNav>

    <!-- ========== 主内容区域 ========== -->
    <main class="app-main">
      <!-- 错误提示 -->
      <div v-if="hasError && (pageType === 'popular' || pageType === 'personalized' || pageType === 'all-movies')" class="error-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <span>{{ errorMessage }}</span>
        <button @click="() => loadData(false)">重试</button>
      </div>

      <!-- 当前选择的类型 -->
      <div v-if="selectedGenre" class="filter-status">
        <span>正在查看: <strong>{{ genreMap[selectedGenre] || selectedGenre }}</strong> 推荐</span>
        <button @click="handleGenreSelect('')" class="clear-filter">清除筛选</button>
      </div>

      <!-- 骨架屏加载态 -->
      <div v-if="isLoading && (pageType === 'popular' || pageType === 'personalized' || pageType === 'all-movies')" class="movie-grid">
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

      <!-- 操作栏 -->
      <div v-if="pageType === 'popular' && !isLoading && !hasError && displayMovies.length > 0" class="action-bar">
        <button @click="() => loadData(false)" class="refresh-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          换一批
        </button>
      </div>

      <!-- 电影卡片网格 -->
      <div v-if="!isLoading && !hasError && displayMovies.length > 0" class="movie-grid">
        <transition-group name="card-enter">
          <MovieCard
            v-for="(movie, index) in displayMovies"
            :key="`${movie.movieId}-${index}`"
            :movie="movie"
            :style="{ animationDelay: `${(index % 20) * 50}ms` }"
            @click="onMovieClick"
            @dislike="onMovieDislike"
            @rate="onMovieRate"
          />
        </transition-group>
      </div>

      <!-- 底部加载触发器 (全量电影可用) -->
      <div 
        ref="loadMoreTrigger" 
        class="load-more-trigger" 
        v-show="pageType === 'all-movies' && !isLoading && !hasError && displayMovies.length > 0"
      >
        <div v-if="isFetchingMore" class="loading-spinner"></div>
        <span v-if="isFetchingMore">加载更多中...</span>
      </div>
    </main>


    <!-- ========== 底部类型挑选 Dock 栏 ========== -->
    <section class="dock-section" v-if="(pageType === 'popular' || pageType === 'personalized' || pageType === 'all-movies') && genreItems.length > 0">
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
import { ref, onMounted, onUnmounted, computed, watch, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MovieCard from '../components/MovieCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import CircularGallery from '../components/CircularGallery.vue'
import CardNav from '../components/CardNav.vue'
import logoSvg from '../assets/logo.svg'
import { useRecommendations } from '../composables/useRecommendations'
import { useDebounce } from '../composables/useDebounce'
import { useUserStore } from '../stores/user'
import { useHistoryStore } from '../stores/history'
import { fetchWithAuth } from '../api/fetch'
import type { FeedbackPayload, Movie } from '../types'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const historyStore = useHistoryStore()
const userId = computed(() => userStore.userId)

const genres = ref<string[]>([])
const selectedGenre = ref('')

const currentPage = ref(0)
const isFetchingMore = ref(false)
const observer = ref<IntersectionObserver | null>(null)
const loadMoreTrigger = useTemplateRef<HTMLElement>('loadMoreTrigger')

// 基于同构页面和路由区分页面类型
const pageType = computed(() => route.name as string)

const genreMap: Record<string, string> = {
  Action: '动作',
  Adventure: '冒险',
  Animation: '动画',
  Children: '儿童',
  Comedy: '喜剧',
  Crime: '犯罪',
  Documentary: '纪录',
  Drama: '剧情',
  Fantasy: '奇幻',
  'Film-Noir': '黑色电影',
  Horror: '恐怖',
  IMAX: 'IMAX',
  Musical: '音乐',
  Mystery: '悬疑',
  Romance: '爱情',
  'Sci-Fi': '科幻',
  Thriller: '惊悚',
  War: '战争',
  Western: '西部',
  '(no genres listed)': '未分类'
}

const navItems = [
  {
    label: "探索",
    bgColor: "#0D0716",
    textColor: "#fff",
    links: [
      { label: "热门推荐", href: "/popular", ariaLabel: "热门推荐电影" },
      { label: "为你推荐", href: "/personalized", ariaLabel: "个性化推荐电影" },
      { label: "全部电影", href: "/all", ariaLabel: "全部电影列表" }
    ]
  },
  {
    label: "历史",
    bgColor: "#170D27",
    textColor: "#fff",
    links: [
      { label: "浏览历史", href: "/history/browsing", ariaLabel: "浏览历史" },
      { label: "评分历史", href: "/history/rating", ariaLabel: "评分历史" }
    ]
  },
  {
    label: "我的",
    bgColor: "#271E37",
    textColor: "#fff",
    links: [
      { label: "个人主页", href: "/profile", ariaLabel: "用户主页" }
    ]
  }
]

const imdbLinks = ref<Record<string, string>>({})

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
  let sourceMovies: Movie[] = [];
  if (pageType.value === 'popular' || pageType.value === 'personalized' || pageType.value === 'all-movies') {
    sourceMovies = movies.value;
  } else if (pageType.value === 'browsing-history') {
    sourceMovies = historyStore.browsingHistory;
  } else if (pageType.value === 'rating-history') {
    sourceMovies = historyStore.ratingHistory;
  }

  if (!selectedGenre.value) return sourceMovies
  return sourceMovies.filter(m => m.genres.includes(selectedGenre.value))
})

const genreImages = import.meta.glob('../assets/genres/*.jpg', { eager: true, as: 'url' }) as Record<string, string>

const getGenreImage = (genre: string) => {
  const path = `../assets/genres/${genre}.jpg`
  return genreImages[path] || `https://picsum.photos/seed/${genre}/800/600`
}

const genreItems = computed(() => {
  return genres.value.map((genre) => ({
    text: genreMap[genre] || genre,
    value: genre,
    image: getGenreImage(genre)
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
  loadData()

  // 预加载 IMDB 链接字典以实现跳转
  try {
    const linksRes = await fetch('/imdb_links.json')
    if (linksRes.ok) {
      imdbLinks.value = await linksRes.json()
    }
  } catch (err) {
    console.error('Failed to load IMDB links:', err)
  }

  // 挂载无限滚动监听器
  observer.value = new IntersectionObserver((entries) => {
    if (entries[0]?.isIntersecting && pageType.value === 'all-movies' && !isFetchingMore.value && !isLoading.value) {
      currentPage.value++
      loadData(true)
    }
  }, { rootMargin: '400px' })

  if (loadMoreTrigger.value) {
    observer.value.observe(loadMoreTrigger.value)
  }
})

onUnmounted(() => {
  if (observer.value) {
    observer.value.disconnect()
  }
})

const loadData = (append = false) => {
  if (!append) {
    currentPage.value = 0
  }

  if (pageType.value === 'popular') {
    if (userId.value !== null) {
      fetchRecommendations(userId.value, 'popular', 0, append)
    }
  } else if (pageType.value === 'personalized') {
    if (userId.value !== null) {
      fetchRecommendations(userId.value, 'personalized', 0, append)
    }
  } else if (pageType.value === 'all-movies') {
    if (userId.value !== null) {
      isFetchingMore.value = true
      fetchRecommendations(userId.value, 'all', currentPage.value, append)
    }
  }
  // history views dont need to fetch from backend
}

// 监听加载状态，收尾无限滚动状态
watch(isLoading, (newLoading) => {
  if (!newLoading) {
    isFetchingMore.value = false
  }
})

// 监听用户变动或路由变动自动刷新
watch([() => userId.value, () => pageType.value], ([newId]) => {
  if (newId !== null) {
    loadData(false)
  }
}, { immediate: true })

// 监听后端返回的电影列表，将本地缓存的历史评分强制合并到全量/热门列表中，实现全局评分显示
watch(() => movies.value, (newMovies) => {
  if (newMovies && newMovies.length > 0) {
    newMovies.forEach(movie => {
      // 只要本地有过打分记录，优先显示本地打分
      const historical = historyStore.ratingHistory.find(r => r.movieId === movie.movieId)
      if (historical && historical.rating) {
        movie.rating = historical.rating
      }
    })
  }
}, { deep: true })

const handleGenreSelect = (genre: string) => {
  selectedGenre.value = genre
}

const buildPayload = (movieId: number, actionType: FeedbackPayload['actionType'], rating?: number): FeedbackPayload => {
  const payload: FeedbackPayload = {
    userId: userId.value || 0,
    movieId,
    actionType,
    timestamp: Date.now(),
  }
  if (rating !== undefined) {
    payload.rating = rating
  }
  return payload
}

const debouncedFeedback = debounce((payload: FeedbackPayload) => {
  sendFeedback(payload)
}, 600)

const onMovieClick = (movieId: number) => {
  const movie = displayMovies.value.find(m => m.movieId === movieId)
  if (movie) {
    historyStore.addBrowsingHistory(movie)
  }

  debouncedFeedback(buildPayload(movieId, 'click'))
  
  const imdbId = imdbLinks.value[movieId.toString()]
  if (imdbId) {
    window.open(`https://www.imdb.com/title/tt${imdbId}`, '_blank', 'noopener,noreferrer')
  }
}

const onMovieDislike = (movieId: number) => {
  const movie = displayMovies.value.find(m => m.movieId === movieId)
  if (movie && (pageType.value !== 'rating-history')) {
    historyStore.addRatingHistory(movie)
  }

  debouncedFeedback(buildPayload(movieId, 'dislike'))
}

const onMovieRate = (movieId: number, rating: number) => {
  const movie = displayMovies.value.find(m => m.movieId === movieId)
  if (movie) {
    movie.rating = rating // Update rating locally
    if (pageType.value !== 'rating-history') {
      historyStore.addRatingHistory(movie)
    }
  }

  debouncedFeedback(buildPayload(movieId, 'rate', rating))
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
  padding-bottom: 250px; /* 调整为半收起状态所需留白 */
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
  height: 420px; /* 增加容器高度以容纳 16:9 的竖直海报和文字 */
  width: 100%;
  max-width: 1440px;
  pointer-events: auto; /* 重新启用画廊的交互 */
  background: transparent;
  border: none;
  overflow: hidden;
  transform: translateY(240px); /* 默认收起超出的一半多，形成抽屉感 */
  transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: transform;
}

/* 悬停抽屉拉起效果 */
.dock-section .gallery-container:hover,
.dock-section .gallery-container:focus-within,
.dock-section .gallery-container:active {
  transform: translateY(0);
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
  padding-top: 100px; /* offset for absolute cardnav */
}

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 24px;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: 20px;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-weight: 500;
  font-size: 14px;
}

.refresh-btn:hover {
  background: var(--color-accent-glow);
  border-color: var(--color-accent);
  color: var(--color-accent-light);
}

.refresh-btn svg {
  transition: transform 0.5s ease;
}

.refresh-btn:hover svg {
  transform: rotate(180deg);
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

/* ========== 无限滚动触发器 ========== */
.load-more-trigger {
  width: 100%;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  font-size: 14px;
  gap: 12px;
  margin-top: 24px;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(124, 92, 252, 0.3);
  border-top-color: #7c5cfc;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
