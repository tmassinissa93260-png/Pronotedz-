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

-- Deduplication des evenements webhook entrants (protection contre le replay
-- / les retries de Meta en cas de reponse lente ou d'erreur transitoire).
CREATE TABLE IF NOT EXISTS processed_events (
  channel TEXT NOT NULL,
  event_id TEXT NOT NULL,
  processed_at TEXT NOT NULL,
  PRIMARY KEY (channel, event_id)
);

CREATE INDEX IF NOT EXISTS idx_bookings_business_datetime ON bookings(business_id, datetime);
CREATE INDEX IF NOT EXISTS idx_bookings_business_status ON bookings(business_id, status);
CREATE INDEX IF NOT EXISTS idx_table_reservations_business_datetime ON table_reservations(business_id, datetime);
CREATE INDEX IF NOT EXISTS idx_table_reservations_business_status ON table_reservations(business_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_business_created ON orders(business_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_business_phone_created ON orders(business_id, customer_phone, created_at);
-- Pas d'index supplementaire pour conversations: la contrainte UNIQUE ci-dessus
-- cree deja un index couvrant (channel, external_user_id, business_id).
