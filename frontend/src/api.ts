import axios from 'axios';
import router from './router';

/**
 * Fetches the API base URL from local storage or returns a default fallback.
 * @returns The resolved base URL string.
 */
const getBaseUrl = () => localStorage.getItem('api_url') || 'https://localhost:8000';

/**
 * Global authentication state tracking login status and check completion.
 */
export const authState = {
    isLoggedIn: false,
    hasChecked: false
};

/**
 * Axios instance configured with dynamic base URL and credentials enabled.
 */
export const api = axios.create({
    baseURL: getBaseUrl(),
    withCredentials: true
});

/**
 * Updates the API base URL in local storage and refreshes the active instance.
 * @param url - The new base URL to apply.
 */
export function updateApiUrl(url: string) {
    localStorage.setItem('api_url', url);
    api.defaults.baseURL = url;
}

/**
 * Intercepts API responses to handle authentication failures.
 * Resets auth state and redirects to login on 401 Unauthorized errors.
 */
api.interceptors.response.use(
    (response) => response,
    (error) => {
        // Handle unauthorized access by clearing session and redirecting
        if (error.response && error.response.status === 401) {
            authState.isLoggedIn = false;
            router.push('/login');
        }
        return Promise.reject(error);
    }
);