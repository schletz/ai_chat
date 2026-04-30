<template>
  <div :class="['bubble', message.role]">
    <div class="msg-content" v-html="formattedContent"></div>

    <div class="msg-footer">
      <span class="time">{{ formattedTime }}</span>
      <button
        v-if="message.role === 'user'"
        class="icon-btn delete-btn"
        @click="$emit('delete', message.timestamp)"
        title="Delete message"
      >
        🗑️
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ChatMessage } from "../services/ChatService";

const props = defineProps<{
  message: ChatMessage;
}>();

const emit = defineEmits<{
  (e: "delete", timestamp: number): void;
}>();

/**
 * Processes raw message content by escaping HTML and applying basic markdown formatting.
 */
const formattedContent = computed(() => {
  let text = props.message.content;

  // Escape HTML entities to prevent injection when rendering with v-html
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Apply markdown-like transformations for bold, italic, and inline code
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");
  text = text.replace(/`(.*?)`/g, "<code>$1</code>");

  // Normalize multiple consecutive newlines into a single newline for pre-wrap rendering
  return text.replace(/\n+/g, "\n");
});

/**
 * Formats the message timestamp into a localized time string.
 */
const formattedTime = computed(() => {
  const date = new Date(props.message.timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
});
</script>

<style scoped>
.bubble {
  max-width: 80%;
  padding: 10px 15px;
  border-radius: 15px;
  position: relative;
  word-wrap: break-word;
}

.user {
  align-self: flex-end;
  background-color: #dcf8c6;
  border-bottom-right-radius: 0;
}

.assistant {
  align-self: flex-start;
  background-color: white;
  border-bottom-left-radius: 0;
}

.msg-content {
  white-space: pre-wrap;
  line-height: 1.2;
  color: #111111;
  font-size: 0.95rem;
}

/* Vue :deep() selector required to style elements injected via v-html */
:deep(code) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
  color: #d63384;
}

:deep(strong) {
  font-weight: bold;
}

:deep(em) {
  font-style: italic;
}

.msg-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 0.75rem;
}

.user .msg-footer {
  color: #5b8c5a;
}

.assistant .msg-footer {
  color: #999;
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

.delete-btn {
  font-size: 0.85rem;
  margin: 0;
}
</style>