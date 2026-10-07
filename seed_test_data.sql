-- Test-only rows: a second "Grace Kim" so name lookups can return several customers.
-- Safe to re-run (skips rows that already exist). Remove with:
--   delete from order_items where order_id = 'ORD-1006';
--   delete from orders where order_id = 'ORD-1006';
--   delete from customers where customer_id = 'CUST-006';

insert into customers (customer_id, name, email, phone, account_type, region)
values ('CUST-006', 'Grace Kim', 'grace.kim.dunedin@example.com', '021 555 0106', 'retail', 'Dunedin')
on conflict (customer_id) do nothing;

insert into orders (order_id, customer_id, order_date, status)
values ('ORD-1006', 'CUST-006', '2026-09-25', 'delivered')
on conflict (order_id) do nothing;

insert into order_items (order_id, product_code, quantity, unit_price_charged)
select 'ORD-1006', 'PC-101', 1, 189.00
where not exists (select 1 from order_items where order_id = 'ORD-1006');
