-- Reconstructed from information_schema / pg_constraint on 2026-10-07, not the original DDL.
-- Structure only, no data. Indexes other than the primary-key/unique ones are not captured.

create table customers (
    customer_id  text primary key,
    name         text not null,
    email        text not null unique,
    phone        text,
    account_type text not null check (account_type in ('retail', 'trade')),
    region       text,
    created_at   timestamptz not null default now()
);

create table products (
    product_code     text primary key,
    name             text not null,
    category         text,
    type             text,
    material         text,
    min_pressure_kpa integer,
    max_pressure_kpa integer,
    warranty_terms   text,
    retail_price_nzd numeric not null,
    trade_price_nzd  numeric not null
);

create table orders (
    order_id    text primary key,
    customer_id text not null references customers (customer_id),
    order_date  date not null,
    status      text not null check (status in ('pending', 'delivered', 'partially_returned', 'returned', 'cancelled'))
);

create table order_items (
    order_item_id      bigint primary key,  -- generated always as identity
    order_id           text not null references orders (order_id),
    product_code       text not null references products (product_code),
    quantity           integer not null check (quantity > 0),
    unit_price_charged numeric not null
);
