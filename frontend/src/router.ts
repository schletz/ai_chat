import { createRouter, createWebHashHistory } from 'vue-router';
import { api, authState } from './api';

import LoginView from './views/LoginView.vue';
import CharacterListView from './views/CharacterListView.vue';
import ChatView from './views/ChatView.vue';
import SettingsView from './views/SettingsView.vue';
import CharacterFormView from './views/CharacterFormView.vue';

/**
 * Application route definitions.
 */
const routes = [
    { path: '/login', component: LoginView },
    { path: '/settings', component: SettingsView },

    // Protected routes requiring authentication
    { path: '/', component: CharacterListView, meta: { requiresAuth: true } },
    { path: '/character/add', component: CharacterFormView, meta: { requiresAuth: true } },
    { path: '/character/:name/edit', component: CharacterFormView, props: true, meta: { requiresAuth: true } },
    { path: '/chat/:name', component: ChatView, props: true, meta: { requiresAuth: true } },
];

/**
 * Initializes the Vue Router instance with hash-based history.
 */
const router = createRouter({
    history: createWebHashHistory(),
    routes,
});

/**
 * Navigation guard that verifies authentication status before allowing access to protected routes.
 * @param {import('vue-router').RouteLocationNormalized} to - Target route object.
 * @returns {boolean|string|undefined} Navigation result or redirect path.
 */
router.beforeEach(async (to) => {
    if (to.meta.requiresAuth) {
        // Perform initial auth check only once per session
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