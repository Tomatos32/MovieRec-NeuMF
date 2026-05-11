<template>
  <div class="app-container">
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
          <span class="username text-sm text-[#9a9ab0]">欢迎你，{{ userStore.user?.username }}</span>
        </div>
      </template>
    </CardNav>

    <main class="app-main profile-page">
      <div class="profile-card">
        <div class="avatar">
          <span>{{ userStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</span>
        </div>
        <h2>{{ userStore.user?.username }}</h2>
        <p class="user-id">User ID: {{ userStore.userId }}</p>

        <div class="stats">
          <div class="stat-box">
            <span class="value">{{ historyStore.browsingHistory.length }}</span>
            <span class="label">已浏览</span>
          </div>
          <div class="stat-box">
            <span class="value">{{ historyStore.ratingHistory.length }}</span>
            <span class="label">已打分</span>
          </div>
          <div class="stat-box">
            <span class="value">{{ favoriteGenre }}</span>
            <span class="label">最爱类型</span>
          </div>
          <div class="stat-box">
            <span class="value">{{ averageRating }}</span>
            <span class="label">平均打分</span>
          </div>
        </div>

        <div class="action-buttons">
          <button class="clear-btn" @click="historyStore.clearHistory()">
            清除历史记录
          </button>
          <button class="logout-btn" @click="handleLogout">
            退出登录
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import CardNav from '../components/CardNav.vue'
import logoSvg from '../assets/logo.svg'
import { useUserStore } from '../stores/user'
import { useHistoryStore } from '../stores/history'

const router = useRouter()
const userStore = useUserStore()
const historyStore = useHistoryStore()

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

const favoriteGenre = computed(() => {
  const allGenres = [...historyStore.ratingHistory, ...historyStore.browsingHistory]
    .flatMap(m => (m.genres || '').split('|'))
    .filter(g => g && g !== '(no genres listed)')

  if (allGenres.length === 0) return '暂无'
  
  const counts: Record<string, number> = {}
  let maxCount = 0
  let maxGenre = ''
  
  allGenres.forEach(g => {
    counts[g] = (counts[g] || 0) + 1
    if (counts[g] > maxCount) {
      maxCount = counts[g]
      maxGenre = g
    }
  })
  
  return genreMap[maxGenre] || maxGenre || '暂无'
})

const averageRating = computed(() => {
  const rated = historyStore.ratingHistory.filter(m => m.rating)
  if (rated.length === 0) return '0.0'
  const sum = rated.reduce((acc, m) => acc + (m.rating || 0), 0)
  return (sum / rated.length).toFixed(1)
})

const navItems = [
  {
    label: "探索",
    bgColor: "#0D0716",
    textColor: "#fff",
    links: [
      { label: "热门推荐", href: "/popular", ariaLabel: "热门推荐电影" },
      { label: "为你推荐", href: "/personalized", ariaLabel: "个性化推荐电影" }
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

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.profile-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 100px;
}

.profile-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: white;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7c5cfc, #a463ff);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 20px;
}

h2 {
  font-size: 24px;
  margin: 0;
  margin-bottom: 8px;
}

.user-id {
  color: #9a9ab0;
  font-size: 14px;
  margin: 0;
  margin-bottom: 30px;
}

.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  width: 100%;
  margin-bottom: 30px;
}

.stat-box {
  background: rgba(0,0,0,0.2);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.stat-box .value {
  font-size: 20px;
  font-weight: bold;
  color: #a463ff;
}

.stat-box .label {
  font-size: 12px;
  color: #9a9ab0;
}

.action-buttons {
  display: flex;
  gap: 12px;
  width: 100%;
}

.clear-btn, .logout-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.clear-btn {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.2);
}

.clear-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}

.logout-btn {
  background: rgba(124, 92, 252, 0.1);
  color: #a463ff;
  border-color: rgba(124, 92, 252, 0.2);
}

.logout-btn:hover {
  background: rgba(124, 92, 252, 0.2);
}
</style>
