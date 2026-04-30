<template>
  <button
    :type="type || 'button'"
    :class="['async-btn', customClass]"
    :disabled="disabled || isInternalLoading"
    :title="title"
    @click="handleClick"
  >
    <span v-if="isInternalLoading" class="spinner"></span>
    <span v-else class="content"><slot></slot></span>
  </button>
</template>

<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  action: () => Promise<void>;
  disabled?: boolean;
  title?: string;
  customClass?: string;
  type?: "button" | "submit" | "reset"; // <--- NEU
}>();

const isInternalLoading = ref(false);

const handleClick = async () => {
  if (isInternalLoading.value || props.disabled) return;

  isInternalLoading.value = true;
  try {
    await props.action();
  } catch (error) {
    console.error("Fehler bei der Aktion:", error);
    // Optional: Hier könnte man später einen globalen Toast/Alert triggern
    alert("Aktion fehlgeschlagen. Überprüfe die Verbindung.");
  } finally {
    isInternalLoading.value = false;
  }
};
</script>

<style scoped>
.async-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Der kleine Ladekreis */
.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: inherit; /* Passt sich an die Schriftfarbe an */
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.content {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}
</style>
