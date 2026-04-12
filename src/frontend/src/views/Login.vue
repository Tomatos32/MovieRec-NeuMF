<template>
  <div class="flex min-h-screen items-center justify-center p-4 relative overflow-hidden" style="background:#06060f">
    <!-- WebGL animated background -->
    <DarkVeil
      :hue-shift="0"
      :noise-intensity="0"
      :scanline-intensity="0"
      :speed="0.5"
      :scanline-frequency="0"
      :warp-amount="0"
      :resolution-scale="1"
    />
    <div class="login-card flex w-full max-w-5xl rounded-3xl shadow-2xl min-h-[600px] backdrop-blur-sm relative transition-all duration-500">
      
      <!-- Left Side: Tagline in three languages -->
      <div class="hidden md:flex w-1/2 relative flex-col items-center justify-center overflow-hidden px-12 py-14 left-panel">
        <!-- inner glow -->
        <div class="absolute inset-0 bg-gradient-to-br from-[#0052D4]/25 via-[#090979]/15 to-transparent pointer-events-none" />

        <!-- Logo: top-left corner -->
        <div class="absolute top-7 left-8 z-20 select-none">
          <img
            src="@/assets/openclipart-vectors-camera.svg"
            alt="MovieRec Logo"
            width="100"
            height="100"
          />
        </div>

        <div class="relative z-10 w-full space-y-6">

          <!-- 中文 -->
          <div class="tagline-row">
            <p class="tagline-text text-white/90 text-2xl font-bold tracking-wide select-none">
              <DecryptedText
                text="看见你喜欢的每一帧"
                :speed="110"
                :max-iterations="14"
                :sequential="true"
                reveal-direction="start"
                animate-on="view"
                :repeat="true"
                :repeat-delay="5000"
                class-name="text-white/90"
                encrypted-class-name="text-blue-300/30"
              />
            </p>
          </div>

          <!-- 分隔线 -->
          <div class="w-8 h-px bg-white/15" />

          <!-- English -->
          <div class="tagline-row">
            <p class="tagline-text text-white/55 text-lg font-light tracking-wider select-none">
              <DecryptedText
                text="See every frame you love"
                :speed="85"
                :max-iterations="10"
                :sequential="true"
                reveal-direction="start"
                animate-on="view"
                :repeat="true"
                :repeat-delay="6000"
                class-name="text-white/55"
                encrypted-class-name="text-blue-400/20"
              />
            </p>
          </div>

          <!-- 分隔线 -->
          <div class="w-8 h-px bg-white/15" />

          <!-- Italiano -->
          <div class="tagline-row">
            <p class="tagline-text text-white/35 text-base font-extralight tracking-widest select-none italic">
              <DecryptedText
                text="Vedi ogni fotogramma che ami"
                :speed="70"
                :max-iterations="8"
                :sequential="true"
                reveal-direction="start"
                animate-on="view"
                :repeat="true"
                :repeat-delay="7000"
                class-name="text-white/35"
                encrypted-class-name="text-blue-500/15"
              />
            </p>
          </div>

        </div>
      </div>

      <!-- Right Side: Login/Register Form (Glassmorphism) -->
      <div class="w-full md:w-1/2 p-12 flex flex-col justify-center bg-white/10 backdrop-blur-xl relative z-10 overflow-y-auto">
        <div class="max-w-xs mx-auto w-full transition-all duration-500 relative">
          
          <div class="mb-10">
            <h2 class="text-2xl font-bold text-white mb-2 transition-all">{{ isLogin ? 'Hello Again!' : '创建新账户' }}</h2>
            <p class="text-gray-300 transition-all">{{ isLogin ? '欢迎回来' : '' }}</p>
          </div>

          <form @submit.prevent="handleAuth" class="space-y-5">
            <div>
               <!-- Username Input -->
              <div class="relative">
                <input 
                  v-model="form.username" 
                  type="text" 
                  class="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 pl-10 text-sm text-white outline-none focus:border-blue-400 focus:bg-white/10 transition-all placeholder-gray-400"
                  placeholder="用户名"
                  autocomplete="username"
                  required
                >
                <Mail class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
              </div>
            </div>

            <div>
              <!-- Password Input -->
              <div class="relative">
                <input 
                  v-model="form.password" 
                  type="password" 
                  class="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 pl-10 text-sm text-white outline-none focus:border-blue-400 focus:bg-white/10 transition-all placeholder-gray-400"
                  placeholder="密码"
                  autocomplete="current-password"
                  required
                  minlength="6"
                >
                 <Lock class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
              </div>
            </div>

            <!-- Confirm Password (Only for Register) Using Transition -->
            <transition name="fade-slide">
              <div v-show="!isLogin" class="overflow-hidden">
                <div class="relative">
                  <input 
                    v-model="form.confirmPassword" 
                    type="password" 
                    class="w-full bg-white/5 border border-white/10 rounded-full px-5 py-3 pl-10 text-sm text-white outline-none focus:border-blue-400 focus:bg-white/10 transition-all placeholder-gray-400"
                    placeholder="确认密码"
                    autocomplete="new-password"
                    :required="!isLogin"
                    minlength="6"
                  >
                   <Lock class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                </div>
              </div>
            </transition>

            <button 
              type="submit" 
              class="w-full py-3 bg-[#0052D4] hover:bg-[#0041a8] text-white font-bold rounded-full shadow-[0_4px_14px_0_rgba(0,82,212,0.39)] hover:shadow-[0_6px_20px_rgba(0,82,212,0.23)] transition-all transform hover:-translate-y-0.5 text-sm active:scale-95"
              :disabled="loading"
            >
              <span v-if="loading" class="flex items-center justify-center">
                <Loader2 class="animate-spin mr-2 w-4 h-4" />{{ isLogin ? '正在登录...' : '正在注册...' }}
              </span>
              <span v-else>{{ isLogin ? '登录' : '注册' }}</span>
            </button>
            
            <div class="flex justify-center items-center mt-6">
               <a href="#" @click.prevent="toggleMode" class="text-xs text-blue-200 hover:text-white transition-colors">
                 {{ isLogin ? "没有帐户？去注册" : "已有帐户？去登录" }}
               </a>
            </div>
          </form>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { ElMessage } from 'element-plus';
import { Mail, Lock, Loader2 } from 'lucide-vue-next';
import DarkVeil from '@/components/DarkVeil.vue';
import DecryptedText from '@/components/DecryptedText.vue';


const router = useRouter();
const userStore = useUserStore();

const isLogin = ref(true);
const loading = ref(false);

const form = ref({
  username: '', 
  password: '',
  confirmPassword: ''
});

const toggleMode = () => {
  isLogin.value = !isLogin.value;
  form.value.password = '';
  form.value.confirmPassword = '';
};

const handleAuth = async () => {
  // Client-side validation for registration
  if (!isLogin.value) {
    if (form.value.password.length < 6) {
      ElMessage.error('Password must be at least 6 characters');
      return;
    }
    if (form.value.password !== form.value.confirmPassword) {
      ElMessage.error('Passwords do not match');
      return;
    }
  }

  loading.value = true;
  try {
    if (isLogin.value) {
      // Login flow
      await userStore.login({ username: form.value.username, password: form.value.password });
      ElMessage.success('Login Successful');
      
      if (form.value.username === 'admin') {
        router.push('/admin');
      } else {
        router.push('/');
      }
    } else {
      // Registration flow
      await userStore.register({ username: form.value.username, password: form.value.password });
      ElMessage.success('Registration completed. Please Login.');
      // Auto-toggle to login mode after successful registration
      isLogin.value = true;
      form.value.password = '';
      form.value.confirmPassword = '';
    }
  } catch (error: any) {
    console.error('Auth error details:', error);
    ElMessage.error(error.message || (isLogin.value ? 'Login Failed' : 'Registration Failed'));
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

div {
  font-family: 'Poppins', sans-serif;
}

/* ── 边缘羽化：让卡片四周渐变透明，融入 WebGL 背景 ── */
.login-card {
  /* 椭圆渐变 mask：中心完全不透明，向四边缓慢透明 */
  -webkit-mask-image: radial-gradient(
    ellipse 88% 88% at 50% 50%,
    black 55%,
    transparent 100%
  );
  mask-image: radial-gradient(
    ellipse 88% 88% at 50% 50%,
    black 55%,
    transparent 100%
  );
  /* 允许 mask 生效：不裁剪溢出内容 */
  overflow: visible;
}

/* 左侧面板左侧无圆角，内容溢出隐藏 */
.login-card > div:first-child {
  overflow: hidden;
  border-radius: 1.5rem 0 0 1.5rem;
}

/* 标语行：lang 标签 + 文字水平排列 */
.tagline-row {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

/* 语言标签 ZH / EN / IT */
.lang-label {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: rgba(255, 255, 255, 0.25);
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
  width: 1.6rem;
  text-align: right;
}

/* Animations for isomorphic form switching */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 100px;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-10px);
  margin-top: 0 !important;
}
</style>
