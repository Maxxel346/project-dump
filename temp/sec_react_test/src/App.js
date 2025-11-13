import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './LoginPage';
import Dashboard from './Dashboard';
import { useAuth } from './AuthProvider';
import ProtectedRoute from './ProtectedRoute';

export default function App() {
const { accessToken } = useAuth();

return (
<Routes>
<Route path="/login" element={<LoginPage />} />
<Route
path="/"
element={
<ProtectedRoute>
<Dashboard />
</ProtectedRoute>
}
/>
<Route path="*" element={<Navigate to={accessToken ? '/' : '/login'} replace />} />
</Routes>
);
}