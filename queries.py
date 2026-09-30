from psycopg.rows import dict_row
from db import get_connection

def get_order(order_id):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "select order_id, customer_id, order_date, status from orders where order_id = %s",
                (order_id,),
            )
            order = cur.fetchone()
            if order is None:
                return None

            cur.execute(
                """
                select oi.product_code, p.name as product_name, oi.quantity, oi.unit_price_charged
                from order_items oi
                join products p on p.product_code = oi.product_code
                where oi.order_id = %s
                """,
                (order_id,),
            )
            order["items"] = cur.fetchall()

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
            orders = cur.fetchall()

            for order in orders:
                cur.execute(
                    """
                    select oi.product_code, p.name as product_name, oi.quantity, oi.unit_price_charged
                    from order_items oi
                    join products p on p.product_code = oi.product_code
                    where oi.order_id = %s
                    """,
                    (order["order_id"],),
                )
                order["items"] = cur.fetchall()

    return orders

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