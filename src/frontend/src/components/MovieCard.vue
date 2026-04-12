<template>
  <div class="movie-card" @click="handleClick">
    <!-- 海报区域 -->
    <div class="card-poster">
      <img
        :src="`/posters/${movie.movieId}.jpg`"
        :alt="movie.title"
        width="300"
        height="450"
        loading="lazy"
        @error="onImgError"
      />
      <div class="poster-overlay"></div>
    </div>

    <!-- 信息区域 -->
    <div class="card-body">
      <h3 class="card-title">{{ movie.title }}</h3>
      <p class="card-genres">{{ formattedGenres }}</p>

      <!-- 评分组件 -->
      <div class="card-rating" @click.stop>
        <span 
          v-for="star in 5" 
          :key="star"
          class="star-icon"
          :class="{ 'active': star <= (hoverRating || movie.rating || 0) }"
          @mouseenter="hoverRating = star"
          @mouseleave="hoverRating = 0"
          @click="handleRate(star)"
          :title="`${star} 星`"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{'filled': star <= (hoverRating || movie.rating || 0)}">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        </span>
      </div>

      <!-- 操作按钮区 -->
      <div class="card-actions">
        <button
          class="btn-dislike"
          title="不感兴趣"
          aria-label="不感兴趣"
          @click.stop="handleDislike"
          :disabled="isDislikeDisabled"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
          </svg>
          不喜欢
        </button>
        <button class="btn-detail" @click.stop="handleClick">
          查看详情 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Movie } from '../types'

const props = defineProps<{
  movie: Movie
}>()

const emit = defineEmits<{
  (e: 'click', movieId: number): void
  (e: 'dislike', movieId: number): void
  (e: 'rate', movieId: number, rating: number): void
}>()

const hoverRating = ref(0)
const isDislikeDisabled = ref(false)

const fallbackPoster = 'https://placehold.co/300x450/1a1a28/5e5e78?text=No+Poster'

const formattedGenres = computed(() =>
  props.movie.genres
    .split('|')
    .slice(0, 3)
    .join(' · ')
)

const handleClick = () => {
  emit('click', props.movie.movieId)
}

const handleDislike = () => {
  isDislikeDisabled.value = true
  emit('dislike', props.movie.movieId)
  // 3 秒后重新启用按钮
  setTimeout(() => {
    isDislikeDisabled.value = false
  }, 3000)
}

const handleRate = (star: number) => {
  emit('rate', props.movie.movieId, star)
}

const onImgError = (e: Event) => {
  const target = e.target as HTMLImageElement
  target.src = fallbackPoster
}
</script>

<style scoped>
.movie-card {
  position: relative;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-card);
  transition: transform var(--transition-normal), box-shadow var(--transition-normal), border-color var(--transition-normal);
  cursor: pointer;
}

.movie-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: var(--radius-md);
  box-shadow: inset 0 0 0 1px transparent;
  transition: box-shadow var(--transition-normal);
  pointer-events: none;
  z-index: 10;
}

.movie-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-card-hover), var(--shadow-glow);
  border-color: transparent;
}

.movie-card:hover::before {
  box-shadow: inset 0 0 0 1px var(--color-accent-light);
}

/* 海报 */
.card-poster {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  background: var(--color-bg-skeleton);
}

.card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--transition-slow);
}

.poster-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 40%;
  background: linear-gradient(to top, var(--color-bg-card) 0%, transparent 100%);
  z-index: 1;
}

.movie-card:hover .card-poster img {
  transform: scale(1.05);
}

/* 信息区 */
.card-body {
  position: relative;
  z-index: 2;
  padding: 10px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-genres {
  font-size: 12px;
  color: var(--color-text-secondary);
  letter-spacing: 0.03em;
}

/* 评分组件 */
.card-rating {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  align-items: center;
}

.star-icon {
  cursor: pointer;
  color: var(--color-text-muted);
  transition: color 0.2s, transform 0.1s;
}

.star-icon svg {
  transition: fill 0.2s, color 0.2s;
}

.star-icon:hover {
  transform: scale(1.1);
}

.star-icon.active svg {
  color: #fbbf24;
}

.star-icon svg.filled {
  fill: #fbbf24;
}

/* 操作按钮 */
.card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 8px;
}

.btn-dislike {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), border-color var(--transition-fast), background-color var(--transition-fast);
}

.btn-dislike:hover:not(:disabled) {
  color: var(--color-danger);
  border-color: var(--color-danger);
  background: rgba(248, 113, 113, 0.08);
}

.btn-dislike:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-detail {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-accent-light);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  transition: background-color var(--transition-fast), color var(--transition-fast);
}

.btn-detail:hover {
  background: var(--color-accent-glow);
}
</style>
