import { api, authState } from '../api';

export class LoginService {
    async login(username: string, password: string): Promise<void> {
        await api.post('/users/auth', { username, password });

        authState.isLoggedIn = true;
        authState.hasChecked = true;

        // NEU: Benutzernamen für den Avatar merken
        localStorage.setItem('username', username);
    }

    async logout(): Promise<void> {
        await api.post('/users/logout');

        authState.isLoggedIn = false;

        // NEU: Benutzernamen beim Logout wieder verwerfen
        localStorage.removeItem('username');
    }
}