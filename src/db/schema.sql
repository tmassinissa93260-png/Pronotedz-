CREATE TABLE IF NOT EXISTS businesses (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('hairdresser', 'fastfood', 'restaurant')),
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  address TEXT NOT NULL,
  timezone TEXT NOT NULL,
  open_hour INTEGER NOT NULL,
  close_hour INTEGER NOT NULL,
  slot_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  name TEXT NOT NULL,
  duration_minutes INTEGER NOT NULL,
  price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price REAL NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_tables (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  capacity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  service_id TEXT NOT NULL REFERENCES services(id),
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  datetime TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS table_reservations (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  table_id TEXT NOT NULL REFERENCES restaurant_tables(id),
  party_size INTEGER NOT NULL,
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  datetime TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  items TEXT NOT NULL,
  total REAL NOT NULL,
  order_type TEXT NOT NULL CHECK (order_type IN ('pickup', 'delivery')),
  address TEXT,
  status TEXT NOT NULL CHECK (status IN ('received', 'preparing', 'ready', 'completed', 'cancelled')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  external_user_id TEXT NOT NULL,
  business_id TEXT NOT NULL REFERENCES businesses(id),
  history TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(channel, external_user_id, business_id)
);
