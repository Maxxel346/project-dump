import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);

    try {
      const resp = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'include',
      });

      if (resp.ok) {
        alert('Registration successful, please login');
        navigate('/login');
      } else {
        const json = await resp.json();
        setError(json.message || 'Registration failed');
      }
    } catch (e) {
      setError('Request failed: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '2rem auto', padding: 16, border: '1px solid #ccc', borderRadius: 6 }}>
      <h2>Register</h2>
      <form onSubmit={submit}>
        <label>
          Email
          <input type="email" value={email} required onChange={(e) => setEmail(e.target.value)} style={{ width: '100%', padding: 8, marginTop: 6 }} />
        </label>
        <label style={{ marginTop: 12 }}>
          Password
          <input type="password" value={password} required onChange={(e) => setPassword(e.target.value)} style={{ width: '100%', padding: 8, marginTop: 6 }} />
        </label>
        <label style={{ marginTop: 12 }}>
          Confirm Password
          <input type="password" value={confirm} required onChange={(e) => setConfirm(e.target.value)} style={{ width: '100%', padding: 8, marginTop: 6 }} />
        </label>
        {error && <div style={{ color: 'red', marginTop: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{ marginTop: 16, padding: '8px 16px' }}>
          {loading ? 'Registering...' : 'Register'}
        </button>
      </form>
    </div>
  );
}