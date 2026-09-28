"""
ui_assets.py – Asset tab UI and logic for FloodGate
"""

import os, shutil, threading, tkinter as tk, platform
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from core import *

class AssetUI:
    def __init__(self, app):
        self.app = app
        self.config = app.config
        self.fonts = app.fonts
        self.listboxes = app.listboxes
        self.meta = app.meta
        self.projects = app.projects
        self.upload = app.upload
        self.fonts_ok = app.fonts_ok
        self._busy = False
        self.log_widget = None
        self.log_hovered = False

    def build_tab(self, parent):
        tab = tk.Frame(parent, bg=BG_RED)
        self.tab = tab
        sf = ctk.CTkScrollableFrame(tab, fg_color=BG_RED)
        sf.pack(side="left", fill="both", expand=True)

        # Top bar
        fb = tk.Frame(sf, bg=DARK_RED, height=34)
        fb.pack(fill="x", padx=14, pady=(6,4))
        fb.pack_propagate(False)

        tk.Label(fb, text="TEMPLATE:", font=("Courier New",8,"bold"), fg=ACCENT, bg=DARK_RED).pack(side="left", padx=(10,4))
        self.app.template_var = tk.StringVar(value="SAD CLIP / HAPPY CLIP")
        self.app.template_menu = tk.OptionMenu(fb, self.app.template_var, *self.app.templates.keys(), command=self.app._on_template_change)
        self.app.template_menu.config(font=self.app.fonts["body"], bg=DARK_RED, fg=WHITE, activebackground=CARD_BG, bd=0, highlightthickness=0)
        self.app.template_menu["menu"].config(font=self.app.fonts["body"], bg=CARD_BG, fg=WHITE, bd=0)
        self.app.template_menu.pack(side="left", padx=2)
        tk.Button(fb, text="+", font=("Courier New",7,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=4, cursor="hand2", command=self.app._save_template).pack(side="left", padx=1)
        tk.Button(fb, text="✖", font=("Courier New",7,"bold"), fg=TRASH_RED, bg=DARK_RED, bd=0, padx=4, cursor="hand2", command=self.app._remove_template_popup).pack(side="left", padx=1)
        tk.Label(fb, text="FORMAT:", font=("Courier New",8,"bold"), fg=GRAY, bg=DARK_RED).pack(side="left", padx=(10,4))
        self.app.fmt_menu = tk.OptionMenu(fb, self.app.fmt_var, *FORMAT_PRESETS.keys(), command=self.app._on_format_change)
        self.app.fmt_menu.config(font=self.app.fonts["body"], bg=DARK_RED, fg=WHITE, activebackground=CARD_BG, bd=0, highlightthickness=0)
        self.app.fmt_menu["menu"].config(font=self.app.fonts["body"], bg=CARD_BG, fg=WHITE, bd=0)
        self.app.fmt_menu.pack(side="left", padx=2)
        tk.Label(fb, text="LENGTH:", font=("Courier New",8,"bold"), fg=GRAY, bg=DARK_RED).pack(side="left", padx=(14,4))
        self.app.len_menu = tk.OptionMenu(fb, self.app.len_var, *CLIP_LENGTHS.keys(), command=lambda c: (self.app.len_var.set(CLIP_LENGTHS[c]), self.app._save_config()))
        self.app.len_menu.config(font=self.app.fonts["body"], bg=DARK_RED, fg=WHITE, activebackground=CARD_BG, bd=0, highlightthickness=0)
        self.app.len_menu["menu"].config(font=self.app.fonts["body"], bg=CARD_BG, fg=WHITE, bd=0)
        self.app.len_menu.pack(side="left", padx=2)

        # Two columns
        af = tk.Frame(sf, bg=BG_RED)
        af.pack(fill="x", padx=60, pady=(4,0))
        af.columnconfigure(0, weight=1)
        af.columnconfigure(1, weight=1)
        lc = tk.Frame(af, bg=BG_RED)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0,3))
        rc = tk.Frame(af, bg=BG_RED)
        rc.grid(row=0, column=1, sticky="nsew", padx=(3,0))
        for key in ["act_a_videos","act_a_music","act_b_videos","act_b_music"]:
            m = SLOTS[key]
            if m["side"] == "left":
                self._slot(lc, key, m)
            else:
                self._slot(rc, key, m)

        # Center
        ct = tk.Frame(sf, bg=BG_RED)
        ct.pack(fill="x", padx=80, pady=(4,0))
        self._slot(ct, "voiceover_clips", SLOTS["voiceover_clips"])
        self._logo_card(ct)
        self._settings_card(ct)
        self._render_card(ct)

        # Log viewer – the working approach with _parent_canvas
        log_frame = tk.Frame(ct, bg=DARK_RED)
        log_frame.pack(fill="x", pady=(6,0))
        tk.Label(log_frame, text="REMIXER LOG", font=("Courier New",7,"bold"), fg=GRAY, bg=DARK_RED, anchor="w").pack(fill="x", padx=4, pady=(4,0))

        self.log_widget = ctk.CTkTextbox(log_frame, fg_color=DARK_RED, text_color=WHITE, font=("Courier New",11), height=120, wrap="word")
        self.log_widget.pack(fill="x", padx=4, pady=(0,4))
        self.log_widget.insert("end", "Ready for remixer output...\n")
        self.log_widget.configure(state="disabled")

        # Force scrollbar visible
        if hasattr(self.log_widget, '_scrollbar'):
            self.log_widget._scrollbar.pack(side="right", fill="y")

        # --- WORKING SCROLL LOGIC (using _parent_canvas, no errors) ---
        def on_log_scroll(event):
            # Determine scroll direction
            if hasattr(event, 'num'):
                if event.num == 4:
                    units = -1
                elif event.num == 5:
                    units = 1
                else:
                    units = 0
            else:
                delta = event.delta
                if delta > 0:
                    units = -1
                elif delta < 0:
                    units = 1
                else:
                    units = 0
            if units != 0:
                try:
                    if hasattr(self.log_widget, '_parent_canvas'):
                        # Use the canvas method – this worked for scrolling
                        self.log_widget._parent_canvas.yview_scroll(units, "units")
                    else:
                        # Fallback
                        self.log_widget.yview_scroll(units, "units")
                except Exception:
                    # If anything fails, use the fallback
                    self.log_widget.yview_scroll(units, "units")
                return "break"
            return "break"

        # Bind to the log widget itself (catches events on the text area)
        self.log_widget.bind("<MouseWheel>", on_log_scroll, add="+")
        self.log_widget.bind("<Button-4>", on_log_scroll, add="+")
        self.log_widget.bind("<Button-5>", on_log_scroll, add="+")
        # Also bind to the internal text widget if it exists
        if hasattr(self.log_widget, '_textbox'):
            self.log_widget._textbox.bind("<MouseWheel>", on_log_scroll, add="+")
            self.log_widget._textbox.bind("<Button-4>", on_log_scroll, add="+")
            self.log_widget._textbox.bind("<Button-5>", on_log_scroll, add="+")

        # Hover tracking for global scroll bypass
        def set_hover(state):
            self.log_hovered = state
        self.log_widget.bind("<Enter>", lambda e: set_hover(True), add="+")
        self.log_widget.bind("<Leave>", lambda e: set_hover(False), add="+")
        if hasattr(self.log_widget, '_textbox'):
            self.log_widget._textbox.bind("<Enter>", lambda e: set_hover(True), add="+")
            self.log_widget._textbox.bind("<Leave>", lambda e: set_hover(False), add="+")

        return tab

    # ------------------------------------------------------------------
    # All other methods (unchanged)
    # ------------------------------------------------------------------
    def _slot(self, parent, key, meta):
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="x", pady=(0,6), ipady=2)
        tk.Label(card, text=meta["label"], font=self.fonts["subheading"], fg=WHITE, bg=CARD_BG).pack(pady=(8,1))
        tk.Label(card, text=meta["hint"], font=self.fonts["small"], fg="#E8DDD4", bg=CARD_BG).pack(pady=(0,4))
        lb = tk.Listbox(card, bg=DARK_RED, fg=WHITE, selectbackground=WHITE, selectforeground=BLACK, font=self.fonts["body"], height=3, bd=0, highlightthickness=0, activestyle="none")
        lb.pack(fill="x", padx=12, pady=(0,4))
        self.listboxes[key] = lb
        lb.bind("<Delete>", lambda e, k=key: self._remove_selected(k))
        lb.bind("<BackSpace>", lambda e, k=key: self._remove_selected(k))
        br = tk.Frame(card, bg=CARD_BG)
        br.pack(pady=(0,6))
        HoverButton(br, text="ADD", font=("Courier New",8,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=10, pady=2, cursor="hand2", command=lambda k=key,m=meta: self._add_files(k,m)).pack(side="left", padx=2)
        HoverButton(br, text="REMOVE", font=self.fonts["body"], fg=WHITE, bg=DARK_RED, hover_bg="#7A0000", bd=0, padx=10, pady=2, cursor="hand2", command=lambda k=key: self._remove_selected(k)).pack(side="left", padx=2)

    def _logo_card(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="x", pady=(0,6), ipady=2)
        tk.Label(card, text=LOGO_SLOT["label"], font=self.fonts["heading"], fg=WHITE, bg=CARD_BG).pack(pady=(8,1))
        tk.Label(card, text=LOGO_SLOT["hint"], font=self.fonts["tiny"], fg=GRAY, bg=CARD_BG).pack(pady=(0,4))
        self.logo_var = tk.StringVar()
        tk.Entry(card, textvariable=self.logo_var, font=self.fonts["body"], bg=DARK_RED, fg=WHITE, insertbackground=WHITE, bd=0, justify="center").pack(fill="x", padx=16, ipady=3)
        HoverButton(card, text="SELECT LOGO", font=("Courier New",8,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=12, pady=3, cursor="hand2", command=self._add_logo).pack(pady=(4,8))

    def _settings_card(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="x", pady=(0,6), ipady=2)
        tk.Label(card, text="SETTINGS", font=self.fonts["heading"], fg=WHITE, bg=CARD_BG).pack(pady=(8,4))
        self.preview_var = tk.BooleanVar(value=self.config["settings"].get("preview_mode", True))
        tk.Checkbutton(card, text="Preview Mode (1080p)", variable=self.preview_var, font=self.fonts["small"], fg=WHITE, bg=CARD_BG, selectcolor=DARK_RED, activebackground=CARD_BG, activeforeground=WHITE, relief="flat", command=self._save_settings).pack(pady=(0,4))
        tk.Label(card, text="CAPTION FONT", font=("Courier New",7,"bold"), fg=GRAY, bg=CARD_BG).pack(pady=(6,0))
        cf = self.config.get("caption_font", "Impact")
        if cf not in self.fonts_ok: cf = "Impact"
        self.font_preview = tk.Label(card, text="Aa Bb Cc 123", font=(cf,14), fg=WHITE, bg=DARK_RED)
        self.font_preview.pack(pady=(2,4), ipadx=20, ipady=2)
        self.cap_font_var = tk.StringVar(value=cf)
        fd = tk.OptionMenu(card, self.cap_font_var, cf, *self.fonts_ok, command=lambda c: (self.cap_font_var.set(c), self.config.update({"caption_font":c}), self.app._save_config(), self.font_preview.config(font=(c,14))))
        fd.config(font=self.fonts["body"], bg=DARK_RED, fg=WHITE, activebackground=CARD_BG, bd=0, highlightthickness=1, highlightcolor=BORDER, highlightbackground=CARD_BG, width=28)
        fd["menu"].config(font=self.fonts["body"], bg=CARD_BG, fg=WHITE, activebackground=DARK_RED, bd=0)
        fd.pack(fill="x", padx=8, pady=(2,6))
        caps = self.config.get("captions", {})
        for act, vn, lb in [("act_a","cap_a_var","ACT A"), ("act_b","cap_b_var","ACT B")]:
            tk.Label(card, text=lb, font=("Courier New",7,"bold"), fg=GRAY, bg=CARD_BG).pack(pady=(3,1))
            e = tk.Entry(card, font=self.fonts["body"], bg=DARK_RED, fg=WHITE, insertbackground=WHITE, bd=0, highlightthickness=1, highlightcolor=BORDER, highlightbackground=CARD_BG, justify="center")
            e.pack(fill="x", padx=16, ipady=2)
            sv = tk.StringVar(value=caps.get(act, ""))
            e.configure(textvariable=sv)
            setattr(self, vn, sv)
        HoverButton(card, text="SAVE", font=("Courier New",8,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=12, pady=3, command=self._save_settings).pack(pady=(8,8))

    def _render_card(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="x", pady=(0,6), ipady=2)
        tk.Label(card, text="RENDER", font=self.fonts["heading"], fg=WHITE, bg=CARD_BG).pack(pady=(8,2))
        self.render_count_var = tk.IntVar(value=self.config.get("num_renders",10))
        self.count_label = tk.Label(card, text=str(self.render_count_var.get()), font=("Helvetica Neue",28,"bold"), fg=WHITE, bg=CARD_BG)
        self.count_label.pack()
        tk.Scale(card, from_=1, to=100, orient="horizontal", variable=self.render_count_var,
                 command=lambda v: (self.count_label.config(text=str(int(float(v)))),
                                    self.config.update({"num_renders": int(float(v))}),
                                    self.app._save_config()),
                 bg=CARD_BG, fg=WHITE, troughcolor=DARK_RED, highlightthickness=0, bd=0, length=240, showvalue=False).pack(pady=(0,3))
        pr = tk.Frame(card, bg=CARD_BG)
        pr.pack(pady=(0,4))
        for n in [5,10,25,50,100]:
            HoverButton(pr, text=str(n), font=("Courier New",8,"bold"), fg=GRAY, bg=DARK_RED, hover_bg=ACCENT, hover_fg=WHITE, bd=0, padx=8, pady=1, cursor="hand2",
                        command=lambda v=n: (self.render_count_var.set(v), self.count_label.config(text=str(v)), self.config.update({"num_renders":v}), self.app._save_config())).pack(side="left", padx=1)
        HoverButton(card, text="▶  RUN REMIXER  (Ctrl+R)", font=("Helvetica Neue",11,"bold"), fg=BLACK, bg=WHITE, hover_bg=ACCENT, hover_fg=WHITE, bd=0, padx=24, pady=6, cursor="hand2", command=self.app._run_remixer).pack(pady=(0,8))

    # ------------------------------------------------------------------
    # Log methods
    # ------------------------------------------------------------------
    def clear_log(self):
        if self.log_widget:
            self.log_widget.configure(state="normal")
            self.log_widget.delete("1.0", "end")
            self.log_widget.configure(state="disabled")

    def log(self, message):
        if self.log_widget:
            self.app.after(0, lambda: self._do_log(message))

    def _do_log(self, message):
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _add_files(self, key, meta):
        if self._busy: return
        paths = filedialog.askopenfilenames(title=f"Select files for {meta['label']}", filetypes=meta["types"] + [("All files","*.*")])
        if not paths: return
        threading.Thread(target=self._process_files, args=(key, meta, paths), daemon=True).start()

    def _process_files(self, key, meta, paths):
        self._busy = True
        self.app.after(0, lambda: self.app._show_progress(True))
        added = 0
        total = len(paths)
        base_dir = Path(__file__).parent.resolve()
        for idx, path in enumerate(paths):
            src = Path(path)
            size = src.stat().st_size
            if size > 200 * 1024 * 1024:
                rel = str(src).replace("\\", "/")
            else:
                dd = base_dir / meta["subfolder"]
                dd.mkdir(parents=True, exist_ok=True)
                dest = dd / src.name
                if str(dest) != str(src):
                    shutil.copy2(str(src), str(dest))
                rel = str(dest.relative_to(base_dir)).replace("\\", "/")
            cur = self.config.get(key, [])
            if rel not in cur:
                cur.append(rel)
                added += 1
            self.config[key] = cur
            progress = (idx + 1) / total
            self.app.after(0, lambda p=progress: self.app._update_progress(p))
        self.app._save_config()
        self.app.after(0, lambda: (self._refresh_listbox(key), self.app._show_progress(False)))
        self.app._set_status(f"{added} file(s) added.")
        self._busy = False

    def _remove_selected(self, key):
        lb = self.listboxes.get(key)
        if not lb: return
        sel = lb.curselection()
        if not sel: return
        items = list(self.config.get(key, []))
        for i in reversed(sel):
            if i < len(items):
                items.pop(i)
        self.config[key] = items
        self.app._save_config()
        self._refresh_listbox(key)
        self.app._set_status("Removed.")

    def _add_logo(self):
        if self._busy: return
        p = filedialog.askopenfilename(title="Select Logo", filetypes=LOGO_SLOT["types"] + [("All files","*.*")])
        if not p: return
        threading.Thread(target=self._process_logo, args=(p,), daemon=True).start()

    def _process_logo(self, path):
        self._busy = True
        src = Path(path)
        size = src.stat().st_size
        base_dir = Path(__file__).parent.resolve()
        if size > 200 * 1024 * 1024:
            rel = str(src).replace("\\", "/")
        else:
            dd = base_dir / LOGO_SLOT["subfolder"]
            dd.mkdir(parents=True, exist_ok=True)
            dest = dd / src.name
            if str(dest) != str(src):
                shutil.copy2(str(src), str(dest))
            rel = str(dest.relative_to(base_dir)).replace("\\", "/")
        self.config["logo"] = rel
        self.app._save_config()
        self.app.after(0, lambda: self.logo_var.set(rel))
        self.app._set_status(f"Logo: {src.name}")
        self._busy = False

    def _refresh_listbox(self, key):
        lb = self.listboxes.get(key)
        if not lb: return
        lb.delete(0, "end")
        for path in self.config.get(key, []):
            full = Path(path)
            if not full.is_absolute():
                full = self.app.BASE_DIR / full
            sz = f"[{human_size(full.stat().st_size)}]" if full.exists() else "[MISSING]"
            name = full.name
            if len(name) > 38:
                name = name[:18] + "..." + name[-15:]
            entry = f" {sz:>10}  {name}"
            lb.insert("end", entry)

    def _save_settings(self):
        self.config["settings"]["preview_mode"] = self.preview_var.get()
        self.config["captions"]["act_a"] = self.cap_a_var.get()
        self.config["captions"]["act_b"] = self.cap_b_var.get()
        self.config["caption_font"] = self.cap_font_var.get()
        self.config["settings"]["format"] = self.app.fmt_var.get()
        self.config["settings"]["template"] = self.app.template_var.get()
        self.config["settings"]["clip_length"] = self.app.len_var.get()
        self.app._save_config()
        self.app._set_status("Settings saved.")

    def refresh_all(self):
        for key in self.listboxes:
            self._refresh_listbox(key)
        self.logo_var.set(self.config.get("logo", ""))