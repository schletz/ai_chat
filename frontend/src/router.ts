import { createRouter, createWebHashHistory } from 'vue-router';
import { api, authState } from './api';

import LoginView from './views/LoginView.vue';
import CharacterListView from './views/CharacterListView.vue';
import ChatView from './views/ChatView.vue';
import SettingsView from './views/SettingsView.vue';
import CharacterFormView from './views/CharacterFormView.vue';

const routes = [
    { path: '/login', component: LoginView },
    // Settings bleibt OHNE requiresAuth, damit man die URL vor dem Login fixen kann
    { path: '/settings', component: SettingsView },

    // Geschützte Routen
    { path: '/', component: CharacterListView, meta: { requiresAuth: true } },
    { path: '/character/add', component: CharacterFormView, meta: { requiresAuth: true } },
    { path: '/character/:name/edit', component: CharacterFormView, props: true, meta: { requiresAuth: true } },
    { path: '/chat/:name', component: ChatView, props: true, meta: { requiresAuth: true } },
];

const router = createRouter({
    history: createWebHashHistory(),
    routes,
});

router.beforeEach(async (to) => {
    if (to.meta.requiresAuth) {
        if (!authState.hasChecked) {
            try {
                await api.get('/characters');
                authState.isLoggedIn = true;
            } catch (error) {
                authState.isLoggedIn = false;
            } finally {
                authState.hasChecked = true;
            }
        }
        if (authState.isLoggedIn) {
            return true;
        } else {
            return '/login';
        }
    }
    return true;
});

export default router;