import axios from 'axios';
import router from './router';

const getBaseUrl = () => localStorage.getItem('api_url') || 'https://localhost:8000';

// Globaler Auth-State, damit der Router weiß, ob er prüfen muss
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

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            authState.isLoggedIn = false; // Status zurücksetzen
            router.push('/login');
        }
        return Promise.reject(error);
    }
);