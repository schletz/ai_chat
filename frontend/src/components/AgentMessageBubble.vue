<template>
  <div class="agent-row">
    <button
      type="button"
      class="agent-toggle"
      :class="{ 'is-open': expanded }"
      :title="agentLabel"
      :aria-label="agentLabel"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      {{ agentIcon }}
    </button>

    <div v-if="expanded" class="agent-content">
      <div class="agent-text">{{ message.content }}</div>
      <div class="agent-footer">
        <button
          type="button"
          class="icon-btn delete-btn"
          title="Agent-Nachricht löschen"
          @click="$emit('delete', message.timestamp)"
        >
          🗑️
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ChatMessage } from "../services/ChatService";

const props = defineProps<{
  message: ChatMessage;
  // When debug mode is active every agent message is revealed automatically.
  debugMode?: boolean;
}>();

defineEmits<{
  (e: "delete", timestamp: number): void;
}>();

// Whether the raw agent message is currently revealed. Collapsed by default so
// the chat only shows a compact icon until the user opts in, but expanded from
// the start while debug mode is active.
const expanded = ref(props.debugMode ?? false);

// Enabling debug mode reveals all agent messages; the user can still collapse an
// individual message afterwards without leaving debug mode.
watch(
  () => props.debugMode,
  (isDebug) => {
    if (isDebug) expanded.value = true;
  }
);

/**
 * Maps the agent message to its presentation (icon + label) based on the
 * steering tag contained in the raw content. Falls back to the generic agent
 * marker when no known tag is present.
 */
const agentType = computed<{ icon: string; label: string }>(() => {
  const content = props.message.content;
  if (content.includes("<director>")) return { icon: "🎬", label: "Director" };
  return { icon: "🤖", label: "Agent" };
});

const agentIcon = computed(() => agentType.value.icon);
const agentLabel = computed(() => agentType.value.label);
</script>

<style scoped>
/* Centered row so agent steering messages read as system-level notes rather
   than regular chat bubbles. */
.agent-row {
  align-self: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  max-width: 90%;
}

.agent-toggle {
  border: 1px solid #d1d1d6;
  background: #f1f1f4;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background-color 0.2s, box-shadow 0.2s;
}

.agent-toggle:hover {
  background: #e5e5ea;
}

.agent-toggle.is-open {
  background: #e1f3fb;
  box-shadow: inset 0 0 0 1px #b6dcea;
}

/* Raw agent content shown verbatim, including its XML steering tags. */
.agent-content {
  background: #f5f5f7;
  color: #444;
  border: 1px solid #d1d1d6;
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 0.85rem;
  line-height: 1.3;
}

.agent-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-style: italic;
}

.agent-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
  font-size: 0.85rem;
  padding: 0;
}

.icon-btn:hover {
  opacity: 1;
}
</style>
