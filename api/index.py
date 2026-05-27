from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
import gspread
from google.oauth2.service_account import Credentials
import json
import os
import random
from datetime import datetime

app = FastAPI(title="TinyUniquon Logic API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SPREADSHEET_ID = "1ZizjWpqeX42mKarIIzM2JkqHqjQxbNV1nhdRNYxzeRQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheet_client():
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


@app.post("/api/validate-order")
def validate_order(order: dict):
    customerName = order.get("customerName", "")
    phone = order.get("phone", "")
    design = order.get("design", "")
    quantity = int(order.get("quantity", 0))
    availableStock = int(order.get("availableStock", 0))
    address = order.get("address", "")
    city = order.get("city", "")
    pincode = order.get("pincode", "")

    errors = []

    if len(customerName) < 2:
        errors.append("Name too short.")
    if len(phone) != 10 or not phone.isdigit() or phone[0] not in "6789":
        errors.append("Invalid phone number. Must be 10 digits starting with 6/7/8/9.")
    if len(pincode) != 6 or not pincode.isdigit() or pincode[0] == "0":
        errors.append("Invalid pincode. Must be 6 digits.")
    if quantity <= 0 or quantity > 10:
        errors.append("Quantity must be between 1 and 10.")
    if quantity > availableStock:
        errors.append(f"Only {availableStock} in stock. Reduce quantity.")
    if len(address) < 5:
        errors.append("Address too short.")
    if len(city) < 2:
        errors.append("City too short.")

    if errors:
        return {"valid": False, "errors": errors}

    price = quantity * 500
    order_number = f"TU{random.randint(10000, 99999)}"
    order_date = datetime.now().strftime("%Y-%m-%d")
    new_stock = availableStock - quantity

    try:
        spreadsheet = get_sheet_client()

        # Write to Shipping details
        ship_sheet = spreadsheet.worksheet("Shipping details")
        ship_sheet.append_row([
            order_number, order_date, customerName, phone,
            quantity, price, address, city, pincode
        ])

        # Write to Order detail
        detail_sheet = spreadsheet.worksheet("Order detail")
        detail_sheet.append_row([phone, order_number, order_date, "Open"])

        # Update inventory
        inv_sheet = spreadsheet.worksheet("Inventory")
        inv_rows = inv_sheet.get_all_records()
        for i, r in enumerate(inv_rows):
            if r["Design"] == design:
                inv_sheet.update_cell(i + 2, 4, new_stock)
                break

    except Exception as e:
        return {"valid": True, "orderNumber": order_number, "orderDate": order_date, "price": price, "newStock": new_stock, "sheetError": str(e)}

    return {
        "valid": True,
        "orderNumber": order_number,
        "orderDate": order_date,
        "price": price,
        "newStock": new_stock,
        "sheetUpdated": True,
    }


@app.post("/api/compute-status")
def compute_status(req: dict):
    orderId = req.get("orderId", "")
    phone = req.get("phone", "")

    try:
        spreadsheet = get_sheet_client()
        sheet = spreadsheet.worksheet("Order detail")
        rows = sheet.get_all_records()

        matching = [
            r for r in rows
            if str(r.get("Order Id", "")).strip() == str(orderId).strip()
            and str(r.get("Customer Name", "")).strip() == str(phone).strip()
        ]

        if not matching:
            return {"orderId": orderId, "overallStatus": "not_found"}

        statuses = [r.get("Order Status", "").strip() for r in matching]

        if "Open" in statuses:
            overall = "Open"
        elif "Partially processed" in statuses:
            overall = "Partially processed"
        elif all(s == "Completed" for s in statuses):
            overall = "Completed"
        else:
            overall = "Open"

        return {
            "orderId": orderId,
            "totalItems": len(statuses),
            "breakdown": {
                "open": statuses.count("Open"),
                "partiallyProcessed": statuses.count("Partially processed"),
                "completed": statuses.count("Completed"),
            },
            "overallStatus": overall,
        }

    except Exception as e:
        return {"orderId": orderId, "overallStatus": "error", "error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}
