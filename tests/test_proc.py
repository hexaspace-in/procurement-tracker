from datetime import date

import pytest

from procurement_tracker import (ProcurementError, check_po_ready, compare_quotes, item_state, need_by, next_actions,
                                 next_status, order_by, po_amounts)

T = date(2026, 12, 10)


def test_dates():
    assert need_by("carpentry", "2027-01-10", "2027-02-10") == "2027-01-08"
    assert need_by("furniture", "2027-01-10", "2027-02-10") == "2027-02-08"
    assert order_by("2027-01-08", "carpentry", today=T) == "2026-12-18"
    assert order_by("2026-12-15", "furniture", today=T) == "2026-12-10"     # never before today


def test_flow_and_state():
    assert next_status("ordered") == "in_production"
    with pytest.raises(ProcurementError):
        next_status("installed")
    assert item_state({"status": "to_order", "order_by": "2026-12-05"}, T) == {"late_order": True, "late_delivery": False, "days": 5}
    assert item_state({"status": "dispatched", "expected_delivery": "2026-12-08"}, T)["late_delivery"]


def test_po():
    po = {"items": [{"name": "Ply", "rate": 1000, "qty": 10}, {"name": "Hinges", "rate": 200, "qty": 5, "gst_pct": 12}],
          "advance_pct": 50, "payments": [{"amount": 5000}]}
    a = po_amounts(po)
    assert (a["taxable"], a["gst"], a["total"], a["advance"], a["due"]) == (11000, 1920, 12920, 6460, 7920)
    with pytest.raises(ProcurementError):
        check_po_ready({"items": [{"name": "Glass", "qty": 1}]})


def test_next_actions():
    items = [{"id": "a", "status": "to_order", "order_by": "2026-12-01"},
             {"id": "b", "status": "ordered", "expected_delivery": "2026-12-12"},
             {"id": "c", "status": "to_order", "order_by": "2026-12-08"}]
    acts = next_actions(items, T)
    assert [x["item"] for x in acts] == ["a", "c", "b"]


def test_compare_quotes():
    q = [{"vendor": "V1", "item": "Laminate", "rate": 100, "lead_days": 20},
         {"vendor": "V2", "item": "Laminate", "rate": 110, "lead_days": 5},
         {"vendor": "V3", "item": "Laminate", "rate": 120, "lead_days": 3}]
    r = compare_quotes(q, need="2026-12-20", today=T)["Laminate"]
    assert r["best"]["vendor"] == "V2" and len(r["others"]) == 2
