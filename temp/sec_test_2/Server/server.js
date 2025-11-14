// Simple demo auth server with refresh-token rotation (in-memory)
// Run: cd server && npm install && npm start

const express = require('express');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const db = require('./db');

const app = express();
app.use(express.json());
app.use(cookieParser());

app.use(cors({
  origin: 'http://localhost:3000',
  credentials: true
}));

const PORT = 4000;

const ACCESS_TOKEN_SECRET = 'replace-with-strong-secret-in-prod';
const ACCESS_TOKEN_TTL_SECONDS = 60 * 5;
const REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30;
const COOKIE_NAME = 'refreshToken';
const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: false, // true in prod w/ HTTPS
  sameSite: 'lax',
  path: '/',
  maxAge: REFRESH_TOKEN_TTL_SECONDS * 1000
};

function randomTokenString() {
  return crypto.randomBytes(64).toString('hex');
}

function hashToken(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

function generateAccessToken(userId) {
  return jwt.sign({ sub: userId }, ACCESS_TOKEN_SECRET, { expiresIn: ACCESS_TOKEN_TTL_SECONDS });
}

function verifyAccessToken(token) {
  try {
    return jwt.verify(token, ACCESS_TOKEN_SECRET);
  } catch {
    return null;
  }
}

// REGISTER
app.post('/api/register', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ message: 'Email and password required' });

  try {
    // Check if user exists
    const userExists = await db.query('SELECT id FROM users WHERE email = $1', [email]);
    if (userExists.rows.length > 0) {
      return res.status(409).json({ message: 'Email already in use' });
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, 10);

    // Insert user
    const result = await db.query(
      'INSERT INTO users(email, password_hash) VALUES($1, $2) RETURNING id',
      [email, passwordHash]
    );

    const userId = result.rows[0].id;

    return res.status(201).json({ message: 'User registered', userId });
  } catch (err) {
    console.error('Register error', err);
    return res.status(500).json({ message: 'Internal server error' });
  }
});

// LOGIN (adapted to DB)
app.post('/api/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ message: 'Email and password required' });

  try {
    const userResult = await db.query('SELECT id, password_hash FROM users WHERE email = $1', [email]);
    if (userResult.rows.length === 0) return res.status(401).json({ message: 'Invalid credentials' });

    const user = userResult.rows[0];
    const ok = await bcrypt.compare(password, user.password_hash);
    if (!ok) return res.status(401).json({ message: 'Invalid credentials' });

    const deviceId = crypto.randomBytes(12).toString('hex');
    const refreshToken = randomTokenString();
    const tokenHash = hashToken(refreshToken);
    const expiresAt = new Date(Date.now() + REFRESH_TOKEN_TTL_SECONDS * 1000);

    await db.query('INSERT INTO refresh_tokens(token_hash, user_id, device_id, expires_at) VALUES ($1, $2, $3, $4)', [
      tokenHash, user.id, deviceId, expiresAt
    ]);

    res.cookie(COOKIE_NAME, refreshToken, COOKIE_OPTIONS);

    const accessToken = generateAccessToken(user.id);
    return res.json({ accessToken });
  } catch (err) {
    console.error('Login error', err);
    return res.status(500).json({ message: 'Internal server error' });
  }
});

// REFRESH (rotate with transaction)
app.post('/api/refresh', async (req, res) => {
  const token = req.cookies[COOKIE_NAME];
  if (!token) return res.status(401).json({ message: 'No refresh token' });

  const tokenHash = hashToken(token);
  const client = await db.getClient();

  try {
    await client.query('BEGIN');

    const result = await client.query('SELECT token_hash, user_id, device_id, expires_at FROM refresh_tokens WHERE token_hash = $1 FOR UPDATE', [tokenHash]);
    if (result.rows.length === 0) {
      // Maybe reuse attack, revoke sessions here
      await client.query('COMMIT');
      res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
      return res.status(401).json({ message: 'Invalid refresh token' });
    }

    const record = result.rows[0];
    if (new Date(record.expires_at) < new Date()) {
      // expired
      await client.query('DELETE FROM refresh_tokens WHERE token_hash = $1', [tokenHash]);
      await client.query('COMMIT');
      res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
      return res.status(401).json({ message: 'Refresh token expired' });
    }

    // rotate: delete old token and insert new one
    await client.query('DELETE FROM refresh_tokens WHERE token_hash = $1', [tokenHash]);

    const newRefreshToken = randomTokenString();
    const newHash = hashToken(newRefreshToken);
    const expiresAt = new Date(Date.now() + REFRESH_TOKEN_TTL_SECONDS * 1000);

    await client.query('INSERT INTO refresh_tokens(token_hash, user_id, device_id, expires_at) VALUES ($1, $2, $3, $4)', [
      newHash, record.user_id, record.device_id, expiresAt
    ]);

    await client.query('COMMIT');

    res.cookie(COOKIE_NAME, newRefreshToken, COOKIE_OPTIONS);

    const accessToken = generateAccessToken(record.user_id);
    return res.json({ accessToken });
  } catch (err) {
    await client.query('ROLLBACK');
    console.error('Refresh error', err);
    res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
    return res.status(401).json({ message: 'Could not refresh token' });
  } finally {
    client.release();
  }
});

// LOGOUT (delete refresh token)
app.post('/api/logout', async (req, res) => {
  const token = req.cookies[COOKIE_NAME];
  if (token) {
    const tokenHash = hashToken(token);
    try {
      await db.query('DELETE FROM refresh_tokens WHERE token_hash = $1', [tokenHash]);
    } catch (e) {
      console.warn('Logout DB error', e);
    }
  }
  res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
  res.json({ ok: true });
});

// PROTECTED route (same)
app.get('/api/protected', async (req, res) => {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) return res.status(401).json({ message: 'Missing token' });
  const token = auth.slice('Bearer '.length);
  const payload = verifyAccessToken(token);
  if (!payload) return res.status(401).json({ message: 'Invalid or expired token' });
  return res.json({ message: 'This is protected data', userId: payload.sub, time: Date.now() });
});

app.listen(PORT, () => {
  console.log(`Auth server listening on http://localhost:${PORT}`);
});