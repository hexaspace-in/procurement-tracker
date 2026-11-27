# procurement-tracker

Procurement for interior and construction projects, from the signed BOQ to installation. Plain Python, no dependencies.

- **Status flow**: To order → Ordered → In production → Dispatched → Delivered → Installed
- **Need-by date** per item from the project plan. Site materials are needed before site work starts; furniture, soft furnishing and appliances before handover
- **Order-by date** = need-by minus the lead time. Typical Indian lead times per category are included; override them per item
- **Late flags**: not ordered by its order-by date, or delivery overdue, with the number of days
- **Purchase-order maths**: taxable value, GST, total, advance %, paid and due. A PO can't be sent until every rate is filled
- **Next actions** list, most urgent first: order now, chase the vendor, order soon, delivery due
- **Vendor quote comparison**: the cheapest quote (incl. GST) that still arrives in time, with the other quotes and why they lost

Built from the procurement flow Hexaspace runs on real projects. Pairs with [interior-boq](https://github.com/hexaspace-in/interior-boq) and [interior-project-plan](https://github.com/hexaspace-in/interior-project-plan).

## Example

```python
from procurement_tracker import need_by, order_by, next_actions, po_amounts, compare_quotes

need = need_by("carpentry", site_start="2027-01-10", handover_start="2027-02-10")
item = {"id": "1", "status": "to_order", "order_by": order_by(need, "carpentry")}
next_actions([item])
compare_quotes(quotes, need=need)
```

## Licence

MIT. Maintained by [Hexaspace](https://hexaspace.in).
