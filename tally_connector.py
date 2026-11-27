import os
import requests
import sqlite3
import re
import time
import threading
from datetime import datetime

TALLY_URL = "http://localhost:9000"
DB_FILE = "mappings.db"


class TallyManager:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_FILE)
        conn.cursor().execute(
            "CREATE TABLE IF NOT EXISTS item_map "
            "(bill_name TEXT PRIMARY KEY, tally_name TEXT)"
        )
        conn.commit()
        conn.close()

    def get_mapped_name(self, bill_item_name):
        conn = sqlite3.connect(DB_FILE)
        res = conn.cursor().execute(
            "SELECT tally_name FROM item_map WHERE bill_name=?",
            (bill_item_name,),
        ).fetchone()
        conn.close()
        return res[0] if res else None

    def save_new_mapping(self, bill_name, tally_name):
        if bill_name == tally_name:
            return
        conn = sqlite3.connect(DB_FILE)
        conn.cursor().execute(
            "INSERT OR REPLACE INTO item_map VALUES (?, ?)", (bill_name, tally_name)
        )
        conn.commit()
        conn.close()

    def clean_text(self, text):
        if not text:
            return ""
        text = str(text).strip()
        text = text.replace("&", "and").replace("'", "").replace('"', "")
        text = text.replace("<", "").replace(">", "")
        text = re.sub(r"[^a-zA-Z0-9\s\-\.\/\(\)]", "", text)
        if len(text) > 50:
            text = text[:47] + "..."
        return text.strip()

    def _get_item_name(self, item):
        raw = self.get_mapped_name(item["item_name"]) or item["item_name"]
        return self.clean_text(raw)

    def _format_date(self, d):
        if not d:
            return "20261231"
        
        d = str(d).strip().upper()
        d = d.replace("/", "-").replace(".", "-").replace(" ", "-")
        d = "-".join([s for s in d.split("-") if s])
        
        month_map = {
            'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
            'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
            'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
        }
        
        parts = [p for p in d.split("-") if p]
        
        if len(parts) >= 2:
            day = parts[0] if parts[0].isdigit() else "01"
            month = parts[1]
            year = parts[2] if len(parts) > 2 else "2026"
            
            if month in month_map:
                month = month_map[month]
            
            if len(year) == 2:
                year = "20" + year
            
            try:
                day = day.zfill(2)
                month = month.zfill(2)
                datetime(int(year), int(month), int(day))
                return f"{year}{month}{day}"
            except:
                pass
        
        return "20261231"

    def _validate_invoice_data(self, invoice_data):
        if not invoice_data.get("header"):
            return False, "Missing invoice header"
        
        header = invoice_data["header"]
        if not header.get("supplier"):
            return False, "Missing supplier name"
        if not header.get("inv_no"):
            return False, "Missing invoice number"
        
        items = invoice_data.get("items", [])
        if not items:
            return False, "No line items to process"
        
        warnings = []
        for idx, item in enumerate(items, 1):
            batch = str(item.get("batch", "")).strip()
            if not batch or len(batch) < 2:
                warnings.append(f"Row {idx}: Missing batch number — will use 'NOBATCH'")
            
            expiry = str(item.get("expiry", "")).strip()
            if not expiry:
                warnings.append(f"Row {idx}: Missing expiry date")
        
        return True, warnings

    def xml_create_stock_group(self):
        return (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA>"
            "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA>"
            '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
            '<STOCKGROUP NAME="Medical Devices" ACTION="Create">'
            "<NAME>Medical Devices</NAME>"
            "<PARENT>Stock Items</PARENT>"
            "</STOCKGROUP></TALLYMESSAGE>"
            "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        )

    def _get_tax_rates(self, invoice_data):
        rates = set()
        for item in invoice_data.get("items", []):
            try:
                rate = float(item.get("tax_percent", 12))
            except (ValueError, TypeError):
                rate = 12.0
            rates.add(rate)
        return sorted(rates)

    def _ledger_name_for_tax(self, tax_rate):
        if tax_rate == int(tax_rate):
            return f"Purchase @ {int(tax_rate)}"
        return f"Purchase @ {tax_rate}"

    def xml_wave_1(self, invoice_data):
        supplier = self.clean_text(invoice_data["header"]["supplier"])
        tax_rates = self._get_tax_rates(invoice_data)

        xml = (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA>"
            "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA>"
            '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
            '<UNIT NAME="Nos" ACTION="Create">'
            "<NAME>Nos</NAME>"
            "<ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>"
            "</UNIT></TALLYMESSAGE>"
            f'<TALLYMESSAGE xmlns:UDF="TallyUDF">'
            f'<LEDGER NAME="{supplier}" ACTION="Create">'
            f"<NAME>{supplier}</NAME>"
            f"<PARENT>Sundry Creditors</PARENT>"
            f"<ISBILLWISEON>Yes</ISBILLWISEON>"
            f"</LEDGER></TALLYMESSAGE>"
        )

        for rate in tax_rates:
            ledger_name = self._ledger_name_for_tax(rate)
            xml += (
                f'<TALLYMESSAGE xmlns:UDF="TallyUDF">'
                f'<LEDGER NAME="{ledger_name}" ACTION="Create">'
                f"<NAME>{ledger_name}</NAME>"
                f"<PARENT>Purchase Accounts</PARENT>"
                f"</LEDGER></TALLYMESSAGE>"
            )

        xml += "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        return xml

    def _stock_item_block(self, item_name, action):
        cleaned_name = self.clean_text(item_name)
        return (
            f'<TALLYMESSAGE xmlns:UDF="TallyUDF">'
            f'<STOCKITEM NAME="{cleaned_name}" ACTION="{action}">'
            f"<NAME>{cleaned_name}</NAME>"
            f"<BASEUNITS>Nos</BASEUNITS>"
            f"<PARENT>Medical Devices</PARENT>"
            f"<MAINTAINBATCHES>Yes</MAINTAINBATCHES>"
            f"<ISBATCHON>Yes</ISBATCHON>"
            f"<USEEXPIRYDATES>Yes</USEEXPIRYDATES>"
            f"<USEEXPIRYDATE>Yes</USEEXPIRYDATE>"
            f"<TRACKMANUFACTUREDDATE>No</TRACKMANUFACTUREDDATE>"
            f"</STOCKITEM></TALLYMESSAGE>"
        )

    def _build_wave2_xml(self, item_names, action):
        xml = (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA>"
            "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA>"
        )
        for name in item_names:
            xml += self._stock_item_block(name, action)
        xml += "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        return xml

    def _save_xml_backup(self, wave_name, xml_data):
        backup_dir = "Backup_tallypush"
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(backup_dir, f"{wave_name}_{ts}.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml_data)
        print(f"[Backup] Saved: {path}")

    def _build_batch_masters_xml(self, invoice_data):
        xml = (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA>"
            "<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA>"
        )
        for item in invoice_data["items"]:
            final_name = self._get_item_name(item)
            safe_batch = self.clean_text(item.get("batch", ""))
            if not safe_batch:
                safe_batch = "NOBATCH"
            expiry_tally = self._format_date(item.get("expiry", ""))
            xml += (
                f'<TALLYMESSAGE xmlns:UDF="TallyUDF">'
                f'<STOCKITEM NAME="{final_name}" ACTION="Alter">'
                f"<NAME>{final_name}</NAME>"
                "<ISBATCHON>Yes</ISBATCHON>"
                "<USEEXPIRYDATES>Yes</USEEXPIRYDATES>"
                "<BATCHALLOCATIONS.LIST>"
                "<GODOWNNAME>Main Location</GODOWNNAME>"
                f"<BATCHNAME>{safe_batch}</BATCHNAME>"
                f"<EXPDATE>{expiry_tally}</EXPDATE>"
                "</BATCHALLOCATIONS.LIST>"
                f"</STOCKITEM></TALLYMESSAGE>"
            )
        xml += "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        return xml

    def _send_to_tally(self, xml_data, timeout=15):
        """Send XML to Tally with proper error handling"""
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        try:
            response = requests.post(
                TALLY_URL,
                data=xml_data.encode("utf-8"),
                headers=headers,
                timeout=timeout
            )
            return response.status_code, response.text
        except requests.exceptions.Timeout:
            return -1, "Tally did not respond within timeout"
        except requests.exceptions.ConnectionError:
            return -2, "Cannot connect to Tally. Ensure Tally is running on port 9000"
        except Exception as e:
            return -3, str(e)

    def _check_tally_response(self, response_text):
        """Check if Tally response indicates success"""
        if "<CREATED>1</CREATED>" in response_text:
            return True, "Created"
        if "<ALTERED>1</ALTERED>" in response_text:
            return True, "Altered"
        
        # Check for errors
        errors = re.findall(r'<LINEERROR>(.*?)</LINEERROR>', response_text)
        if errors:
            return False, f"Tally error: {'; '.join(errors[:3])}"
        
        # Check for specific error patterns
        if "Stock Group" in response_text and "does not exist" in response_text:
            return False, "Stock group missing"
        
        return False, f"Unknown response: {response_text[:200]}"

    def xml_wave_3(self, invoice_data):
        supplier = self.clean_text(invoice_data["header"]["supplier"])
        inv_no = self.clean_text(invoice_data["header"]["inv_no"])
        date_str = self._format_date(invoice_data["header"]["date"])
        
        grand_total = 0.0

        xml = (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA>"
            "<REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA>"
            '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
            '<VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">'
            f"<DATE>{date_str}</DATE>"
            f"<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>"
            f"<REFERENCE>{inv_no}</REFERENCE>"
            f"<PARTYLEDGERNAME>{supplier}</PARTYLEDGERNAME>"
            f"<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>"
            f"<ISINVOICE>Yes</ISINVOICE>"
        )

        for item in invoice_data["items"]:
            final_name = self._get_item_name(item)
            safe_batch = self.clean_text(item.get("batch", ""))
            if not safe_batch:
                safe_batch = "NOBATCH"
            
            expiry_raw = item.get("expiry", "")
            expiry_tally = self._format_date(expiry_raw)

            try:
                qty = float(item.get("qty", 0))
            except:
                qty = 0.0
            try:
                rate = float(item.get("rate", 0))
            except:
                rate = 0.0

            try:
                tax_percent = float(item.get("tax_percent", 12))
            except:
                tax_percent = 12.0
            tax_ledger = self._ledger_name_for_tax(tax_percent)

            amount = rate * qty
            grand_total += amount

            # Batch allocation with expiry
            xml += (
                "<ALLINVENTORYENTRIES.LIST>"
                f"<STOCKITEMNAME>{final_name}</STOCKITEMNAME>"
                "<ISBATCHON>Yes</ISBATCHON>"
                "<USEEXPIRYDATES>Yes</USEEXPIRYDATES>"
                "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
                f"<RATE>{rate:.2f}/Nos</RATE>"
                f"<AMOUNT>-{amount:.2f}</AMOUNT>"
                f"<ACTUALQTY>{qty} Nos</ACTUALQTY>"
                f"<BILLEDQTY>{qty} Nos</BILLEDQTY>"

                "<BATCHALLOCATIONS.LIST>"
                "<GODOWNNAME>Main Location</GODOWNNAME>"
                f"<BATCHNAME>{safe_batch}</BATCHNAME>"
                f"<EXPDATE>{expiry_tally}</EXPDATE>"
                f"<AMOUNT>-{amount:.2f}</AMOUNT>"
                f"<ACTUALQTY>{qty} Nos</ACTUALQTY>"
                f"<BILLEDQTY>{qty} Nos</BILLEDQTY>"
                "</BATCHALLOCATIONS.LIST>"

                "<ACCOUNTINGALLOCATIONS.LIST>"
                f"<LEDGERNAME>{tax_ledger}</LEDGERNAME>"
                "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>-{amount:.2f}</AMOUNT>"
                "</ACCOUNTINGALLOCATIONS.LIST>"
                "</ALLINVENTORYENTRIES.LIST>"
            )

        xml += (
            "<LEDGERENTRIES.LIST>"
            f"<LEDGERNAME>{supplier}</LEDGERNAME>"
            "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
            f"<AMOUNT>{grand_total:.2f}</AMOUNT>"
            "</LEDGERENTRIES.LIST>"
            "</VOUCHER>"
            "</TALLYMESSAGE>"
            "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        )
        return xml

    def push_to_tally(self, invoice_data, progress_callback=None):
        """
        Push invoice to Tally with full error handling.
        Returns dict with status and message.
        """
        # Step 1: Validation
        is_valid, result = self._validate_invoice_data(invoice_data)
        if not is_valid:
            return {"status": "error", "msg": result}

        warnings = result

        item_names = list({
            self._get_item_name(item)
            for item in invoice_data["items"]
            if self._get_item_name(item)
        })
        expected = len(item_names)

        if expected == 0:
            return {"status": "error", "msg": "No valid items to process"}

        try:
            # Step 2: Create Stock Group
            if progress_callback:
                progress_callback("Creating stock group...", 10)
            
            xml0 = self.xml_create_stock_group()
            self._save_xml_backup("Wave0_StockGroup", xml0)
            status, response = self._send_to_tally(xml0, timeout=10)
            
            if status < 0:
                return {"status": "error", "msg": f"Wave 0 failed: {response}"}
            
            time.sleep(0.5)

            # Step 3: Create Ledgers
            if progress_callback:
                progress_callback("Creating supplier ledgers...", 20)
            
            xml1 = self.xml_wave_1(invoice_data)
            self._save_xml_backup("Wave1_Ledgers", xml1)
            status, response = self._send_to_tally(xml1, timeout=10)
            
            if status < 0:
                return {"status": "error", "msg": f"Wave 1 failed: {response}"}
            
            success, msg = self._check_tally_response(response)
            if not success and "already exists" not in response.lower():
                print(f"[Wave 1 Warning] {msg}")
            
            time.sleep(1)

            # Step 4: Create Stock Items
            if progress_callback:
                progress_callback(f"Creating {expected} stock items...", 40)
            
            xml2a = self._build_wave2_xml(item_names, "Create")
            self._save_xml_backup("Wave2a_CreateItems", xml2a)
            status, response = self._send_to_tally(xml2a, timeout=20)
            
            if status < 0:
                return {"status": "error", "msg": f"Wave 2a failed: {response}"}
            
            time.sleep(2)

            # Step 5: Update Stock Items (ensure flags)
            if progress_callback:
                progress_callback("Updating stock item settings...", 60)
            
            xml2b = self._build_wave2_xml(item_names, "Alter")
            self._save_xml_backup("Wave2b_AlterItems", xml2b)
            status, response = self._send_to_tally(xml2b, timeout=20)
            
            if status < 0:
                return {"status": "error", "msg": f"Wave 2b failed: {response}"}
            
            success, msg = self._check_tally_response(response)
            print(f"[Wave 2b] {msg}")
            
            time.sleep(2)

            # Step 5c: Create batch masters with expiry dates before voucher
            if progress_callback:
                progress_callback("Creating batch masters with expiry...", 70)

            xml2c = self._build_batch_masters_xml(invoice_data)
            self._save_xml_backup("Wave2c_BatchMasters", xml2c)
            status, response = self._send_to_tally(xml2c, timeout=20)

            if status < 0:
                print(f"[Wave 2c Warning] Batch master creation failed: {response}")
            else:
                print(f"[Wave 2c] Batch masters sent")

            time.sleep(1)

            # Step 6: Create Voucher
            if progress_callback:
                progress_callback("Creating purchase voucher...", 80)
            
            xml3 = self.xml_wave_3(invoice_data)
            self._save_xml_backup("Wave3_Voucher", xml3)
            status, response = self._send_to_tally(xml3, timeout=30)
            
            if status < 0:
                return {"status": "error", "msg": f"Wave 3 failed: {response}"}
            
            success, msg = self._check_tally_response(response)
            
            if progress_callback:
                progress_callback("Complete!", 100)

            if success:
                for item in invoice_data["items"]:
                    bill_name = item["item_name"]
                    tally_name = self._get_item_name(item)
                    self.save_new_mapping(bill_name, tally_name)

                msg_parts = [f"✅ Posted to Tally: {expected} items with batch/expiry tracking."]
                if warnings:
                    msg_parts.append(f"\n\n⚠️ {len(warnings)} warning(s):")
                    msg_parts.extend(f"\n- {w}" for w in warnings[:5])
                msg_parts.append("\n\nCheck Backup_tallypush/ folder for XML copies of each wave.")

                return {"status": "success", "msg": "".join(msg_parts)}
            else:
                return {"status": "error", "msg": f"❌ Tally rejected voucher: {msg}\n\nResponse: {response[:500]}"}

        except Exception as e:
            return {"status": "error", "msg": f"System error: {str(e)}"}