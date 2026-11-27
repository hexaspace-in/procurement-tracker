"""Procurement from a signed BOQ: item status flow, need-by and order-by dates, late flags, purchase-order maths,
next actions, and vendor quote comparison.

Item: {"id", "name", "category", "qty", "status", "need_by"?, "order_by"?, "expected_delivery"?}
Dates are ISO strings (YYYY-MM-DD).
"""
from datetime import date, timedelta
from typing import Dict, List, Optional

FLOW = ["to_order", "ordered", "in_production", "dispatched", "delivered", "installed"]
FLOW_LABEL = {"to_order": "To order", "ordered": "Ordered", "in_production": "In production", "dispatched": "Dispatched",
              "delivered": "Delivered", "installed": "Installed"}
# Typical lead times in days for Indian interior work; override per item or per category.
LEAD_DAYS = {"carpentry": 21, "furniture": 30, "appliances": 10, "soft": 14, "electrical": 7, "plumbing": 7,
             "flooring": 14, "paint": 5, "civil": 7, "services": 0}
LATE_STAGE = {"furniture", "soft", "appliances"}   # needed before handover; the rest before site work starts
DEFAULT_GST = 18.0


class ProcurementError(ValueError):
    pass


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s[:10]) if s else None


def next_status(current: str) -> str:
    """The next step in the flow. Raises at the end."""
    i = FLOW.index(current)
    if i == len(FLOW) - 1:
        raise ProcurementError("Already installed")
    return FLOW[i + 1]


def need_by(category: str, site_start: str, handover_start: str, buffer_days: int = 2) -> str:
    """Date an item must be on site: before site work, or before handover for furniture, soft furnishing and appliances."""
    base = _d(handover_start if category in LATE_STAGE else site_start)
    return (base - timedelta(days=buffer_days)).isoformat()


def order_by(need: str, category: str, lead_days: Optional[int] = None, today: Optional[date] = None) -> str:
    """need-by minus the lead time, never earlier than today."""
    lead = LEAD_DAYS.get(category, 14) if lead_days is None else lead_days
    d = _d(need) - timedelta(days=lead)
    return max(d, today or date.today()).isoformat()


def item_state(item: dict, today: Optional[date] = None) -> dict:
    """{"late_order", "late_delivery", "days"}: not ordered by its order-by date, or delivery overdue."""
    now = today or date.today()
    out = {"late_order": False, "late_delivery": False, "days": 0}
    if item["status"] == "to_order":
        ob = _d(item.get("order_by"))
        if ob and ob < now:
            out.update(late_order=True, days=(now - ob).days)
    elif item["status"] in ("ordered", "in_production", "dispatched"):
        ed = _d(item.get("expected_delivery"))
        if ed and ed < now:
            out.update(late_delivery=True, days=(now - ed).days)
    return out


def po_amounts(po: dict) -> dict:
    """PO: {"items": [{"rate" (excl. GST), "qty", "gst_pct"?}], "advance_pct"?, "payments"?: [{"amount"}]}"""
    taxable = round(sum((i.get("rate") or 0) * i["qty"] for i in po["items"]), 2)
    gst = round(sum((i.get("rate") or 0) * i["qty"] * (i.get("gst_pct") or DEFAULT_GST) / 100 for i in po["items"]), 2)
    total = round(taxable + gst)
    adv = round(total * (po.get("advance_pct") or 0) / 100)
    paid = sum(x["amount"] for x in po.get("payments", []))
    return {"taxable": taxable, "gst": gst, "total": total, "advance": adv, "balance": total - adv, "paid": paid, "due": total - paid}


def check_po_ready(po: dict) -> None:
    """A PO can be sent only when every item has a rate."""
    missing = [i.get("name", "?") for i in po["items"] if not i.get("rate")]
    if missing:
        raise ProcurementError("Fill the rate for: " + ", ".join(missing[:5]))


def next_actions(items: List[dict], today: Optional[date] = None, soon_days: int = 3) -> List[dict]:
    """What to do next, most urgent first: late orders, late deliveries, orders due soon, deliveries due soon."""
    now = today or date.today()
    out = []
    for it in items:
        st = item_state(it, now)
        if st["late_order"]:
            out.append({"item": it["id"], "action": "Order now", "late_days": st["days"], "rank": 0})
        elif st["late_delivery"]:
            out.append({"item": it["id"], "action": "Chase the vendor", "late_days": st["days"], "rank": 1})
        elif it["status"] == "to_order" and it.get("order_by") and _d(it["order_by"]) <= now + timedelta(days=soon_days):
            out.append({"item": it["id"], "action": "Order soon", "late_days": 0, "rank": 2})
        elif it["status"] in ("ordered", "in_production", "dispatched") and it.get("expected_delivery") \
                and _d(it["expected_delivery"]) <= now + timedelta(days=soon_days):
            out.append({"item": it["id"], "action": "Delivery due", "late_days": 0, "rank": 3})
    return sorted(out, key=lambda a: (a["rank"], -a["late_days"]))


def compare_quotes(quotes: List[dict], need: Optional[str] = None, today: Optional[date] = None) -> Dict[str, dict]:
    """quotes: [{"vendor", "item", "rate" (excl. GST), "gst_pct"?, "lead_days"}].
    For each item, the cheapest quote (incl. GST) that can arrive by `need`; others listed with the reason they lost."""
    now = today or date.today()
    by_item: Dict[str, list] = {}
    for q in quotes:
        by_item.setdefault(q["item"], []).append(q)
    out = {}
    for item, qs in by_item.items():
        rows = []
        for q in qs:
            gross = round(q["rate"] * (1 + (q.get("gst_pct") or DEFAULT_GST) / 100), 2)
            arrives = now + timedelta(days=q.get("lead_days") or 0)
            ok = need is None or arrives <= _d(need)
            rows.append({**q, "rate_incl_gst": gross, "arrives": arrives.isoformat(), "in_time": ok})
        good = sorted([r for r in rows if r["in_time"]], key=lambda r: (r["rate_incl_gst"], r.get("lead_days") or 0))
        out[item] = {"best": good[0] if good else None,
                     "others": [r for r in rows if not good or r is not good[0]],
                     "note": None if good else "No quote arrives in time"}
    return out
