import React, { createContext, useContext, useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const AuthContext = createContext();

export function AuthProvider({ children }) {
const [accessToken, setAccessTokenState] = useState(null);
const accessTokenRef = useRef(null);
const navigate = useNavigate();

// keep ref in sync so interceptors can read current token without re-registering
const setAccessToken = (token) => {
accessTokenRef.current = token;
setAccessTokenState(token);
};

// Create axios instance with credentials included so cookies are sent
const api = axios.create({
baseURL: '/',
withCredentials: true,
});

// refresh control
let isRefreshing = false;
let refreshSubscribers = [];

const subscribeTokenRefresh = (cb) => {
refreshSubscribers.push(cb);
};

const onRefreshed = (token) => {
refreshSubscribers.forEach((cb) => cb(token));
refreshSubscribers = [];
};

// Call server to refresh using cookie. Returns new access token or throws.
const refreshToken = useCallback(async () => {
try {
const resp = await axios.post('/api/refresh', null, { withCredentials: true });
const newToken = resp.data?.accessToken;
if (!newToken) throw new Error('No access token in refresh response');
setAccessToken(newToken);
return newToken;
} catch (err) {
setAccessToken(null);
throw err;
}
}, []);

// Request interceptor: attach authorization header from current token
api.interceptors.request.use((config) => {
const token = accessTokenRef.current;
if (token) {
config.headers = config.headers || {};
config.headers.Authorization = `Bearer ${token}`;
}
return config;
});

// Response interceptor: on 401, try refresh once and retry original
api.interceptors.response.use(
(response) => response,
async (error) => {
const originalRequest = error.config;
if (!originalRequest) return Promise.reject(error);

const status = error.response?.status;
// if unauthorized and we haven't already retried this request
if (status === 401 && !originalRequest._retry) {
originalRequest._retry = true;

if (!isRefreshing) {
isRefreshing = true;
try {
const newToken = await refreshToken();
isRefreshing = false;
onRefreshed(newToken);
} catch (e) {
isRefreshing = false;
onRefreshed(null);
// optionally force logout
logout();
return Promise.reject(error);
}
}

// return a promise that resolves once the token is refreshed
return new Promise((resolve, reject) => {
subscribeTokenRefresh((token) => {
if (!token) {
reject(error);
return;
}
originalRequest.headers.Authorization = `Bearer ${token}`;
resolve(api(originalRequest));
});
});
}

return Promise.reject(error);
}
);

const login = async (email, password) => {
// server authenticates, sets refresh cookie, and returns short-lived access token
const resp = await axios.post('/api/login', { email, password }, { withCredentials: true, headers: { 'Content-Type': 'application/json' } });
const token = resp.data?.accessToken;
if (!token) throw new Error('No access token returned from login');
setAccessToken(token);
return true;
};

const logout = async () => {
try {
await axios.post('/api/logout', null, { withCredentials: true });
} catch (e) {
// ignore
}
setAccessToken(null);
navigate('/login', { replace: true });
};

return (
<AuthContext.Provider value={{ accessToken, setAccessToken, api, login, logout }}>
{children}
</AuthContext.Provider>
);
}

export function useAuth() {
return useContext(AuthContext);
}