import { FormEvent, useState } from 'react';
import { login } from './api';

export default function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState('demo@stocksense.dev');
  const [password, setPassword] = useState('demo-shop-2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="card login-card" onSubmit={submit}>
        <h1>StockSense</h1>
        <p className="muted">Inventory, orders and profit for shops selling on Shopee, Lazada, LINE and Facebook.</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to the demo shop'}</button>
        <p className="muted small">The demo login is filled in. Data resets are not guaranteed, so feel free to place orders.</p>
      </form>
    </main>
  );
}
