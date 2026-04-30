<template>
  <div class="header">
    <div class="header-left">
      <button class="avatar-btn" @click="confirmLogout" title="Abmelden">
        {{ userInitial }}
      </button>
      <button class="icon-btn" @click="$router.push('/settings')">⚙️</button>
    </div>

    <span>Chats</span>

    <div class="header-right">
      <button class="icon-btn" @click="$router.push('/character/add')">➕</button>
    </div>
  </div>

  <div class="content list-container">
    <div v-if="isLoading" class="loading">Lade Charaktere...</div>

    <div v-else-if="characters.length === 0" class="empty-state">
      Noch keine Charaktere vorhanden. Klicke auf ➕ um einen zu erstellen!
    </div>

    <div v-else class="character-list">
      <div v-for="char in characters" :key="char.name" class="character-item"
        @click="$router.push(`/chat/${char.name}`)">
        <div class="avatar">{{ char.name.charAt(0).toUpperCase() }}</div>
        <div class="char-info">
          <h3>{{ char.name }}</h3>
          <p class="preview-text">Tippe, um den Chat zu öffnen...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { CharacterListService, Character } from "../services/CharacterListService";
import { LoginService } from "../services/LoginService";

const router = useRouter();
const characterService = new CharacterListService();
const loginService = new LoginService();

const characters = ref<Character[]>([]);
const isLoading = ref(true);

// Retrieve username from local storage and compute the initial character.
const username = ref(localStorage.getItem("username") || "?");
const userInitial = computed(() => username.value.charAt(0).toUpperCase());

/**
 * Handles user logout with a confirmation prompt.
 */
const confirmLogout = async () => {
  if (confirm(`Möchtest du dich als "${username.value}" abmelden?`)) {
    try {
      await loginService.logout();
    } catch (error) {
      console.error("Fehler beim Logout", error);
    } finally {
      router.push("/login");
    }
  }
};

onMounted(async () => {
  try {
    characters.value = await characterService.getCharacters();
  } catch (error) {
    console.error("Fehler beim Laden der Charaktere", error);
  } finally {
    isLoading.value = false;
  }
});
</script>

<style scoped>
/* Header Layout */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 60px;
}

.header-right {
  justify-content: flex-end;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: white;
  padding: 0;
}

.avatar-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background-color: white;
  color: #075e54;
  border: none;
  font-weight: bold;
  font-size: 1.1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transition: transform 0.1s;
}

.avatar-btn:active {
  transform: scale(0.95);
}

/* List Container */
.list-container {
  padding: 0;
}

.character-item {
  display: flex;
  align-items: center;
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
  background: white;
  cursor: pointer;
}

.character-item:active {
  background-color: #f5f5f5;
}

.avatar {
  width: 50px;
  height: 50px;
  background-color: #075e54;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: bold;
  margin-right: 15px;
}

.char-info h3 {
  margin: 0 0 5px 0;
  font-size: 1.1rem;
  color: #000;
}

.preview-text {
  margin: 0;
  color: #777;
  font-size: 0.9rem;
}

.loading,
.empty-state {
  text-align: center;
  padding: 30px;
  color: #666;
}
</style>