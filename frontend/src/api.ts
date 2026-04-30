import axios, { InternalAxiosRequestConfig } from 'axios';
import router from './router';

/**
 * Interface extending the standard Axios config to track retry attempts.
 */
interface CustomAxiosRequestConfig extends InternalAxiosRequestConfig {
    _retry?: boolean;
}

/**
 * Interface for queued requests awaiting token refresh.
 */
interface FailedRequestQueueItem {
    resolve: (value?: unknown) => void;
    reject: (reason?: any) => void;
}

/**
 * Fetches the API base URL from local storage or returns a default fallback.
 * @returns The resolved base URL string.
 */
const getBaseUrl = () => localStorage.getItem('api_url') || 'https://localhost:8000';

export const authState = {
    isLoggedIn: false,
    hasChecked: false
};

export const api = axios.create({
    baseURL: getBaseUrl(),
    withCredentials: true
});

export function updateApiUrl(url: string) {
    localStorage.setItem('api_url', url);
    api.defaults.baseURL = url;
}

// State variables for managing concurrent token refreshes
let isRefreshing = false;
let failedQueue: FailedRequestQueueItem[] = [];

/**
 * Resolves or rejects all queued requests based on the outcome of the refresh operation.
 * * @param error - The error encountered during refresh, if any.
 */
const processQueue = (error: any = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve();
        }
    });
    failedQueue = [];
};

/**
 * Intercepts API responses to handle authentication failures gracefully.
 * Attempts to refresh the session via an HttpOnly refresh token on a 401 response.
 */
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config as CustomAxiosRequestConfig;

        if (error.response && error.response.status === 401 && !originalRequest._retry) {

            // Prevent infinite loops if the refresh or auth routes themselves fail
            if (originalRequest.url === '/users/refresh' || originalRequest.url === '/users/auth') {
                authState.isLoggedIn = false;
                router.push('/login');
                return Promise.reject(error);
            }

            // If a refresh is already in progress, queue the incoming request
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then(() => {
                    return api(originalRequest);
                }).catch(err => {
                    return Promise.reject(err);
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                // Attempt to rotate tokens via the refresh route
                await api.post('/users/refresh');

                // Process queued requests and retry the original one
                processQueue();
                return api(originalRequest);
            } catch (refreshError) {
                // If refresh fails (e.g., refresh token expired), clear state and force login
                processQueue(refreshError);
                authState.isLoggedIn = false;
                router.push('/login');
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);