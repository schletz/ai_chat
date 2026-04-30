<template>
  <TextViewerPanel title="🔎 Context" :text="contextDisplay" :copyable="context !== null"
    @close="$emit('close')" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ChatService } from "../services/ChatService";
import TextViewerPanel from "./TextViewerPanel.vue";

/**
 * Fullscreen overlay that shows the assembled chat context (optional intro and
 * the rolling-summary history, optionally prefixed with the virtual point in
 * time) in a read-only textarea for debugging and analysis. It owns the fetch
 * itself and delegates the rendering to `TextViewerPanel`; the
 * parent only toggles visibility and reacts to the close event.
 */
const props = defineProps<{
  /** Character name used to scope the context request to the right chat. */
  name: string;
  /**
   * Optional virtual time (ms since epoch) of the user-set "in-world" clock.
   * Forwarded to the backend so the context is prefixed with the matching point
   * in time. Null when no virtual clock is active.
   */
  baseTimestamp: number | null;
}>();

defineEmits<{
  /** Requests the panel be closed. */
  (e: "close"): void;
}>();

const chatService = new ChatService(props.name);

// Fetched context; null while loading. Errors are kept separately so the
// textarea can surface a notice instead of a blank panel.
const context = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

// Resolves to a loading hint, the error notice, or the fetched context string.
const contextDisplay = computed(() => {
  if (errorMessage.value !== null) return errorMessage.value;
  if (context.value === null) return "Lade Context …";
  return context.value;
});

onMounted(async () => {
  try {
    context.value = await chatService.getContext(props.baseTimestamp);
  } catch (error) {
    console.error("Failed to load chat context", error);
    errorMessage.value = "Context konnte nicht geladen werden.";
  }
});
</script>
