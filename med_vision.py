import json
import os
import re
import time

from google import genai
from google.genai import errors as genai_errors
from PIL import Image

import config


def get_api_key():
    key = config.GEMINI_API_KEY
    if not key or key == "YOUR_GEMINI_API_KEY_HERE":
        return None
    return key


def _load_image(image_input):
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"Image not found: {image_input}")
        with Image.open(image_input) as img:
            return img.copy()
    return image_input.copy() if hasattr(image_input, "copy") else image_input


def _clean_json_text(text):
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return text


def _normalize_result(data):
    items = data.get("items", [])
    processed = []
    errors_fixed = 0

    for item in items:
        try:
            qty = float(item.get("qty", 0))
            rate = float(item.get("rate", 0))
            amount = float(item.get("row_total", 0))

            status = "OK"
            if abs(qty * rate - amount) > 1 and rate > 0:
                correct = round(amount / rate)
                if abs(correct * rate - amount) < 1:
                    qty = correct
                    errors_fixed += 1
                    status = "FIXED"

            batch = str(item.get("batch", "")).strip()
            expiry = str(item.get("expiry", "")).strip()

            if batch and not expiry:
                expiry = "31-DEC-2099"
                print(f"[Fallback] Batch '{batch}' has no expiry, using default 31-DEC-2099")
            elif not batch and not expiry:
                batch = "NOBATCH"
                expiry = "31-DEC-2099"
            elif not batch and expiry:
                batch = "NOBATCH"

            processed.append({
                "item_name": str(item.get("item_name", "")).strip(),
                "variant_size": str(item.get("variant_size", "")).strip(),
                "batch": batch,
                "expiry": expiry,
                "qty": qty,
                "rate": rate,
                "row_total": qty * rate,
                "tax_percent": float(item.get("tax_percent", 5)),
                "validation_status": status,
            })
        except Exception:
            continue

    total = sum(i["row_total"] for i in processed)
    print(f"[AI] Success: {len(processed)} items, Rs {total:,.2f}, {errors_fixed} fixed")

    return {
        "header": data.get("header", {}),
        "items": processed,
        "validation": {"total_items": len(processed), "errors_fixed": errors_fixed, "extracted_total": total},
    }


def analyze_invoice_image(image_input):
    api_key = get_api_key()
    if not api_key:
        return {"error": "Set GEMINI_API_KEY in config.py"}

    prompt = """You are a medical invoice data entry expert. Extract ALL fields strictly as JSON.

Extract every line item from the invoice image. Every item MUST have a batch number and expiry date.

CRITICAL RULES:
- "date" = the INVOICE DATE only (not order date, not delivery date). Format DD-MM-YYYY.
- "batch" = Batch No / Lot No / B.No / Batch/Lot. If found on the bill, extract it. If truly missing, put "NOBATCH".
- "expiry" = Expiry Date / Exp.Date / Use By / Best Before. Format DD-MMM-YYYY (e.g. 31-DEC-2026). If truly missing, put "31-DEC-2099".
- "item_name" = full product description, do NOT shorten.
- "variant_size" = size/dimensions if separate column, else "".
- "qty" = quantity (number only, do not confuse with tax%).
- "rate" = unit rate (price of 1 unit).
- "row_total" = qty * rate.
- "tax_percent" = GST/Sales Tax rate (5, 12, 18, etc.). If not visible, put 12.
- Return ONLY valid JSON, no extra text.

Output JSON:
{
  "header": {"supplier": "SUPPLIER NAME", "inv_no": "INVOICE NUMBER", "date": "DD-MM-YYYY"},
  "items": [
    {
      "item_name": "FULL PRODUCT NAME",
      "variant_size": "SIZE",
      "batch": "BATCH123",
      "expiry": "DD-MMM-YYYY",
      "qty": 10,
      "rate": 100.0,
      "row_total": 1000.0,
      "tax_percent": 12
    }
  ]
}
"""

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-001",
    ]

    max_retries = 3
    last_error = ""

    try:
        img = _load_image(image_input)

        if img.height > 1500:
            ratio = 1500 / img.height
            img = img.resize((int(img.width * ratio), 1500), Image.Resampling.LANCZOS)
            print("[AI] Resized image to save tokens")

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        client = genai.Client(api_key=api_key)

        for model_name in models_to_try:
            for attempt in range(max_retries):
                try:
                    print(f"[AI] Trying {model_name} (attempt {attempt + 1})...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[prompt, img],
                    )
                    text = _clean_json_text(response.text)
                    data = json.loads(text)

                    if "items" not in data:
                        return {"error": f"Gemini ({model_name}) response did not include invoice items"}

                    return _normalize_result(data)

                except genai_errors.APIError as e:
                    code = e.code
                    last_error = f"{model_name} (HTTP {code}): {e.message}"
                    print(f"[Model {model_name}] Failed (code {code}): {e.message}")

                    if code == 429:
                        match = re.search(r"retry in (\d+)", str(e).lower())
                        wait = int(match.group(1)) + 2 if match else 60
                        print(f"[Quota] Quota hit on {model_name}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue

                    if code == 503:
                        wait = min(10 * (attempt + 1), 30)
                        print(f"[Overload] {model_name} busy, retrying in {wait}s...")
                        time.sleep(wait)
                        continue

                    if code in (400, 404):
                        print(f"[Skip] {model_name} not available (code {code}), trying next model...")
                        break

                    print(f"[Fail] {model_name} unrecoverable error (code {code})")
                    time.sleep(2)
                    break

                except Exception as e:
                    last_error = f"{model_name}: {str(e)[:200]}"
                    print(f"[Error] {model_name}: {last_error}")
                    break

        return {"error": f"All models failed. Last: {last_error}"}

    except Exception as e:
        return {"error": f"System Error: {str(e)}"}
