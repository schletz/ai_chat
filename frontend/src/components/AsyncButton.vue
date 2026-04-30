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

/**
 * Props for the AsyncButton component.
 */
const props = defineProps<{
  /** Action to execute on click. Must return a Promise. */
  action: () => Promise<void>;
  /** Disables the button when true. */
  disabled?: boolean;
  /** Optional title attribute for accessibility or tooltips. */
  title?: string;
  /** Additional CSS classes applied to the button element. */
  customClass?: string;
  /** HTML button type (button, submit, reset). Defaults to 'button'. */
  type?: "button" | "submit" | "reset";
}>();

const isInternalLoading = ref(false);

/**
 * Handles the click event. Manages loading state and error catching.
 */
const handleClick = async () => {
  if (isInternalLoading.value || props.disabled) return;

  isInternalLoading.value = true;
  try {
    await props.action();
  } catch (error) {
    console.error("Error during action execution:", error);
    alert("Action failed. Please check your connection.");
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
  overflow: hidden;
  line-height: 1;
  padding: 0;
  appearance: none;
  -webkit-appearance: none;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: inherit;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  line-height: 1;
}
</style>