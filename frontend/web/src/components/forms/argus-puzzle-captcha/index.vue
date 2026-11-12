<!-- 滑块拼图验证码：拖动图块补齐背景缺口，位置由服务端校验 -->
<template>
  <div class="argus-puzzle" :class="{ 'is-passed': passed, 'is-loading': loading }">
    <Teleport to="body">
      <Transition name="puzzle-pop">
        <div v-if="panelOpen" class="argus-puzzle__overlay" @click.self="closePanel">
          <div class="argus-puzzle__dialog" role="dialog" aria-modal="true">
            <button
              type="button"
              class="argus-puzzle__close"
              :aria-label="closeText"
              @click="closePanel"
            >
              <ArgusSvgIcon icon="ri:close-line" />
            </button>
            <p class="argus-puzzle__title">{{ titleText }}</p>
            <div ref="areaRef" class="argus-puzzle__area">
              <img v-if="bgImage" :src="bgImage" class="argus-puzzle__bg" alt="" draggable="false" />
              <img
                v-if="pieceImage"
                :src="pieceImage"
                class="argus-puzzle__piece"
                alt=""
                draggable="false"
                :style="{ left: `${leftPx}px`, top: `${topPx}px`, width: `${pieceWidthPx}px` }"
              />
              <div v-if="loading" class="argus-puzzle__mask">
                <ArgusSvgIcon icon="ri:loader-4-line" class="animate-spin" />
              </div>
            </div>

            <div
              ref="trackRef"
              class="argus-puzzle__track"
              :class="{ 'is-dragging': dragging }"
              @pointerdown.prevent="onPointerDown"
            >
              <div class="argus-puzzle__fill" :style="{ width: `${progress * 100}%` }" />
              <div
                class="argus-puzzle__handler"
                :style="{ transform: `translateX(${handlerLeft}px)` }"
              >
                <ArgusSvgIcon :icon="passed ? 'ri:check-line' : 'ri:arrow-right-line'" />
              </div>
              <span class="argus-puzzle__text">{{ passed ? successText : text }}</span>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <button type="button" class="argus-puzzle__entry" :disabled="loading" @click="requestPanel">
      <ArgusSvgIcon :icon="passed ? 'ri:check-line' : 'ri:lock-2-line'" />
      <span class="argus-puzzle__entry-text">{{ passed ? successText : entryText }}</span>
      <ArgusSvgIcon v-if="!passed" icon="ri:arrow-right-line" class="argus-puzzle__entry-arrow" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { useElementSize } from "@vueuse/core";

defineOptions({ name: "ArgusPuzzleCaptcha" });

interface Props {
  bgImage: string;
  pieceImage: string;
  pieceY?: number;
  pieceWidth?: number;
  pieceHeight?: number;
  bgWidth?: number;
  bgHeight?: number;
  passed?: boolean;
  loading?: boolean;
  text: string;
  titleText: string;
  successText: string;
  closeText: string;
  entryText: string;
}

const props = withDefaults(defineProps<Props>(), {
  pieceY: 0,
  pieceWidth: 55,
  pieceHeight: 48,
  bgWidth: 320,
  bgHeight: 160,
  passed: false,
  loading: false,
});

const emit = defineEmits<{
  verify: [position: number];
  refresh: [];
  request: [];
}>();

const areaRef = ref<HTMLElement>();
const trackRef = ref<HTMLElement>();
const { width: areaWidth, height: areaHeight } = useElementSize(areaRef);
const { width: trackWidth } = useElementSize(trackRef);

const progress = ref(0);
const dragging = ref(false);
const panelOpen = ref(false);
const startX = ref(0);
const startProgress = ref(0);

watch(
  () => props.bgImage,
  () => {
    progress.value = 0;
    dragging.value = false;
    panelOpen.value = false;
  }
);

watch(
  () => props.passed,
  (passed) => {
    if (passed) window.setTimeout(closePanel, 700);
  }
);

const HANDLER = 40;

const pieceWidthPx = computed(
  () => (areaWidth.value || props.bgWidth) * (props.pieceWidth / props.bgWidth)
);
const leftPx = computed(
  () => progress.value * Math.max(0, (areaWidth.value || props.bgWidth) - pieceWidthPx.value)
);
const topPx = computed(
  () => (areaHeight.value || props.bgHeight) * (props.pieceY / props.bgHeight)
);
const handlerLeft = computed(
  () => progress.value * Math.max(0, (trackWidth.value || 300) - HANDLER)
);

function requestPanel(): void {
  if (props.loading) return;
  emit("request");
}

function openPanel(): void {
  if (props.loading) return;
  panelOpen.value = true;
}

function closePanel(): void {
  panelOpen.value = false;
  progress.value = 0;
  dragging.value = false;
}

function clampProgress(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function onPointerDown(event: PointerEvent): void {
  if (props.passed || props.loading) return;
  dragging.value = true;
  startX.value = event.clientX;
  startProgress.value = progress.value;
  (event.target as HTMLElement | null)?.setPointerCapture?.(event.pointerId);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp, { once: true });
}

function onPointerMove(event: PointerEvent): void {
  if (!dragging.value) return;
  const rect = trackRef.value?.getBoundingClientRect();
  if (!rect) return;
  const delta = (event.clientX - startX.value) / Math.max(1, rect.width - HANDLER);
  progress.value = clampProgress(startProgress.value + delta);
}

function onPointerUp(): void {
  window.removeEventListener("pointermove", onPointerMove);
  dragging.value = false;
  if (progress.value <= 0.03) {
    progress.value = 0;
    return;
  }
  const max = Math.max(0, props.bgWidth - props.pieceWidth);
  emit("verify", Math.round(progress.value * max));
}

function reset(): void {
  progress.value = 0;
  dragging.value = false;
  panelOpen.value = false;
}

defineExpose({ reset, open: openPanel });
</script>

<style scoped lang="scss">
.argus-puzzle {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  user-select: none;
}

.argus-puzzle__entry {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 40px;
  font-size: 13px;
  color: var(--el-color-primary);
  cursor: pointer;
  background: color-mix(in srgb, var(--el-color-primary) 6%, transparent);
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 8px;
  transition:
    background 0.2s ease,
    border-color 0.2s ease;
}

@media (width < 768px) {
  .argus-puzzle__entry {
    gap: 4px;
    height: 24px;
    font-size: 12px;
    border-radius: 6px;
  }

  .argus-puzzle__entry-arrow {
    font-size: 11px;
  }
}

.argus-puzzle__entry:hover {
  background: color-mix(in srgb, var(--el-color-primary) 10%, transparent);
}

.argus-puzzle__entry:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.argus-puzzle__entry-text {
  background: linear-gradient(
    to right,
    var(--el-color-primary) 0%,
    var(--el-color-primary) 42%,
    #dbe4ff 50%,
    var(--el-color-primary) 58%,
    var(--el-color-primary) 100%
  );
  background-clip: text;
  background-size: 200% 100%;
  animation: puzzle-entry-shimmer 2.4s cubic-bezier(0, 0.2, 1, 1) infinite;
  -webkit-text-fill-color: transparent;
}

.argus-puzzle__entry-arrow {
  font-size: 12px;
  opacity: 0.75;
  animation: puzzle-arrow-nudge 2.4s ease-in-out infinite;
}

.is-passed .argus-puzzle__entry-text {
  color: var(--el-color-success);
  background: none;
  -webkit-text-fill-color: currentcolor;
  animation: none;
}

.is-passed .argus-puzzle__entry-arrow {
  animation: none;
}

.argus-puzzle__title {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.argus-puzzle__overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(0 0 0 / 45%);
  backdrop-filter: blur(2px);
}

.argus-puzzle__dialog {
  position: relative;
  width: min(92vw, 360px);
  padding: 12px;
  background: var(--default-box-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  box-shadow: var(--el-box-shadow-dark);
}

.argus-puzzle__close {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  background: rgb(0 0 0 / 28%);
  border: 0;
  border-radius: 6px;
}

.argus-puzzle__dialog .argus-puzzle__area {
  margin-bottom: 10px;
}

.argus-puzzle__area {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 1;
  overflow: hidden;
  background: var(--default-box-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
}

.argus-puzzle__bg {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
  object-fit: fill;
}

.argus-puzzle__piece {
  position: absolute;
  height: auto;
  pointer-events: none;
  filter: drop-shadow(0 2px 6px rgb(0 0 0 / 45%));
}

.argus-puzzle__refresh {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: #fff;
  cursor: pointer;
  background: rgb(0 0 0 / 38%);
  border: 0;
  border-radius: 6px;
  transition: background 0.2s;

  &:hover {
    background: rgb(0 0 0 / 60%);
  }
}

.argus-puzzle__mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: var(--el-color-primary);
  background: rgb(0 0 0 / 35%);
}

.argus-puzzle__track {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  order: 1;
  width: 100%;
  height: 40px;
  overflow: hidden;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  touch-action: none;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;

  &.is-dragging {
    cursor: grabbing;
  }
}

:global(html.dark) .argus-puzzle__track {
  background: #26272f;
}

.argus-puzzle__fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, var(--el-color-success), var(--el-color-success-light-3));
  transition: width 0.3s ease;
}

.argus-puzzle__handler {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 100%;
  color: var(--el-text-color-secondary);
  cursor: grab;
  background: var(--default-box-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  box-shadow: none;
}

.argus-puzzle__text {
  position: relative;
  z-index: 1;
  color: transparent;
  pointer-events: none;
  background: linear-gradient(
    to right,
    var(--el-text-color-secondary) 0%,
    var(--el-text-color-secondary) 40%,
    #fff 50%,
    var(--el-text-color-secondary) 60%,
    var(--el-text-color-secondary) 100%
  );
  background-clip: text;
  background-size: 200% 100%;
  animation: puzzle-shimmer 2.2s cubic-bezier(0, 0.2, 1, 1) infinite;
  -webkit-text-fill-color: transparent;
}

.is-passed {
  .argus-puzzle__entry {
    color: var(--el-color-success);
    background: color-mix(in srgb, var(--el-color-success) 8%, transparent);
    border-color: var(--el-color-success-light-5);
  }

  .argus-puzzle__track {
    color: var(--el-color-success);
    border-color: var(--el-color-success-light-5);
  }

  .argus-puzzle__fill {
    background: linear-gradient(90deg, var(--el-color-success), var(--el-color-success-light-3));
  }

  .argus-puzzle__handler {
    color: var(--el-color-success);
    border-color: var(--el-color-success-light-5);
  }

  .argus-puzzle__text {
    color: var(--el-color-success);
    background: none;
    -webkit-text-fill-color: currentcolor;
    animation: none;
  }
}

@keyframes puzzle-entry-shimmer {
  0% {
    background-position: 150% 0;
  }

  100% {
    background-position: -50% 0;
  }
}

@keyframes puzzle-arrow-nudge {
  0%,
  100% {
    transform: translateX(0);
  }

  50% {
    transform: translateX(3px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .argus-puzzle__entry-text {
    color: var(--el-color-primary);
    background: none;
    -webkit-text-fill-color: currentcolor;
    animation: none;
  }

  .argus-puzzle__entry-arrow {
    animation: none;
  }
}

@keyframes puzzle-shimmer {
  0% {
    background-position: 150% 0;
  }

  100% {
    background-position: -50% 0;
  }
}

.is-loading {
  opacity: 0.75;
}
</style>
