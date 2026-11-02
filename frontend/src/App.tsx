import { useCallback, useEffect, useState } from 'react';
import { api, isLoggedIn, logout, type Channel, type Order, type OrderStatus, type Product, type Summary } from './api';
import Login from './Login';
import RevenueChart from './RevenueChart';
import { CHANNEL_LABEL, thb } from './format';

const NEXT: Record<OrderStatus, OrderStatus[]> = {
  pending: ['paid', 'cancelled'],
  paid: ['shipped', 'cancelled'],
  shipped: [],
  cancelled: [],
};

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn());
  if (!authed) return <Login onDone={() => setAuthed(true)} />;
  return <Dashboard onLogout={() => { logout(); setAuthed(false); }} />;
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [toast, setToast] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, p, o] = await Promise.all([api.summary(days), api.products(), api.orders()]);
      setSummary(s);
      setProducts(p);
      setOrders(o);
    } catch (err) {
      if (!isLoggedIn()) onLogout();
      else setToast({ kind: 'error', text: err instanceof Error ? err.message : 'Could not load data' });
    }
  }, [days, onLogout]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      setToast({ kind: 'ok', text: ok });
      await load();
    } catch (err) {
      setToast({ kind: 'error', text: err instanceof Error ? err.message : 'Something went wrong' });
    }
  };

  const name = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`;
  const margin = summary && Number(summary.revenue) > 0 ? (Number(summary.gross_profit) / Number(summary.revenue)) * 100 : 0;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>▮▮</span> StockSense
          <span className="muted small">Siam Street Goods · demo shop</span>
        </div>
        <div className="row">
          <label className="muted small">
            Period{' '}
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
            </select>
          </label>
          <button onClick={onLogout}>Sign out</button>
        </div>
      </header>

      {toast && (
        <div className={`toast ${toast.kind}`} role="status" onClick={() => setToast(null)}>
          {toast.text}
        </div>
      )}

      <main className="grid">
        <section className="tiles">
          <Tile label="Revenue" value={summary ? thb(summary.revenue) : '…'} />
          <Tile label="Gross profit" value={summary ? thb(summary.gross_profit) : '…'} note={summary ? `${margin.toFixed(0)}% margin` : ''} />
          <Tile label="Orders" value={summary ? String(summary.orders) : '…'} note="cancelled excluded" />
          <Tile label="Low stock" value={summary ? String(summary.low_stock) : '…'} note="at or below threshold" warn={!!summary?.low_stock} />
        </section>

        <section className="card span-2">
          <h2>Daily revenue</h2>
          {summary && <RevenueChart data={summary.daily} />}
        </section>

        <section className="card">
          <h2>By channel</h2>
          <table>
            <thead>
              <tr><th>Channel</th><th className="num">Orders</th><th className="num">Revenue</th><th className="num">Profit</th></tr>
            </thead>
            <tbody>
              {summary?.by_channel.map((c) => (
                <tr key={c.channel}>
                  <td>{CHANNEL_LABEL[c.channel]}</td>
                  <td className="num">{c.orders}</td>
                  <td className="num">{thb(c.revenue)}</td>
                  <td className="num">{thb(c.gross_profit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <NewOrder products={products} onCreate={(ch, items) => act(() => api.createOrder(ch, items), 'Order placed and stock updated')} />

        <section className="card span-2">
          <h2>Products</h2>
          <div className="scroll">
            <table>
              <thead>
                <tr><th>SKU</th><th>Product</th><th className="num">Price</th><th className="num">Cost</th><th className="num">In stock</th><th /></tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td className="mono">{p.sku}</td>
                    <td>{p.name}</td>
                    <td className="num">{thb(p.sale_price)}</td>
                    <td className="num">{thb(p.cost_price)}</td>
                    <td className="num">
                      {p.is_low_stock && <span className="badge warn">Low</span>} {p.stock_on_hand}
                    </td>
                    <td className="num">
                      <button className="small-btn" onClick={() => act(() => api.restock(p.id, 20), `Added 20 × ${p.sku}`)}>
                        +20
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <h2>Recent orders</h2>
          <ul className="orders">
            {orders.map((o) => (
              <li key={o.id}>
                <div>
                  <strong>#{o.id}</strong> <span className="muted">{CHANNEL_LABEL[o.channel]}</span>
                  <div className="muted small">
                    {o.items.map((i) => `${i.quantity} × ${name(i.product_id)}`).join(', ')}
                  </div>
                </div>
                <div className="order-side">
                  <span className={`badge ${o.status}`}>{o.status}</span>
                  <span className="num">{thb(o.total)}</span>
                  <div className="row">
                    {NEXT[o.status].map((s) => (
                      <button key={s} className="small-btn" onClick={() => act(() => api.setStatus(o.id, s), `Order #${o.id} marked ${s}`)}>
                        {s === 'cancelled' ? 'Cancel' : `Mark ${s}`}
                      </button>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <footer className="muted small">
        FastAPI · PostgreSQL · React + TypeScript ·{' '}
        <a href="https://github.com/NusratBegum/stocksense">Source on GitHub</a> · Built by{' '}
        <a href="https://nusratbegum.dev">Nusrat Begum</a>
      </footer>
    </div>
  );
}

function Tile({ label, value, note, warn }: { label: string; value: string; note?: string; warn?: boolean }) {
  return (
    <div className="card tile">
      <span className="muted small">{label}</span>
      <strong className={warn ? 'warn-text' : ''}>{value}</strong>
      {note && <span className="muted small">{note}</span>}
    </div>
  );
}

function NewOrder({ products, onCreate }: { products: Product[]; onCreate: (c: Channel, items: { product_id: number; quantity: number }[]) => void }) {
  const [channel, setChannel] = useState<Channel>('shopee');
  const [productId, setProductId] = useState<number | ''>('');
  const [qty, setQty] = useState(1);
  const chosen = products.find((p) => p.id === productId);

  return (
    <section className="card">
      <h2>New order</h2>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          if (productId !== '') onCreate(channel, [{ product_id: productId, quantity: qty }]);
        }}
      >
        <label>
          Channel
          <select value={channel} onChange={(e) => setChannel(e.target.value as Channel)}>
            {Object.entries(CHANNEL_LABEL).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Product
          <select value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')} required>
            <option value="">Choose a product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({p.stock_on_hand} left)</option>
            ))}
          </select>
        </label>
        <label>
          Quantity
          <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value)))} />
        </label>
        <button className="primary" disabled={productId === ''}>
          Place order{chosen ? ` · ${thb(Number(chosen.sale_price) * qty)}` : ''}
        </button>
        <p className="muted small">Try ordering more than is in stock: the API refuses instead of overselling.</p>
      </form>
    </section>
  );
}
