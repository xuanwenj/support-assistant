import re

from psycopg.rows import dict_row
from db import get_connection

CUSTOMER_COLUMNS = "customer_id, name, email, phone, account_type, region"
ORDER_COLUMNS = "order_id, customer_id, order_date, status"


def _attach_items(cur, orders):
    """Add an `items` list to each order dict using one query for all of them."""
    for order in orders:
        order["items"] = []
    if not orders:
        return orders

    by_id = {order["order_id"]: order for order in orders}
    cur.execute(
        """
        select oi.order_id, oi.product_code, p.name as product_name, oi.quantity, oi.unit_price_charged
        from order_items oi
        join products p on p.product_code = oi.product_code
        where oi.order_id = any(%s)
        order by oi.order_item_id
        """,
        (list(by_id),),
    )
    for item in cur.fetchall():
        by_id[item.pop("order_id")]["items"].append(item)
    return orders


def _normalize_phone(phone):
    """Digits only, with a leading +64 / 64 country code turned into a leading 0."""
    digits = re.sub(r"\D", "", phone or "")
    return re.sub(r"^64", "0", digits)


def get_order(order_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"select {ORDER_COLUMNS} from orders where order_id = %s",
                (order_id,),
            )
            order = cur.fetchone()
            if order is None:
                return None
            _attach_items(cur, [order])

    return order

def get_orders_by_username(username):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select orders.order_id, orders.customer_id, orders.order_date, orders.status
                from orders
                join customers on orders.customer_id = customers.customer_id
                where customers.name = %s
                """,
                (username,),
            )
            orders = _attach_items(cur, cur.fetchall())

    return orders

def get_orders_for_customer(customer_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"select {ORDER_COLUMNS} from orders where customer_id = %s order by order_date, order_id",
                (customer_id,),
            )
            orders = _attach_items(cur, cur.fetchall())

    return orders

def get_customer(customer_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"select {CUSTOMER_COLUMNS} from customers where customer_id = %s",
                (customer_id,),
            )
            return cur.fetchone()

def get_customer_by_email(email):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"select {CUSTOMER_COLUMNS} from customers where lower(email) = lower(%s)",
                (email.strip(),),
            )
            return cur.fetchone()

def get_customer_by_phone(phone):
    # Phones are not unique (shared lines), so this returns a list.
    normalized = _normalize_phone(phone)
    if not normalized:
        return []

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select {CUSTOMER_COLUMNS}
                from customers
                where regexp_replace(regexp_replace(phone, '\\D', '', 'g'), '^64', '0') = %s
                order by customer_id
                """,
                (normalized,),
            )
            return cur.fetchall()

def get_product(product_code):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select product_code, name, category, type, material,
                       min_pressure_kpa, max_pressure_kpa, warranty_terms,
                       retail_price_nzd, trade_price_nzd
                from products
                where product_code = %s
                """,
                (product_code,),
            )
            return cur.fetchone()

if __name__ == "__main__":
    print(get_product("PC-101"))
