import { api, authState } from '../api';

/**
 * Handles user authentication operations including login and logout.
 */
export class LoginService {
    /**
     * Authenticates a user with the provided credentials.
     * @param username - The user's login name.
     * @param password - The user's password.
     */
    async login(username: string, password: string): Promise<void> {
        await api.post('/users/auth', { username, password });

        authState.isLoggedIn = true;
        authState.hasChecked = true;

        localStorage.setItem('username', username);
    }

    /**
     * Logs out the current user and clears local authentication state.
     */
    async logout(): Promise<void> {
        await api.post('/users/logout');

        authState.isLoggedIn = false;

        localStorage.removeItem('username');
    }
}