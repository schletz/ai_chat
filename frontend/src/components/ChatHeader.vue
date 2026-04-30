<template>
  <div class="header">
    <button class="icon-btn header-back" @click="goBack" title="Zurück" aria-label="Zurück">←</button>
    <div class="header-title">
      <span class="header-name">{{ name }}</span>
      <button class="clock-display" :class="{ 'is-virtual': baseTimestamp !== null }" @click="$emit('toggle-time-picker')"
        :title="baseTimestamp !== null ? 'Virtuelle Zeit aktiv – klicken zum Anpassen' : 'Basiszeit setzen'">
        <span class="clock-icon">{{ baseTimestamp !== null ? "⏱" : "🕒" }}</span>
        <span class="clock-text">{{ formattedVirtualTime }}</span>
      </button>
    </div>

    <div class="header-right">
      <span v-if="contextTokens !== null" class="token-display"
        :title="`Tokens im aktuellen Kontext: ${contextTokens.toLocaleString('de-DE')}`">
        <span class="token-icon">🧮</span>
        <span class="token-text">{{ contextTokens.toLocaleString('de-DE') }}</span>
      </span>
      <button class="icon-btn menu-btn" :class="{ 'is-open': showMenu }" @click="toggleMenu" title="Menü"
        aria-label="Menü öffnen">☰</button>
    </div>

    <ChatMenu v-if="showMenu" :append-timestamp="appendTimestamp" :enable-thinking="enableThinking"
      :is-debug-mode="isDebugMode"
      :is-generating-plot="isGeneratingPlot"
      @toggle-timestamp="$emit('toggle-timestamp', $event)" @toggle-thinking="$emit('toggle-thinking', $event)"
      @toggle-debug="$emit('toggle-debug')"
      @generate-director-plot="$emit('generate-director-plot')"
      @cancel-director-plot="$emit('cancel-director-plot')"
      @open-context="onOpenContext"
      @reset-kv-cache="onResetKvCache"
      @clear-history="onClearHistory"
      @open-settings="onOpenSettings" @close="closeMenu" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import ChatMenu from "./ChatMenu.vue";

/**
 * Chat header bar. Owns only the open/close state of its burger submenu and
 * performs purely navigational actions (back, settings) itself; every other
 * concern is driven by props and reported back to the parent view via events.
 */
const props = defineProps<{
  /** Character name shown in the title and used for the settings route. */
  name: string;
  /** Virtual-clock anchor in ms, or null when the real system clock is active. */
  baseTimestamp: number | null;
  /** Pre-formatted virtual time string displayed in the clock pill. */
  formattedVirtualTime: string;
  /** Latest context token count, or null before the first assistant turn. */
  contextTokens: number | null;
  /** Current append-timestamp flag, forwarded to the submenu toggle. */
  appendTimestamp: boolean;
  /** Current reasoning state, forwarded to the submenu thinking toggle. */
  enableThinking: boolean;
  /** Whether debug message mode is active. */
  isDebugMode: boolean;
  /** Whether a director plot is currently being generated, driving the menu spinner. */
  isGeneratingPlot: boolean;
}>();

const emit = defineEmits<{
  (e: "toggle-time-picker"): void;
  (e: "toggle-timestamp", value: boolean): void;
  (e: "toggle-thinking", value: boolean): void;
  (e: "toggle-debug"): void;
  (e: "generate-director-plot"): void;
  (e: "cancel-director-plot"): void;
  (e: "open-context"): void;
  (e: "reset-kv-cache"): void;
  (e: "clear-history"): void;
}>();

const router = useRouter();

// Local open/close state for the submenu; the burger button toggles it.
const showMenu = ref(false);

const toggleMenu = () => {
  showMenu.value = !showMenu.value;
};

const closeMenu = () => {
  showMenu.value = false;
};

/** Navigates back to the character list. */
const goBack = () => router.push("/");

// Plot generation keeps the submenu open so its inline spinner stays visible
// while the plot is generated. The watcher below dismisses the menu once
// generation finishes.
watch(
  () => props.isGeneratingPlot,
  (generating, wasGenerating) => {
    if (wasGenerating && !generating) {
      showMenu.value = false;
    }
  }
);

const onOpenContext = () => {
  showMenu.value = false;
  emit("open-context");
};

const onResetKvCache = () => {
  showMenu.value = false;
  emit("reset-kv-cache");
};

const onClearHistory = () => {
  showMenu.value = false;
  emit("clear-history");
};

const onOpenSettings = () => {
  showMenu.value = false;
  router.push(`/character/${props.name}/edit`);
};
</script>

<style scoped>
/* Establishes the positioning context for the absolutely placed submenu. */
.header {
  position: relative;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
  font-size: 1rem;
  padding: 0;
}

.icon-btn:hover {
  opacity: 1;
}

/* Burger button that opens the submenu; rendered at full opacity for prominence */
.menu-btn {
  color: white;
  font-size: 1.4rem;
  line-height: 1;
  opacity: 0.85;
}

.menu-btn:hover,
.menu-btn.is-open {
  opacity: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Token counter pill, matches the visual language of the other header chips */
.token-display {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: white;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  user-select: none;
  white-space: nowrap;
}

.token-icon {
  font-size: 0.85rem;
}

.token-text {
  font-variant-numeric: tabular-nums;
  font-weight: bold;
  letter-spacing: 0.3px;
}

/* Back arrow rendered as a chunky chevron, matching the form view's header-back styling */
.header-back {
  color: white;
  font-size: 1.6rem;
  line-height: 1;
  padding: 0 6px 0 0;
  opacity: 1;
}

.header-back:hover {
  opacity: 0.75;
}

/* Header layout: title block grows so the clock can sit next to the name and wraps below on narrow viewports */
.header-title {
  flex: 1;
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 10px;
  min-width: 0;
  margin-left: 4px;
}

.header-name {
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* Clock pill displayed beneath the character name */
.clock-display {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-family: inherit;
  cursor: pointer;
  transition: background-color 0.2s;
  max-width: 100%;
}

.clock-display:hover {
  background: rgba(255, 255, 255, 0.22);
}

.clock-display.is-virtual {
  background: rgba(255, 200, 0, 0.25);
}

.clock-icon {
  font-size: 0.85rem;
}

.clock-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
