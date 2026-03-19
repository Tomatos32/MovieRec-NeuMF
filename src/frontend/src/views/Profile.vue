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
          <button @click="handleLogout" class="px-4 py-2 border-0 rounded-[calc(0.75rem-0.2rem)] h-full font-medium transition-colors duration-300 cursor-pointer hover:bg-[#6a4ae0]" style="background-color: #7c5cfc; color: #fff;">登出</button>
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
            <span class="label">已互动</span>
          </div>
        </div>

        <button class="clear-btn" @click="historyStore.clearHistory()">
          清除本地历史记录
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import CardNav from '../components/CardNav.vue'
import logoSvg from '../assets/logo.svg'
import { useUserStore } from '../stores/user'
import { useHistoryStore } from '../stores/history'

const router = useRouter()
const userStore = useUserStore()
const historyStore = useHistoryStore()

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
  display: flex;
  gap: 20px;
  width: 100%;
  margin-bottom: 30px;
}

.stat-box {
  flex: 1;
  background: rgba(0,0,0,0.2);
  border-radius: 12px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.stat-box .value {
  font-size: 24px;
  font-weight: bold;
  color: #a463ff;
}

.stat-box .label {
  font-size: 12px;
  color: #9a9ab0;
}

.clear-btn {
  width: 100%;
  padding: 12px;
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}
</style>
