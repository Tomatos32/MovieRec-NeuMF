<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, useTemplateRef } from 'vue';

interface DecryptedTextProps {
  text: string;
  speed?: number;
  maxIterations?: number;
  sequential?: boolean;
  revealDirection?: 'start' | 'end' | 'center';
  useOriginalCharsOnly?: boolean;
  characters?: string;
  className?: string;
  encryptedClassName?: string;
  parentClassName?: string;
  animateOn?: 'view' | 'hover';
  /** 动画结束后是否循环重复 */
  repeat?: boolean;
  /** 每次循环之间的停顿时间（ms） */
  repeatDelay?: number;
}

const props = withDefaults(defineProps<DecryptedTextProps>(), {
  text: '',
  speed: 50,
  maxIterations: 10,
  sequential: false,
  revealDirection: 'start',
  useOriginalCharsOnly: false,
  characters: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+',
  className: '',
  parentClassName: '',
  encryptedClassName: '',
  animateOn: 'hover',
  repeat: false,
  repeatDelay: 2000,
});

const emit = defineEmits<{ animationComplete: [] }>();

const containerRef = useTemplateRef<HTMLSpanElement>('containerRef');
const displayText = ref(props.text);
const isScrambling = ref(false);
const revealedIndices = ref(new Set<number>());

let interval: ReturnType<typeof setInterval> | null = null;
let repeatTimeout: ReturnType<typeof setTimeout> | null = null;
let intersectionObserver: IntersectionObserver | null = null;

// ── helpers ────────────────────────────────────────────────────────────────

const getNextIndex = (revealedSet: Set<number>): number => {
  const textLength = props.text.length;
  switch (props.revealDirection) {
    case 'start': return revealedSet.size;
    case 'end':   return textLength - 1 - revealedSet.size;
    case 'center': {
      const middle = Math.floor(textLength / 2);
      const offset = Math.floor(revealedSet.size / 2);
      const nextIndex = revealedSet.size % 2 === 0
        ? middle + offset
        : middle - offset - 1;
      if (nextIndex >= 0 && nextIndex < textLength && !revealedSet.has(nextIndex))
        return nextIndex;
      for (let i = 0; i < textLength; i++)
        if (!revealedSet.has(i)) return i;
      return 0;
    }
    default: return revealedSet.size;
  }
};

const getAvailableChars = () =>
  props.useOriginalCharsOnly
    ? Array.from(new Set(props.text.split(''))).filter(c => c !== ' ')
    : props.characters.split('');

const shuffleText = (originalText: string, currentRevealed: Set<number>): string => {
  const chars = getAvailableChars();
  if (props.useOriginalCharsOnly) {
    const positions = originalText.split('').map((char, i) => ({
      char, isSpace: char === ' ', index: i, isRevealed: currentRevealed.has(i)
    }));
    const nonSpaceChars = positions
      .filter(p => !p.isSpace && !p.isRevealed)
      .map(p => p.char);
    for (let i = nonSpaceChars.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [nonSpaceChars[i]!, nonSpaceChars[j]!] = [nonSpaceChars[j]!, nonSpaceChars[i]!];
    }
    let charIndex = 0;
    return positions.map(p => {
      if (p.isSpace) return ' ';
      if (p.isRevealed) return originalText[p.index];
      return nonSpaceChars[charIndex++] ?? '';
    }).join('');
  } else {
    return originalText.split('').map((char, i) => {
      if (char === ' ') return ' ';
      if (currentRevealed.has(i)) return originalText[i];
      return chars[Math.floor(Math.random() * chars.length)];
    }).join('');
  }
};

// ── core animation ─────────────────────────────────────────────────────────

const stopAll = () => {
  if (interval) { clearInterval(interval); interval = null; }
  if (repeatTimeout) { clearTimeout(repeatTimeout); repeatTimeout = null; }
};

const startAnimation = () => {
  stopAll();
  revealedIndices.value = new Set();
  displayText.value = shuffleText(props.text, revealedIndices.value);
  isScrambling.value = true;
  let currentIteration = 0;

  const onComplete = () => {
    isScrambling.value = false;
    displayText.value = props.text;
    emit('animationComplete');

    if (props.repeat) {
      // 等待 repeatDelay 后重置并再次播放
      repeatTimeout = setTimeout(() => {
        startAnimation();
      }, props.repeatDelay);
    }
  };

  interval = setInterval(() => {
    if (props.sequential) {
      if (revealedIndices.value.size < props.text.length) {
        const nextIndex = getNextIndex(revealedIndices.value);
        const newRevealed = new Set(revealedIndices.value);
        newRevealed.add(nextIndex);
        revealedIndices.value = newRevealed;
        displayText.value = shuffleText(props.text, newRevealed);
      } else {
        clearInterval(interval!); interval = null;
        onComplete();
      }
    } else {
      displayText.value = shuffleText(props.text, revealedIndices.value);
      currentIteration++;
      if (currentIteration >= props.maxIterations) {
        clearInterval(interval!); interval = null;
        onComplete();
      }
    }
  }, props.speed);
};

const stopAnimation = () => {
  stopAll();
  displayText.value = props.text;
  revealedIndices.value = new Set();
  isScrambling.value = false;
};

// ── hover ──────────────────────────────────────────────────────────────────

const handleMouseEnter = () => {
  if (props.animateOn === 'hover') startAnimation();
};
const handleMouseLeave = () => {
  if (props.animateOn === 'hover' && !props.repeat) stopAnimation();
};

// ── view trigger ──────────────────────────────────────────────────────────

onMounted(async () => {
  if (props.animateOn === 'view') {
    await nextTick();
    intersectionObserver = new IntersectionObserver(
      entries => entries.forEach(e => {
        if (e.isIntersecting) startAnimation();
        else if (!props.repeat) stopAnimation();
      }),
      { root: null, rootMargin: '0px', threshold: 0.1 }
    );
    if (containerRef.value) intersectionObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  stopAll();
  if (intersectionObserver && containerRef.value)
    intersectionObserver.unobserve(containerRef.value);
});

// 外部 prop 变化时重置
watch(() => props.text, () => stopAnimation());
</script>

<template>
  <span
    ref="containerRef"
    :class="`inline-block whitespace-pre-wrap ${props.parentClassName}`"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <span class="sr-only">{{ props.text }}</span>
    <span aria-hidden="true">
      <span
        v-for="(char, index) in displayText.split('')"
        :key="index"
        :class="revealedIndices.has(index) || !isScrambling
          ? props.className
          : props.encryptedClassName"
      >{{ char }}</span>
    </span>
  </span>
</template>
