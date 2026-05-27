from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
import random
from datetime import datetime

app = FastAPI(title="TinyUniquon Logic API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ============================================
# 1. VALIDATE & FILTER INVENTORY
# Bot gets raw inventory from Pluggy → sends here → gets filtered result
# ============================================
class InventoryItem(BaseModel):
    Gender: str
    Age: str
    Design: str
    Quantity: int

class InventoryRequest(BaseModel):
    gender: str
    age: str
    inventory: List[InventoryItem]

@app.post("/api/filter-inventory")
def filter_inventory(req: InventoryRequest):
    if req.gender not in ("Boys", "Girls"):
        raise HTTPException(400, "gender must be 'Boys' or 'Girls'")
    if req.age not in ("2-4 years", "4-6 years"):
        raise HTTPException(400, "age must be '2-4 years' or '4-6 years'")

    available = [
        {"design": item.Design, "quantity": item.Quantity}
        for item in req.inventory
        if item.Gender == req.gender and item.Age == req.age and item.Quantity > 0
    ]

    return {
        "gender": req.gender,
        "age": req.age,
        "available": available,
        "totalDesigns": len(available),
    }


# ============================================
# 2. VALIDATE ORDER & GENERATE ORDER NUMBER
# Bot collects all info → sends here → gets validated order ready for Pluggy to write
# ============================================
class OrderRequest(BaseModel):
    customerName: str = Field(..., min_length=2)
    phone: str
    design: str
    quantity: int
    availableStock: int
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2)
    pincode: str

@app.post("/api/validate-order")
def validate_order(order: OrderRequest):
    errors = []

    # Phone validation
    if len(order.phone) != 10 or not order.phone.isdigit() or order.phone[0] not in "6789":
        errors.append("Invalid phone number. Must be 10 digits starting with 6/7/8/9.")

    # Pincode validation
    if len(order.pincode) != 6 or not order.pincode.isdigit() or order.pincode[0] == "0":
        errors.append("Invalid pincode. Must be 6 digits.")

    # Quantity validation
    if order.quantity <= 0 or order.quantity > 10:
        errors.append("Quantity must be between 1 and 10.")

    if order.quantity > order.availableStock:
        errors.append(f"Only {order.availableStock} in stock. Reduce quantity.")

    if errors:
        return {"valid": False, "errors": errors}

    # All good — generate order
    price = order.quantity * 500
    order_number = f"TU{random.randint(10000, 99999)}"
    order_date = datetime.now().strftime("%Y-%m-%d")

    new_stock = order.availableStock - order.quantity

    return {
        "valid": True,
        "orderNumber": order_number,
        "orderDate": order_date,
        "price": price,
        "newStock": new_stock,
        "shippingData": {
            "Order number": order_number,
            "Order date": order_date,
            "Name": order.customerName,
            "Phone number": order.phone,
            "Quantity": order.quantity,
            "Price": price,
            "Address": order.address,
            "City": order.city,
            "Pincode": order.pincode,
        },
        "orderDetailData": {
            "Customer Name": order.phone,
            "Order Id": order_number,
            "Order Date": order_date,
            "Order Status": "Open",
        },
    }


# ============================================
# 3. COMPUTE ORDER STATUS
# Bot gets raw order rows from Pluggy → sends here → gets computed status
# Priority: Open > Partially processed > Completed
# ============================================
class OrderRow(BaseModel):
    OrderStatus: str

class TrackRequest(BaseModel):
    orderId: str
    rows: List[OrderRow]

@app.post("/api/compute-status")
def compute_status(req: TrackRequest):
    if not req.rows:
        return {"orderId": req.orderId, "overallStatus": "not_found"}

    statuses = [r.OrderStatus.strip() for r in req.rows]

    if "Open" in statuses:
        overall = "Open"
    elif "Partially processed" in statuses:
        overall = "Partially processed"
    elif all(s == "Completed" for s in statuses):
        overall = "Completed"
    else:
        overall = "Open"

    return {
        "orderId": req.orderId,
        "totalItems": len(statuses),
        "breakdown": {
            "open": statuses.count("Open"),
            "partiallyProcessed": statuses.count("Partially processed"),
            "completed": statuses.count("Completed"),
        },
        "overallStatus": overall,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
