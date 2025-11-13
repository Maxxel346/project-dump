// Simple demo auth server with refresh-token rotation (in-memory)
// Run: cd server && npm install && npm start

const express = require('express');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const jwt = require('jsonwebtoken');

const app = express();
app.use(express.json());
app.use(cookieParser());

// Allow requests from the React client at http://localhost:3000
app.use(cors({
origin: 'http://localhost:3000',
credentials: true
}));

const PORT = 4000;

// --- Configuration (demo) ---
const ACCESS_TOKEN_SECRET = 'replace-with-strong-secret-in-prod';
const ACCESS_TOKEN_TTL_SECONDS = 60 * 5; // 5 minutes
const REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30; // 30 days
const COOKIE_NAME = 'refreshToken';
const COOKIE_OPTIONS = {
httpOnly: true,
secure: false, // NOTE: set true in production (requires HTTPS)
sameSite: 'lax',
path: '/', // cookie sent to all API endpoints; can restrict to /api/refresh if desired
maxAge: REFRESH_TOKEN_TTL_SECONDS * 1000
};

// --- In-memory stores (for demo) ---
const users = new Map(); // email -> { id, email, passwordHash }
const refreshStore = new Map(); // tokenHash -> { tokenHash, userId, deviceId, expiresAt }

// --- Helpers ---
function randomTokenString() {
return crypto.randomBytes(64).toString('hex');
}

function hashToken(token) {
return crypto.createHash('sha256').update(token).digest('hex');
}

function generateAccessToken(userId) {
const payload = { sub: userId };
return jwt.sign(payload, ACCESS_TOKEN_SECRET, { expiresIn: ACCESS_TOKEN_TTL_SECONDS });
}

function verifyAccessToken(token) {
try {
return jwt.verify(token, ACCESS_TOKEN_SECRET);
} catch (e) {
return null;
}
}

// create a demo user
(async function createDemoUser() {
const password = 'password'; // demo password
const passwordHash = await bcrypt.hash(password, 10);
const user = { id: 'user-1', email: 'user@example.com', passwordHash };
users.set(user.email, user);
console.log('Demo user: email=user@example.com password=password');
})();
// --- Routes ---

// POST /api/login
// body { email, password }
// sets refresh cookie and returns access token in JSON
app.post('/api/login', async (req, res) => {
const { email, password } = req.body || {};
if (!email || !password) return res.status(400).json({ message: 'email and password required' });

const user = users.get(email);
if (!user) return res.status(401).json({ message: 'Invalid credentials' });

const ok = await bcrypt.compare(password, user.passwordHash);
if (!ok) return res.status(401).json({ message: 'Invalid credentials' });

// create device id and refresh token
const deviceId = crypto.randomBytes(12).toString('hex');
const refreshToken = randomTokenString();
const tokenHash = hashToken(refreshToken);
const expiresAt = Date.now() + REFRESH_TOKEN_TTL_SECONDS * 1000;

refreshStore.set(tokenHash, { tokenHash, userId: user.id, deviceId, expiresAt });

// set cookie with refresh token (HttpOnly)
res.cookie(COOKIE_NAME, refreshToken, COOKIE_OPTIONS);

const accessToken = generateAccessToken(user.id);
return res.json({ accessToken });
});

// POST /api/refresh
// Uses cookie refreshToken and rotates it. Returns a new access token and sets new cookie.
app.post('/api/refresh', (req, res) => {
const token = req.cookies[COOKIE_NAME];
if (!token) return res.status(401).json({ message: 'No refresh token' });

const tokenHash = hashToken(token);
const record = refreshStore.get(tokenHash);
if (!record) {
// token not found -> possible reuse or already rotated => deny
// In production you might revoke all sessions for the user and alert.
console.warn('Refresh token not found (possible reuse or revoked)');
res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
return res.status(401).json({ message: 'Invalid refresh token' });
}

if (record.expiresAt < Date.now()) {
refreshStore.delete(tokenHash);
res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
return res.status(401).json({ message: 'Refresh token expired' });
}

// rotate: delete old token record, create new token
refreshStore.delete(tokenHash);

const newRefreshToken = randomTokenString();
const newHash = hashToken(newRefreshToken);
const expiresAt = Date.now() + REFRESH_TOKEN_TTL_SECONDS * 1000;
refreshStore.set(newHash, { tokenHash: newHash, userId: record.userId, deviceId: record.deviceId, expiresAt });

// set new cookie
res.cookie(COOKIE_NAME, newRefreshToken, COOKIE_OPTIONS);

// send new access token
const accessToken = generateAccessToken(record.userId);
return res.json({ accessToken });
});

// POST /api/logout
// clears refresh token cookie and removes server-side record
app.post('/api/logout', (req, res) => {
const token = req.cookies[COOKIE_NAME];
if (token) {
const tokenHash = hashToken(token);
refreshStore.delete(tokenHash);
}
res.clearCookie(COOKIE_NAME, { path: COOKIE_OPTIONS.path });
return res.json({ ok: true });
});

// GET /api/protected
// Requires Authorization: Bearer <accessToken>
app.get('/api/protected', (req, res) => {
const auth = req.headers.authorization;
if (!auth || !auth.startsWith('Bearer ')) return res.status(401).json({ message: 'Missing token' });
const token = auth.slice('Bearer '.length);
const payload = verifyAccessToken(token);
if (!payload) return res.status(401).json({ message: 'Invalid or expired token' });

// return some protected data
return res.json({ message: 'This is protected data', userId: payload.sub, time: Date.now() });
});

// Start server
app.listen(PORT, () => {
console.log(`Auth demo server listening on http://localhost:${PORT}`);
});

