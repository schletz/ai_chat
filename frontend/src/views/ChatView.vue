<template>
  <div class="header">
    <button @click="$router.push('/')">← Zurück</button>
    <span>{{ name }}</span>
    <button @click="$router.push(`/character/${name}/edit`)">⚙️</button>
  </div>

  <div class="content chat-window" ref="chatContainer">
    <template v-for="(msg, index) in messages" :key="msg.timestamp">
      <div v-if="showDateSeparator(index)" class="date-separator">
        <span>{{ formatDateSeparator(msg.timestamp) }}</span>
      </div>

      <ChatMessageBubble :message="msg" @delete="deleteMsg" />
    </template>
  </div>

  <div class="input-area">
    <AsyncButton
      v-if="messages.length > 0"
      :action="recreate"
      customClass="action-btn"
      :title="
        messages[messages.length - 1].role === 'assistant'
          ? 'Neu generieren'
          : 'Antworten'
      "
    >
      {{ messages[messages.length - 1].role === "assistant" ? "↻" : "↩" }}
    </AsyncButton>

    <textarea
      ref="messageInput"
      v-model="newMessage"
      @keydown="handleKeydown"
      @input="autoResize"
      placeholder="Nachricht..."
      rows="1"
    ></textarea>

    <AsyncButton
      ref="sendButtonRef"
      :action="send"
      :disabled="!newMessage.trim()"
      customClass="action-btn send-btn"
      title="Senden"
    >
      ➤
    </AsyncButton>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { ChatService, ChatMessage } from "../services/ChatService";
import AsyncButton from "../components/AsyncButton.vue";
import ChatMessageBubble from "../components/ChatMessageBubble.vue";

const props = defineProps<{ name: string }>();
const chatService = new ChatService(props.name);

const messages = ref<ChatMessage[]>([]);
const newMessage = ref("");
const chatContainer = ref<HTMLElement | null>(null);
const messageInput = ref<HTMLTextAreaElement | null>(null);

const sendButtonRef = ref<InstanceType<typeof AsyncButton> | null>(null);

/** Loads the chat history and scrolls to the latest message. */
const loadChat = async () => {
  messages.value = await chatService.getHistory();
  scrollToBottom();
};

/** Handles keyboard events, triggering the send action on Shift+Enter. */
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && e.shiftKey) {
    e.preventDefault();

    // Programmatically trigger the send button when text is present
    if (newMessage.value.trim() && sendButtonRef.value) {
      const btnElement = sendButtonRef.value.$el as HTMLButtonElement;
      if (btnElement && !btnElement.disabled) {
        btnElement.click();
      }
    }
  }
};

/** Dynamically adjusts the textarea height to fit content up to a maximum. */
const autoResize = () => {
  if (!messageInput.value) return;
  messageInput.value.style.height = "auto";
  const newHeight = Math.min(messageInput.value.scrollHeight, 120);
  messageInput.value.style.height = `${newHeight}px`;
};

/** Scrolls the chat container to the bottom after a DOM update cycle. */
const scrollToBottom = async () => {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
};

/** Determines whether to render a date separator for the given message index. */
const showDateSeparator = (index: number) => {
  if (index === 0) return true;

  const currentDate = new Date(messages.value[index].timestamp).setHours(0, 0, 0, 0);
  const prevDate = new Date(messages.value[index - 1].timestamp).setHours(0, 0, 0, 0);

  return currentDate !== prevDate;
};

/** Formats a message timestamp into a localized date header string. */
const formatDateSeparator = (timestamp: number) => {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return "Heute";
  } else if (date.toDateString() === yesterday.toDateString()) {
    return "Gestern";
  } else {
    return date.toLocaleDateString("de-DE", {
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }
};

/** Handles sending a user message and refreshing the chat state. */
const send = async () => {
  const text = newMessage.value;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  // Optimistically update UI before awaiting server response
  messages.value.push({ timestamp: Date.now(), role: "user", content: text });
  scrollToBottom();

  await chatService.sendMessage(text);
  await loadChat();
};

/** Removes a specific message by timestamp and refreshes the chat list. */
const deleteMsg = async (timestamp: number) => {
  await chatService.deleteMessage(timestamp);
  await loadChat();
};

/** Triggers regeneration of the most recent assistant message. */
const recreate = async () => {
  await chatService.recreateAnswer();
  await loadChat();
};

onMounted(loadChat);
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-area {
  padding: 10px;
  background: #f0f0f0;
  display: flex;
  gap: 8px;
  align-items: center;
}
.input-area input {
  flex: 1;
  padding: 12px 15px;
  border-radius: 25px;
  border: 1px solid #ccc;
  font-size: 1rem;
  outline: none;
}

/* Neue Button Styles */
.action-btn {
  width: 45px;
  height: 45px;
  border-radius: 50%;
  border: none;
  background-color: #075e54;
  color: white;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.2s;
}
.action-btn:disabled {
  background-color: #a0a0a0;
  cursor: default;
}
.action-btn:active:not(:disabled) {
  background-color: #128c7e;
}

.send-btn {
  font-size: 1.4rem;
  padding-left: 4px; /* Optischer Ausgleich für den Pfeil */
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
.msg-actions {
  font-size: 0.8rem;
  margin-top: 5px;
  text-align: right;
}
.input-area {
  padding: 10px;
  background: #f0f0f0;
  display: flex;
  gap: 8px;
  align-items: flex-end; /* NEU: Buttons bleiben unten */
}

/* Neues Textarea-Styling */
.input-area textarea {
  flex: 1;
  padding: 12px 15px;
  border-radius: 20px;
  border: 1px solid #ccc;
  font-size: 1rem;
  outline: none;
  resize: none; /* Verhindert das manuelle Ziehen am Rand */
  font-family: inherit;
  line-height: 1.4;
  max-height: 120px; /* Nach ca. 5 Zeilen fängt es intern an zu scrollen */
  overflow-y: auto;
  box-sizing: border-box;
  /* Verhindert Scrollbar-Flackern bei kurzen Texten */
  scrollbar-width: thin;
}

/* Dezentere Farben für die Uhrzeit je nach Blase */
.user {
  color: #5b8c5a;
}
.assistant {
  color: #999;
}

/* Der Container zentriert die Pille */
.date-separator {
  display: flex;
  justify-content: center;
  margin: 15px 0 10px 0;
  width: 100%;
}

/* Die WhatsApp-typische Datums-Pille */
.date-separator span {
  background-color: #e1f3fb; /* Leichtes hellblau/grau */
  color: #555;
  font-size: 0.8rem;
  font-weight: bold;
  padding: 6px 14px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>