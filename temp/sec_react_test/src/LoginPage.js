import React, { useState } from 'react';
import { useAuth } from './AuthProvider';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
const { login } = useAuth();
const navigate = useNavigate();
const [email, setEmail] = useState('');
const [password, setPassword] = useState('');
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');

const submit = async (e) => {
e.preventDefault();
setError('');
setLoading(true);
try {
await login(email, password);
navigate('/', { replace: true });
} catch (err) {
setError(err.response?.data?.message || err.message || 'Login failed');
} finally {
setLoading(false);
}
};

return (
<div style={{ maxWidth: 420, margin: '4rem auto', padding: '1rem', border: '1px solid #ddd', borderRadius: 6 }}>
<h2>Sign in</h2>
<form onSubmit={submit}>
<div style={{ marginBottom: 12 }}>
<label>
Email
<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required style={{ width: '100%', padding: 8 }} />
</label>
</div>
<div style={{ marginBottom: 12 }}>
<label>
Password
<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required style={{ width: '100%', padding: 8 }} />
</label>
</div>
<button type="submit" disabled={loading} style={{ padding: '8px 16px' }}>
{loading ? 'Signing in...' : 'Sign in'}
</button>
{error && <div style={{ color: 'red', marginTop: 12 }}>{error}</div>}
</form>
<div style={{ marginTop: 12, fontSize: 13, color: '#666' }}>
Refresh token is stored as an HttpOnly cookie (server-side). Access token is kept in memory.
</div>
</div>
);
}