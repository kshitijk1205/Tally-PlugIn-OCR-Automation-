import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import fitz
from PIL import Image, ImageTk
import os
import queue
import io
import sys
import med_vision
import tally_connector


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

C_APP_BG = "#F4F5F7"
C_WHITE = "#FFFFFF"
C_BORDER = "#E2E8F0"
C_TEXT_MAIN = "#1F2937"
C_TEXT_LABEL = "#6B7280"
C_PRIMARY = "#4338CA"
C_SUCCESS = "#10B981"
C_DANGER = "#EF4444"
C_WARNING = "#F59E0B"


class DataRow(ctk.CTkFrame):
    def __init__(self, master, index, data=None, calculate_callback=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.index = index
        self.calculate_callback = calculate_callback
        data = data if data else {}
        
        self.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=1)

        # Determine row color based on validation status
        validation_status = data.get('validation_status', 'OK')
        if validation_status == 'ERROR':
            row_color = "#FFE4E4"  # Light red for errors
        elif validation_status == 'FIXED':
            row_color = "#FFF4E4"  # Light orange for fixed
        else:
            row_color = "transparent"
            
        self.configure(fg_color=row_color)

        self.ent_item = self._add_field(0, 150, data.get('item_name', ''))
        self.ent_size = self._add_field(1, 80, data.get('variant_size', ''))
        self.ent_batch = self._add_field(2, 80, data.get('batch', ''))
        self.ent_exp = self._add_field(3, 80, data.get('expiry', ''))
        
        # Highlight qty field if it was auto-corrected
        qty_color = C_WHITE if validation_status == 'OK' else "#FFD700"
        self.ent_qty = self._add_field(4, 40, str(data.get('qty', '')), bind=True, bg_color=qty_color)
        
        self.ent_rate = self._add_field(5, 60, str(data.get('rate', '')), bind=True)
        
        init_amt = data.get('row_total', 0)
        if init_amt == 0 and data.get('qty') and data.get('rate'):
            try:
                init_amt = float(data['qty']) * float(data['rate'])
            except:
                init_amt = 0
        
        self.ent_amt = ctk.CTkEntry(self, width=70, fg_color=C_APP_BG, text_color=C_TEXT_MAIN, border_width=0)
        self.ent_amt.grid(row=0, column=6, padx=2, pady=2, sticky="ew")
        self.ent_amt.insert(0, f"{init_amt:.2f}")

        self.ent_tax = self._add_field(7, 40, str(data.get('tax_percent', '12')))
        
        self.btn_del = ctk.CTkButton(
            self, 
            text="🗑", 
            width=30, 
            fg_color="transparent", 
            text_color=C_DANGER, 
            hover_color="#FEE2E2", 
            command=self.destroy_row
        )
        self.btn_del.grid(row=0, column=8, padx=2, pady=2)
        
        self.separator = ctk.CTkFrame(self, height=1, fg_color=C_BORDER)
        self.separator.grid(row=1, column=0, columnspan=9, sticky="ew", pady=(2, 0))

    def _add_field(self, col, w, val, bind=False, bg_color=None):
        color = bg_color if bg_color else C_WHITE
        ent = ctk.CTkEntry(
            self, 
            width=w, 
            fg_color=color, 
            text_color=C_TEXT_MAIN, 
            border_color=C_BORDER, 
            border_width=1, 
            corner_radius=4
        )
        ent.grid(row=0, column=col, padx=2, pady=2, sticky="ew")
        if val and str(val) not in ["0", "0.0", "None"]:
            ent.insert(0, str(val))
        if bind:
            ent.bind("<KeyRelease>", self.update_total)
        return ent

    def update_total(self, event=None):
        try:
            q = float(self.ent_qty.get() or 0)
            r = float(self.ent_rate.get() or 0)
            total = q * r
            self.ent_amt.delete(0, "end")
            self.ent_amt.insert(0, f"{total:.2f}")
            if self.calculate_callback:
                self.calculate_callback()
        except:
            pass

    def destroy_row(self):
        self.destroy()
        if self.calculate_callback:
            self.calculate_callback()

    def get_data(self):
        return {
            "item_name": self.ent_item.get(),
            "variant_size": self.ent_size.get(),
            "batch": self.ent_batch.get(),
            "expiry": self.ent_exp.get(),
            "qty": self.ent_qty.get(),
            "rate": self.ent_rate.get(),
            "row_total": self.ent_amt.get(),
            "tax_percent": self.ent_tax.get()
        }


class CardioFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Accountant | CardioFlow")
        self.geometry("1440x900")
        self.configure(fg_color=C_APP_BG)
        
        self.session_id = 0
        self.file_queue = queue.Queue()
        self.image_stack = []
        self.stitched_image = None
        self.zoom_level = 1.0
        self.safe_image_ref = None
        self.tally = tally_connector.TallyManager()
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_sidebar()
        self._build_main_area()
        
        try:
            import mobile_bridge
            self.mobile_url = mobile_bridge.start_server(self.file_queue)
        except ImportError:
            self.mobile_url = None
        
        self.check_queue()

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, 
            width=220, 
            corner_radius=0, 
            fg_color=C_WHITE, 
            border_width=1, 
            border_color=C_BORDER
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", pady=20, padx=20)
        ctk.CTkLabel(brand_frame, text="▲", font=("Arial", 24), text_color=C_PRIMARY).pack(side="left")
        ctk.CTkLabel(
            brand_frame, 
            text=" AI Accountant", 
            font=("Arial", 16, "bold"), 
            text_color=C_TEXT_MAIN
        ).pack(side="left", padx=10)

        self._nav_link("📄 Dashboard")
        self._nav_link("↗ Accounts Payable", active=True)
        self._nav_link("📁 Inventory Masters")
        
        ctk.CTkFrame(self.sidebar, height=1, fg_color=C_BORDER).pack(fill="x", padx=20, pady=20)
        
        self._action_btn("➕ Upload PDF/Image", self.action_new_bill, C_PRIMARY, C_WHITE, has_border=False)
        self._action_btn("📎 Add Extra Page", self.action_add_page, C_WHITE, C_TEXT_MAIN, has_border=True)
        self._action_btn("📱 Sync Phone Camera", self.show_qr, C_WHITE, C_TEXT_MAIN, has_border=True)

        self.lbl_status = ctk.CTkLabel(
            self.sidebar, 
            text="Status: Ready", 
            font=("Arial", 12), 
            text_color=C_TEXT_LABEL
        )
        self.lbl_status.pack(side="bottom", pady=20)

    def _build_main_area(self):
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        header = ctk.CTkFrame(self.main_area, fg_color="transparent", height=60)
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header, 
            text="📑 New Bill Entry", 
            font=("Arial", 20, "bold"), 
            text_color=C_TEXT_MAIN
        ).pack(side="left")

        self.btn_tally = ctk.CTkButton(
            header, 
            text="Save to Tally", 
            fg_color=C_PRIMARY, 
            text_color=C_WHITE, 
            corner_radius=6, 
            command=self.push_tally, 
            state="disabled",
            width=120
        )
        self.btn_tally.pack(side="right", padx=5)
        
        self.btn_scan = ctk.CTkButton(
            header, 
            text="✨ Auto-Fill with AI", 
            fg_color=C_SUCCESS, 
            text_color=C_WHITE, 
            corner_radius=6, 
            command=self.run_ai,
            width=140
        )
        self.btn_scan.pack(side="right", padx=5)
        
        self.btn_reset = ctk.CTkButton(
            header, 
            text="Discard", 
            fg_color=C_WHITE, 
            text_color=C_TEXT_MAIN, 
            border_color=C_BORDER, 
            border_width=1, 
            hover_color=C_APP_BG, 
            corner_radius=6, 
            command=self.reset_ui,
            width=80
        )
        self.btn_reset.pack(side="right", padx=5)

        content_split = ctk.CTkFrame(self.main_area, fg_color="transparent")
        content_split.pack(fill="both", expand=True)
        content_split.grid_columnconfigure(0, weight=35)
        content_split.grid_columnconfigure(1, weight=65)
        content_split.grid_rowconfigure(0, weight=1)

        doc_card = ctk.CTkFrame(
            content_split, 
            fg_color=C_WHITE, 
            corner_radius=8, 
            border_width=1, 
            border_color=C_BORDER
        )
        doc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        doc_header = ctk.CTkFrame(doc_card, fg_color="transparent", height=40)
        doc_header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(doc_header, text="Document Preview", text_color=C_TEXT_LABEL).pack(side="left")
        
        zoom_frame = ctk.CTkFrame(doc_header, fg_color="transparent")
        zoom_frame.pack(side="right")
        ctk.CTkButton(
            zoom_frame, 
            text="−", 
            width=30, 
            fg_color="transparent", 
            text_color=C_TEXT_MAIN, 
            command=self.zoom_out
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            zoom_frame, 
            text="+", 
            width=30, 
            fg_color="transparent", 
            text_color=C_TEXT_MAIN, 
            command=self.zoom_in
        ).pack(side="left", padx=2)

        ctk.CTkFrame(doc_card, height=1, fg_color=C_BORDER).pack(fill="x")
        
        self.lbl_preview = ctk.CTkLabel(
            doc_card, 
            text="Click Upload to Load Invoice\nor use sidebar buttons", 
            text_color=C_TEXT_LABEL,
            font=("Arial", 14)
        )
        self.lbl_preview.pack(expand=True, fill="both", padx=10, pady=10)
        self.lbl_preview.bind("<MouseWheel>", self.on_zoom)

        data_card = ctk.CTkFrame(
            content_split, 
            fg_color=C_WHITE, 
            corner_radius=8, 
            border_width=1, 
            border_color=C_BORDER
        )
        data_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(
            data_card, 
            text="Vendor Details", 
            font=("Arial", 16, "bold"), 
            text_color=C_TEXT_MAIN
        ).pack(anchor="w", padx=20, pady=(20, 10))

        info = ctk.CTkFrame(data_card, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color=C_BORDER)
        info.pack(fill="x", padx=20, pady=10)
        
        info.grid_columnconfigure(1, weight=3)
        info.grid_columnconfigure(3, weight=1)
        info.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(info, text="Supplier:", font=("Arial", 12, "bold"), text_color=C_TEXT_MAIN).grid(row=0, column=0, padx=(15, 5), pady=15, sticky="e")
        self.ent_supplier = ctk.CTkEntry(info, fg_color=C_WHITE, border_color=C_BORDER, text_color=C_TEXT_MAIN)
        self.ent_supplier.grid(row=0, column=1, sticky="ew", padx=(0, 15))

        ctk.CTkLabel(info, text="Inv #:", font=("Arial", 12, "bold"), text_color=C_TEXT_MAIN).grid(row=0, column=2, padx=(10, 5), sticky="e")
        self.ent_inv = ctk.CTkEntry(info, text_color=C_PRIMARY, fg_color=C_WHITE, border_color=C_BORDER, font=("Arial", 12, "bold"))
        self.ent_inv.grid(row=0, column=3, sticky="ew", padx=(0, 15))

        ctk.CTkLabel(info, text="Date:", font=("Arial", 12, "bold"), text_color=C_TEXT_MAIN).grid(row=0, column=4, padx=(10, 5), sticky="e")
        self.ent_date = ctk.CTkEntry(info, fg_color=C_WHITE, border_color=C_BORDER, text_color=C_TEXT_MAIN, placeholder_text="DD-MM-YYYY")
        self.ent_date.grid(row=0, column=5, sticky="ew", padx=(0, 15))

        ctk.CTkFrame(data_card, height=1, fg_color=C_BORDER).pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            data_card, 
            text="Line Items", 
            font=("Arial", 16, "bold"), 
            text_color=C_TEXT_MAIN
        ).pack(anchor="w", padx=20, pady=(0, 10))

        h_frame = ctk.CTkFrame(data_card, height=30, fg_color=C_APP_BG, corner_radius=4)
        h_frame.pack(fill="x", padx=20)
        
        headers = ["Description", "Variant", "Batch", "Expiry", "Qty", "Rate", "Total", "Tax", ""]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(h_frame, text=h, font=("Arial", 11, "bold"), text_color=C_TEXT_LABEL)
            lbl.pack(side="left", expand=True if i < 8 else False, padx=5)

        self.scroll = ctk.CTkScrollableFrame(data_card, fg_color="transparent", label_text="")
        self.scroll.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.frame_total = ctk.CTkFrame(data_card, fg_color=C_APP_BG, corner_radius=0, height=50)
        self.frame_total.pack(fill="x", side="bottom")
        
        self.lbl_total = ctk.CTkLabel(
            self.frame_total, 
            text="Net Amount: ₹ 0.00", 
            font=("Arial", 16, "bold"), 
            text_color=C_TEXT_MAIN
        )
        self.lbl_total.pack(side="right", padx=20, pady=15)

    def _nav_link(self, text, active=False):
        color = C_APP_BG if active else "transparent"
        text_col = C_PRIMARY if active else C_TEXT_LABEL
        btn = ctk.CTkButton(
            self.sidebar, 
            text=text, 
            fg_color=color, 
            text_color=text_col, 
            font=("Arial", 14, "bold" if active else "normal"), 
            anchor="w", 
            hover_color=C_APP_BG
        )
        btn.pack(fill="x", padx=10, pady=2)

    def _action_btn(self, text, cmd, bg_col, txt_col, has_border=False):
        kwargs = {
            "master": self.sidebar,
            "text": text,
            "command": cmd,
            "fg_color": bg_col,
            "text_color": txt_col,
            "hover_color": C_APP_BG,
            "height": 32
        }
        
        if has_border:
            kwargs["border_color"] = C_BORDER
            kwargs["border_width"] = 1
        else:
            kwargs["border_width"] = 0
        
        btn = ctk.CTkButton(**kwargs)
        btn.pack(fill="x", padx=20, pady=5)

    def check_queue(self):
        try:
            while True:
                fp = self.file_queue.get_nowait()
                self.process_files([fp], is_new=False)
        except queue.Empty:
            pass
        finally:
            self.after(1000, self.check_queue)

    def reset_ui(self):
        self.session_id += 1
        self.image_stack = []
        self.stitched_image = None
        self.safe_image_ref = None
        self.zoom_level = 1.0
        
        for w in self.scroll.winfo_children():
            w.destroy()
        
        self.ent_supplier.delete(0, "end")
        self.ent_inv.delete(0, "end")
        self.ent_date.delete(0, "end")
        
        self.lbl_total.configure(text="Net Amount: ₹ 0.00")
        self.lbl_preview.configure(image=None, text="Click Upload to Load Invoice\nor use sidebar buttons")
        self.lbl_preview.image = None
        
        self.btn_tally.configure(state="disabled")
        self.btn_scan.configure(state="normal", text="✨ Auto-Fill with AI")
        
        self.lbl_status.configure(text="Status: Ready", text_color=C_TEXT_LABEL)

    def action_new_bill(self):
        self.reset_ui()
        self.after(100, lambda: self.open_dialog(True))

    def action_add_page(self):
        self.open_dialog(False)

    def open_dialog(self, is_new):
        paths = filedialog.askopenfilenames(
            filetypes=[
                ("PDF files", "*.pdf"),
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        if paths:
            self.process_files(paths, is_new)

    def process_files(self, paths, is_new=False):
        current_session = self.session_id
        self.lbl_status.configure(text="Status: Loading...", text_color=C_WARNING)
        
        def worker():
            try:
                imgs = []
                for fp in paths:
                    try:
                        if fp.lower().endswith(".pdf"):
                            doc = fitz.open(fp)
                            try:
                                for page_num in range(len(doc)):
                                    page = doc[page_num]
                                    pix = page.get_pixmap(dpi=150)
                                    pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                    
                                    if pil.width > 1200:
                                        ratio = 1200 / pil.width
                                        pil = pil.resize((1200, int(pil.height * ratio)), Image.Resampling.LANCZOS)
                                    
                                    imgs.append(pil.copy())
                            finally:
                                doc.close()
                        else:
                            with Image.open(fp) as i:
                                if i.mode in ('RGBA', 'LA', 'P'):
                                    bg = Image.new('RGB', i.size, (255, 255, 255))
                                    if i.mode == 'P':
                                        i = i.convert('RGBA')
                                    if i.mode in ('RGBA', 'LA'):
                                        bg.paste(i, mask=i.split()[-1])
                                        i = bg
                                    else:
                                        i = i.convert('RGB')
                                
                                if i.width > 1200:
                                    ratio = 1200 / i.width
                                    i = i.resize((1200, int(i.height * ratio)), Image.Resampling.LANCZOS)
                                
                                imgs.append(i.copy())
                    except Exception as e:
                        print(f"[Process Error] {fp}: {e}")
                        continue
                
                if not imgs or self.session_id != current_session:
                    return
                
                if is_new:
                    self.image_stack = imgs
                else:
                    self.image_stack.extend(imgs)
                
                self.stitch_images(current_session)
                
            except Exception as e:
                print(f"[Worker Error] {e}")
                self.after(0, lambda: self.lbl_status.configure(text="Status: Error loading file", text_color=C_DANGER))
        
        threading.Thread(target=worker, daemon=True).start()

    def stitch_images(self, thread_session_id):
        if not self.image_stack:
            return
        
        try:
            w = self.image_stack[0].width
            h_total = sum(img.height for img in self.image_stack)
            
            final = Image.new("RGB", (w, h_total), "white")
            y = 0
            for img in self.image_stack:
                final.paste(img, (0, y))
                y += img.height
            
            if self.session_id == thread_session_id:
                self.stitched_image = final
                self.after(0, self.update_preview)
                
        except Exception as e:
            print(f"[Stitch Error] {e}")

    def update_preview(self):
        if not self.stitched_image:
            return
        
        try:
            bh = 700
            nh = int(bh * self.zoom_level)
            nw = int(self.stitched_image.width * (nh / self.stitched_image.height))
            
            img = self.stitched_image.resize((nw, nh), Image.Resampling.BOX)
            
            cimg = ctk.CTkImage(img, size=(nw, nh))
            self.safe_image_ref = cimg
            
            self.lbl_preview.configure(image=self.safe_image_ref, text="")
            self.lbl_preview.image = self.safe_image_ref
            
            self.lbl_status.configure(text=f"Status: {len(self.image_stack)} page(s) loaded", text_color=C_SUCCESS)
            
        except Exception as e:
            print(f"[Preview Error] {e}")

    def on_zoom(self, event):
        if event.delta > 0:
            self.zoom_level = min(3.0, self.zoom_level + 0.1)
        else:
            self.zoom_level = max(0.2, self.zoom_level - 0.1)
        self.update_preview()

    def zoom_in(self, event=None):
        self.zoom_level = min(3.0, self.zoom_level + 0.1)
        self.update_preview()

    def zoom_out(self, event=None):
        self.zoom_level = max(0.2, self.zoom_level - 0.1)
        self.update_preview()

    def show_qr(self):
        try:
            if os.path.exists("connect_qr.png"):
                top = ctk.CTkToplevel(self)
                top.title("Mobile Scanner")
                top.geometry("300x350")
                top.configure(fg_color=C_WHITE)
                top.transient(self)
                top.grab_set()
                
                img = Image.open("connect_qr.png").resize((250, 250))
                cimg = ctk.CTkImage(img, size=(250, 250))
                
                ctk.CTkLabel(top, image=cimg, text="").pack(pady=10)
                ctk.CTkLabel(
                    top, 
                    text="Scan with Phone Camera", 
                    font=("Arial", 12), 
                    text_color=C_TEXT_MAIN
                ).pack()
                ctk.CTkLabel(
                    top, 
                    text="Or visit: " + (self.mobile_url or "N/A"), 
                    font=("Arial", 10), 
                    text_color=C_TEXT_LABEL
                ).pack(pady=5)
        except Exception as e:
            messagebox.showerror("Error", f"Could not display QR: {e}")

    def run_ai(self):
        if not self.stitched_image:
            messagebox.showwarning("No Image", "Please upload an invoice image first")
            return
        
        self.btn_scan.configure(state="disabled", text="Extracting...")
        self.lbl_status.configure(text="Status: AI Processing...", text_color=C_PRIMARY)
        
        current_session = self.session_id
        
        def worker():
            try:
                img_byte_arr = io.BytesIO()
                
                send_img = self.stitched_image
                if send_img.height > 2000:
                    ratio = 2000 / send_img.height
                    send_img = send_img.resize((int(send_img.width * ratio), 2000), Image.Resampling.LANCZOS)
                
                send_img.save(img_byte_arr, format='JPEG', quality=70, optimize=True)
                img_byte_arr.seek(0)
                
                compressed_pil = Image.open(img_byte_arr)
                
                data = med_vision.analyze_invoice_image(compressed_pil)
                
                if self.session_id != current_session:
                    return
                
                self.after(0, lambda: self.fill_grid(data))
                
            except Exception as e:
                error_msg = str(e)
                print(f"[AI Worker Error] {error_msg}")
                self.after(0, lambda: messagebox.showerror("Extraction Error", error_msg))
                self.after(0, self.stop_loading)
        
        threading.Thread(target=worker, daemon=True).start()

    def fill_grid(self, data):
        """Fill grid with validation status highlighting"""
        self.stop_loading()
        
        if "error" in data:
            messagebox.showerror("AI Error", data["error"])
            return
        
        # Get validation info
        validation = data.get("validation", {})
        errors_fixed = validation.get("errors_fixed", 0)
        extracted_total = validation.get("extracted_total", 0)
        
        # Show warning if errors were auto-corrected
        if errors_fixed > 0:
            warning_msg = (
                f"⚠️ AI made {errors_fixed} mistakes in quantity extraction.\n\n"
                f"They have been AUTO-CORRECTED to match the Amount column.\n\n"
                f"Extracted Total: ₹{extracted_total:,.2f}\n\n"
                f"Rows with yellow background were fixed. Please verify them."
            )
            messagebox.showwarning("Validation Alert", warning_msg)
        
        # Fill header
        header = data.get("header", {})
        self.ent_supplier.delete(0, "end")
        self.ent_supplier.insert(0, header.get('supplier', ''))
        
        self.ent_inv.delete(0, "end")
        self.ent_inv.insert(0, header.get('inv_no', ''))
        
        raw_date = header.get('date', '')
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0, raw_date)
        
        # Clear existing items
        for w in self.scroll.winfo_children():
            w.destroy()
        
        # Add items with validation status
        items = data.get("items", [])
        for i, item in enumerate(items):
            DataRow(self.scroll, i, item, self.calculate_total).pack(fill="x", pady=2)
        
        self.calculate_total()
        
        # Enable save button
        self.btn_tally.configure(state="normal")
        
        # Update status with validation info
        count = len(items)
        if errors_fixed > 0:
            status_text = f"{count} items, ₹{extracted_total:,.0f} total ({errors_fixed} fixed)"
            self.lbl_status.configure(
                text=f"Status: {status_text}", 
                text_color=C_WARNING
            )
        else:
            self.lbl_status.configure(
                text=f"Status: {count} items extracted - All OK", 
                text_color=C_SUCCESS
            )

    def calculate_total(self):
        total = 0.0
        for w in self.scroll.winfo_children():
            try:
                if isinstance(w, DataRow):
                    amt = float(w.ent_amt.get() or 0)
                    total += amt
            except:
                pass
        
        self.lbl_total.configure(text=f"Net Amount: ₹ {total:,.2f}")

    def stop_loading(self):
        self.btn_scan.configure(state="normal", text="✨ Auto-Fill with AI")

    def push_tally(self):
        """Push to Tally with progress updates"""
        # Pre-push validation
        if not self.ent_supplier.get().strip():
            messagebox.showwarning("Validation", "Supplier name is empty. Please enter a supplier name.")
            self.lbl_status.configure(text="Status: Missing supplier name", text_color=C_DANGER)
            self.btn_tally.configure(state="normal", text="Save to Tally")
            return
        if not self.ent_inv.get().strip():
            messagebox.showwarning("Validation", "Invoice number is empty. Please enter an invoice number.")
            self.lbl_status.configure(text="Status: Missing invoice number", text_color=C_DANGER)
            self.btn_tally.configure(state="normal", text="Save to Tally")
            return
        if not self.ent_date.get().strip():
            messagebox.showwarning("Validation", "Invoice date is empty. Please enter a date.")
            self.lbl_status.configure(text="Status: Missing invoice date", text_color=C_DANGER)
            self.btn_tally.configure(state="normal", text="Save to Tally")
            return

        self.lbl_status.configure(text="Status: Connecting to Tally...", text_color=C_WARNING)
        self.btn_tally.configure(state="disabled", text="Saving...")
        
        # Collect items from UI
        items = []
        for w in self.scroll.winfo_children():
            try:
                if isinstance(w, DataRow):
                    data = w.get_data()
                    try:
                        data["qty"] = float(data["qty"] or 0)
                    except:
                        data["qty"] = 0
                    try:
                        data["rate"] = float(data["rate"] or 0)
                    except:
                        data["rate"] = 0
                    try:
                        data["tax_percent"] = float(data["tax_percent"] or 12)
                    except:
                        data["tax_percent"] = 12
                    
                    items.append(data)
            except Exception as e:
                print(f"[Collect Error] {e}")
        
        if not items:
            messagebox.showerror("Error", "No items to save")
            self.lbl_status.configure(text="Status: No items to save", text_color=C_DANGER)
            self.btn_tally.configure(state="normal", text="Save to Tally")
            return
        
        # Build payload
        header = {
            "supplier": self.ent_supplier.get(),
            "inv_no": self.ent_inv.get(),
            "date": self.ent_date.get()
        }
        
        payload = {"header": header, "items": items}
        
        # Progress callback
        def progress_callback(message, percent):
            self.after(0, lambda: self.lbl_status.configure(
                text=f"Status: {message} ({percent}%)", 
                text_color=C_PRIMARY
            ))
        
        # Worker thread
        def worker():
            try:
                result = self.tally.push_to_tally(payload, progress_callback)
                self.after(0, lambda: self.handle_tally_result(result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Push failed: {e}"))
                self.after(0, lambda: self.lbl_status.configure(
                    text="Status: Sync Failed", 
                    text_color=C_DANGER
                ))
                self.after(0, lambda: self.btn_tally.configure(state="normal", text="Save to Tally"))
        
        threading.Thread(target=worker, daemon=True).start()

    def handle_tally_result(self, result):
        self.btn_tally.configure(state="normal", text="Save to Tally")
        
        if result["status"] == "success":
            messagebox.showinfo("Success", result["msg"])
            self.lbl_status.configure(text="Status: Saved to Tally", text_color=C_SUCCESS)
        else:
            messagebox.showerror("Tally Error", result["msg"])
            self.lbl_status.configure(text="Status: Tally Error", text_color=C_DANGER)


if __name__ == "__main__":
    app = CardioFlowApp()
    app.mainloop()