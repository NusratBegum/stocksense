const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export type Channel = 'shopee' | 'lazada' | 'line' | 'facebook' | 'store';
export type OrderStatus = 'pending' | 'paid' | 'shipped' | 'cancelled';

export interface Product {
  id: number;
  sku: string;
  name: string;
  cost_price: string;
  sale_price: string;
  stock_on_hand: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
}

export interface Order {
  id: number;
  channel: Channel;
  status: OrderStatus;
  created_at: string;
  items: { product_id: number; quantity: number; unit_price: string }[];
  total: string;
}

export interface Summary {
  revenue: string;
  gross_profit: string;
  orders: number;
  low_stock: number;
  by_channel: { channel: Channel; orders: number; revenue: string; gross_profit: string }[];
  daily: { day: string; revenue: string }[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let token: string | null = sessionStorage.getItem('stocksense-token');

export const isLoggedIn = () => token !== null;

export function logout() {
  token = null;
  sessionStorage.removeItem('stocksense-token');
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !(init.body instanceof URLSearchParams)) headers.set('Content-Type', 'application/json');
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && token) logout();
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === 'string' ? detail : detail?.message ?? (Array.isArray(detail) ? detail[0]?.msg : `Request failed (${res.status})`);
    throw new ApiError(res.status, message);
  }
  return res.json();
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const res = await request<{ access_token: string }>('/api/v1/auth/token', { method: 'POST', body });
  token = res.access_token;
  sessionStorage.setItem('stocksense-token', token);
}

export const api = {
  summary: (days: number) => request<Summary>(`/api/v1/analytics/summary?days=${days}`),
  products: () => request<Product[]>('/api/v1/products'),
  orders: () => request<Order[]>('/api/v1/orders?limit=20'),
  createOrder: (channel: Channel, items: { product_id: number; quantity: number }[]) =>
    request<Order>('/api/v1/orders', {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({ channel, items }),
    }),
  setStatus: (id: number, status: OrderStatus) =>
    request<Order>(`/api/v1/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  restock: (product_id: number, change: number) =>
    request('/api/v1/inventory/movements', {
      method: 'POST',
      body: JSON.stringify({ product_id, change, reason: 'purchase', note: 'Restock from dashboard' }),
    }),
};
