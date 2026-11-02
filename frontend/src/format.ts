const baht = new Intl.NumberFormat('en-TH', { style: 'currency', currency: 'THB', maximumFractionDigits: 0 });

export const thb = (v: string | number) => baht.format(Number(v));

export const CHANNEL_LABEL: Record<string, string> = {
  shopee: 'Shopee',
  lazada: 'Lazada',
  line: 'LINE',
  facebook: 'Facebook',
  store: 'Store',
};

export const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
