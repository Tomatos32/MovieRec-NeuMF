<template>
  <div class="min-h-screen bg-gray-50 flex">
    <!-- Sidebar Navigation -->
    <aside class="w-64 bg-white shadow-xl shadow-gray-100 hidden md:flex flex-col border-r border-gray-200">
      <div class="p-6">
        <h1 class="text-2xl font-bold text-blue-600 tracking-tight flex items-center">
          <Activity class="w-6 h-6 mr-2" />
          NNCF Admin
        </h1>
      </div>
      <nav class="flex-1 px-4 space-y-2 mt-4">
        <a href="#" class="flex items-center px-4 py-3 text-blue-700 bg-blue-50 rounded-xl font-semibold transition-colors">
          <LayoutDashboard class="w-5 h-5 mr-3" /> System Dashboard
        </a>
        <a href="#" class="flex items-center px-4 py-3 text-gray-500 hover:bg-gray-50 hover:text-gray-900 rounded-xl font-medium transition-colors">
          <Users class="w-5 h-5 mr-3" /> Account Management
        </a>
        <a href="#" class="flex items-center px-4 py-3 text-gray-500 hover:bg-gray-50 hover:text-gray-900 rounded-xl font-medium transition-colors">
          <Film class="w-5 h-5 mr-3" /> Movies Catalog
        </a>
        <a href="#" class="flex items-center px-4 py-3 text-gray-500 hover:bg-gray-50 hover:text-gray-900 rounded-xl font-medium transition-colors">
          <Cpu class="w-5 h-5 mr-3" /> Model Serving
        </a>
      </nav>
      <div class="p-4 border-t border-gray-100 mt-auto">
        <button @click="logout" class="flex items-center w-full px-4 py-3 text-red-600 hover:bg-red-50 rounded-xl font-medium transition-colors">
          <LogOut class="w-5 h-5 mr-3" /> Sign Out
        </button>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col h-screen overflow-hidden">
      <!-- Top header -->
      <header class="bg-white/80 backdrop-blur-md shadow-sm border-b border-gray-200 h-16 flex items-center justify-between px-6 z-10 sticky top-0">
        <div class="flex items-center md:hidden">
          <h1 class="text-xl font-bold text-blue-600 flex items-center"><Activity class="w-5 h-5 mr-2" />Admin</h1>
        </div>
        <div class="hidden md:block">
          <h2 class="text-lg font-semibold text-gray-800">Operational Overview</h2>
        </div>
        <div class="flex items-center gap-4">
          <div class="text-sm text-gray-500">Logged in as <span class="font-bold text-gray-900">Admin_Root</span></div>
          <div class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center font-bold shadow-lg shadow-blue-200">A</div>
        </div>
      </header>

      <!-- Scrollable Statistics Content -->
      <div class="flex-1 overflow-auto p-6 lg:p-10">
        
        <!-- KPI Cards Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <div class="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 flex items-center hover:shadow-md transition-shadow">
            <div class="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center text-blue-600 mr-5">
              <Users class="w-7 h-7" />
            </div>
            <div>
              <p class="text-sm text-gray-400 font-medium mb-1">Registered Users</p>
              <h3 class="text-3xl font-extrabold text-gray-900 leading-none">12,405</h3>
              <p class="text-xs text-green-500 font-medium mt-1">+14% this week</p>
            </div>
          </div>
          <div class="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 flex items-center hover:shadow-md transition-shadow">
            <div class="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center text-indigo-600 mr-5">
              <Film class="w-7 h-7" />
            </div>
            <div>
              <p class="text-sm text-gray-400 font-medium mb-1">Movies Indexed</p>
              <h3 class="text-3xl font-extrabold text-gray-900 leading-none">84,432</h3>
              <p class="text-xs text-green-500 font-medium mt-1">Live Sync Active</p>
            </div>
          </div>
          <div class="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 flex items-center hover:shadow-md transition-shadow">
            <div class="w-14 h-14 rounded-2xl bg-teal-50 flex items-center justify-center text-teal-600 mr-5">
              <MousePointerClick class="w-7 h-7" />
            </div>
            <div>
              <p class="text-sm text-gray-400 font-medium mb-1">Kafka Feedbacks</p>
              <h3 class="text-3xl font-extrabold text-gray-900 leading-none">2.1M</h3>
              <p class="text-xs text-gray-400 font-medium mt-1">~1,200 EPS</p>
            </div>
          </div>
          <div class="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 flex items-center hover:shadow-md transition-shadow">
            <div class="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center text-purple-600 mr-5">
              <Cpu class="w-7 h-7" />
            </div>
            <div>
              <p class="text-sm text-gray-400 font-medium mb-1">NeuMF Sidecar</p>
              <h3 class="text-3xl font-extrabold text-green-500 leading-none">Online</h3>
              <p class="text-xs text-gray-400 font-medium mt-1">Latency: ~45ms</p>
            </div>
          </div>
        </div>

        <!-- System Table -->
        <div class="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
          <div class="px-8 py-6 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
            <h3 class="text-lg font-bold text-gray-900 tracking-tight">Real-time Recommendation Audits</h3>
            <button class="text-sm px-4 py-2 bg-white text-gray-700 font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors shadow-sm">
              Export Logs
            </button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="bg-white text-gray-400 text-xs uppercase tracking-widest font-semibold border-b border-gray-100">
                  <th class="px-8 py-5">Instance Target</th>
                  <th class="px-8 py-5">Status / Action</th>
                  <th class="px-8 py-5">Result Info</th>
                  <th class="px-8 py-5">Timestamp</th>
                </tr>
              </thead>
              <tbody class="text-sm divide-y divide-gray-50 bg-white">
                <tr class="hover:bg-gray-50/50 transition-colors group">
                  <td class="px-8 py-4 font-medium text-gray-900">User #28591</td>
                  <td class="px-8 py-4"><span class="px-3 py-1.5 rounded-full text-xs font-bold bg-green-100 text-green-700">NeuMF Success</span></td>
                  <td class="px-8 py-4 text-gray-600">Generated 20 recs via Sidecar</td>
                  <td class="px-8 py-4 text-gray-400">Just now</td>
                </tr>
                <tr class="hover:bg-gray-50/50 transition-colors group">
                  <td class="px-8 py-4 font-medium text-gray-900">User #9302</td>
                  <td class="px-8 py-4"><span class="px-3 py-1.5 rounded-full text-xs font-bold bg-red-100 text-red-700">Circuit Breaker</span></td>
                  <td class="px-8 py-4 text-gray-600">Fallback to Top-Popular (Mode A)</td>
                  <td class="px-8 py-4 text-gray-400">2 mins ago</td>
                </tr>
                <tr class="hover:bg-gray-50/50 transition-colors group">
                  <td class="px-8 py-4 font-medium text-gray-900">Kafka Profiler</td>
                  <td class="px-8 py-4"><span class="px-3 py-1.5 rounded-full text-xs font-bold bg-blue-100 text-blue-700">Data Sync</span></td>
                  <td class="px-8 py-4 text-gray-600">Processed 15k interaction bursts</td>
                  <td class="px-8 py-4 text-gray-400">14 mins ago</td>
                </tr>
                <tr class="hover:bg-gray-50/50 transition-colors group">
                  <td class="px-8 py-4 font-medium text-gray-900">User #66721</td>
                  <td class="px-8 py-4"><span class="px-3 py-1.5 rounded-full text-xs font-bold bg-green-100 text-green-700">NeuMF Success</span></td>
                  <td class="px-8 py-4 text-gray-600">Generated 20 recs via Cache</td>
                  <td class="px-8 py-4 text-gray-400">18 mins ago</td>
                </tr>
                <tr class="hover:bg-gray-50/50 transition-colors group">
                  <td class="px-8 py-4 font-medium text-gray-900">Node Worker</td>
                  <td class="px-8 py-4"><span class="px-3 py-1.5 rounded-full text-xs font-bold bg-yellow-100 text-yellow-700">Warning</span></td>
                  <td class="px-8 py-4 text-gray-600">High memory pressure in Datalake</td>
                  <td class="px-8 py-4 text-gray-400">1 hour ago</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user';
import { useRouter } from 'vue-router';
import { 
  LayoutDashboard, 
  Users, 
  Film, 
  Activity, 
  LogOut,
  MousePointerClick,
  Cpu
} from 'lucide-vue-next';

const userStore = useUserStore();
const router = useRouter();

const logout = () => {
  userStore.logout();
  router.push('/login');
};
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

div {
  font-family: 'Inter', sans-serif;
}
</style>
