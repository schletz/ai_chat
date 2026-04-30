<template>
  <div :class="['bubble', message.role]">
    <!-- v-html rendert die generierten <strong> und <code> Tags -->
    <div class="msg-content" v-html="formattedContent"></div>

    <div class="msg-footer">
      <span class="time">{{ formattedTime }}</span>
      <button v-if="message.role === 'user'" class="icon-btn delete-btn" @click="$emit('delete', message.timestamp)"
        title="Nachricht löschen">
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

// Unser Parser
const formattedContent = computed(() => {
  let text = props.message.content;
  // HTML escapen (WICHTIG für Sicherheit bei v-html!)
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Markdown parsen
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>"); // **fett**
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>"); // *kursiv* (wie bei "zu" und "alles")
  text = text.replace(/`(.*?)`/g, "<code>$1</code>"); // `code` (wie bei "flexbox")
  text = text.replace(/\n+/g, "\n"); // Mehrere Zeilenumbrüche auf 1 ändern (für white-space: pre-wrap)

  return text;
});

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
  /* NEU: Erzwingt einen sehr hohen Kontrast */
  font-size: 0.95rem;
  /* Optional: Macht die Schrift minimal größer, falls gewünscht */
}

/* WICHTIG: :deep() ist nötig, weil v-html die Tags nachträglich einfügt 
   und das scoped CSS sie sonst nicht findet. */
:deep(code) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
  color: #d63384;
  /* Ein dezentes Rosa/Rot, ähnlich wie bei Github */
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
