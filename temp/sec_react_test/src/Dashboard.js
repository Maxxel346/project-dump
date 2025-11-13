import React, { useState } from 'react';
import { useAuth } from './AuthProvider';

export default function Dashboard() {
const { api, logout } = useAuth();
const [msg, setMsg] = useState('');
const [loading, setLoading] = useState(false);

const callProtected = async () => {
setLoading(true);
setMsg('');
try {
const r = await api.get('/api/protected'); // server requires Authorization header
setMsg(JSON.stringify(r.data));
} catch (err) {
setMsg('Error: ' + (err.response?.status || err.message));
} finally {
setLoading(false);
}
};

return (
<div style={{ maxWidth: 800, margin: '3rem auto' }}>
<h2>Dashboard (Protected)</h2>
<div style={{ marginBottom: 12 }}>
<button onClick={callProtected} disabled={loading} style={{ marginRight: 8 }}>
{loading ? 'Loading...' : 'Call Protected API'}
</button>
<button onClick={logout}>Logout</button>
</div>
<pre style={{ background: '#f6f8fa', padding: 12 }}>{msg}</pre>
</div>
);
}