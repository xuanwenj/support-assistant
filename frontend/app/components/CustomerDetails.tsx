export type Customer = {
  customer_id: string;
  name: string;
  email: string;
  phone: string | null;
  account_type: string;
  region: string | null;
};

type OrderItem = {
  product_code: string;
  product_name: string;
  quantity: number;
  unit_price_charged: string;
};

type Order = {
  order_id: string;
  customer_id: string;
  order_date: string;
  status: string;
  items: OrderItem[];
};

export type CustomerDetail = {
  customer: Customer;
  orders: Order[];
};

const money = new Intl.NumberFormat("en-NZ", { style: "currency", currency: "NZD" });

export default function CustomerDetails({ detail }: { detail: CustomerDetail }) {
  const { customer, orders } = detail;
  const fields: [string, string][] = [
    ["Customer ID", customer.customer_id],
    ["Email", customer.email],
    ["Phone", customer.phone ?? "Not on file"],
    ["Account type", customer.account_type],
    ["Region", customer.region ?? "Not on file"],
  ];

  return (
    <section className="mt-6">
      <h2 className="text-xl font-semibold">{customer.name}</h2>
      <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
        {fields.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-zinc-600 dark:text-zinc-400">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-6 font-semibold">Orders</h3>
      {orders.length === 0 ? (
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">This customer has no orders.</p>
      ) : (
        <ul className="mt-2 space-y-4">
          {orders.map((order) => (
            <li key={order.order_id} className="rounded border p-3">
              <p className="font-medium">
                {order.order_id}
                <span className="ml-3 font-normal text-zinc-600 dark:text-zinc-400">
                  {order.order_date} · {order.status}
                </span>
              </p>
              <ul className="mt-2 text-sm">
                {order.items.map((item, i) => (
                  <li key={`${item.product_code}-${i}`}>
                    {item.quantity} × {item.product_name} ({item.product_code}) at{" "}
                    {money.format(Number(item.unit_price_charged))}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
