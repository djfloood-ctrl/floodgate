"""
FLOODGATE v2.3
Main application – assets and browse are split into separate UI modules.
"""

import os, shutil, subprocess, sys, threading, tkinter as tk, platform
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

from core import *
from ui_assets import AssetUI
from ui_browse import BrowseUI

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "config.json"
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUT_DIR = BASE_DIR / "output"
TRASH_DIR = BASE_DIR / "trash"
META_PATH = BASE_DIR / "clip_meta.json"
LOGO_PATH = BASE_DIR / "floodgate_icon.png"

class FloodGate(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("FLOODGATE")
        self.configure(fg_color=BG_RED)
        self.geometry("960x680")
        self.minsize(800,600)

        self.fonts = {
            "title": ("Helvetica Neue", 14, "bold"),
            "heading": ("Helvetica Neue", 10, "bold"),
            "subheading": ("Helvetica Neue", 9, "bold"),
            "body": ("Courier New", 8),
            "small": ("Courier New", 7),
            "tiny": ("Courier New", 6),
            "button": ("Courier New", 8, "bold"),
        }
        self.config = self._load_config()
        FORMAT_PRESETS.update(self.config.get("custom_formats", {}))
        CLIP_LENGTHS.update(self.config.get("custom_lengths", {}))
        self.templates = self.config.get("templates", dict(DEFAULT_TEMPLATES))
        self.projects = ProjectManager(PROJECTS_DIR)
        self.meta = ClipMeta(META_PATH, OUTPUT_DIR, TRASH_DIR)
        self.upload = UploadManager()
        self.fonts_all = scan_fonts()
        self.fonts_ok = valid_fonts(self.fonts_all)
        self.listboxes = {}
        self._busy = False
        self._logo_img = None

        self.BASE_DIR = BASE_DIR
        self.OUTPUT_DIR = OUTPUT_DIR
        self.TRASH_DIR = TRASH_DIR

        self.browse_sort = tk.StringVar(value="date_desc")
        self.browse_tag = tk.StringVar(value="all")
        self.browse_folder = tk.StringVar(value="all")
        self.browse_search = tk.StringVar(value="")
        self.fmt_var = tk.StringVar(value=self.config.get("settings",{}).get("format","Reel / TikTok (9:16)"))
        self.len_var = tk.IntVar(value=self.config.get("settings",{}).get("clip_length",30))

        OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
        TRASH_DIR.mkdir(parents=True,exist_ok=True)
        for s in SLOTS.values(): (BASE_DIR/s["subfolder"]).mkdir(parents=True,exist_ok=True)
        (BASE_DIR/LOGO_SLOT["subfolder"]).mkdir(parents=True,exist_ok=True)

        self.bind("<F11>",lambda e:self.attributes("-fullscreen",not self.attributes("-fullscreen")))
        self.bind_all("<MouseWheel>", self._global_scroll)

        self._live_polling = False
        self._poll_counter = 0
        self._last_browse_state = None
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = None
        self._process = None

        self._build_ui()
        self.bind("<Control-r>",lambda e:self._run_remixer())
        self.bind("<Control-R>",lambda e:self._run_remixer())
        self._refresh_all()
        self._refresh_project_menu()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _load_config(self):
        c = load_json(CONFIG_PATH, {"act_a_videos":[], "act_b_videos":[], "act_a_music":[], "act_b_music":[], "voiceover_clips":[], "logo":"", "num_renders":10, "caption_font":"Impact", "captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"}, "settings":{"preview_mode":True, "music_volume":0.35, "format":"Reel / TikTok (9:16)", "clip_length":15}})
        if "caption_font" not in c: c["caption_font"]="Impact"
        return c

    def _save_config(self):
        save_json(CONFIG_PATH, self.config)

    def _set_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------
    def _global_scroll(self, event):
        # --- FIX: If the mouse is over the log widget, do nothing ---
        if hasattr(self, 'asset_ui') and self.asset_ui.log_hovered:
            return "break"
        # -----------------------------------------------------------

        now = event.time
        delta = event.delta
        if not hasattr(self, '_last_scroll_time'):
            self._last_scroll_time = now
            self._scroll_momentum = 0
        time_diff = max(now - self._last_scroll_time, 1)
        self._last_scroll_time = now
        base = abs(delta) / 15
        if time_diff < 80:
            self._scroll_momentum = min(self._scroll_momentum + 0.5, 4.0)
        else:
            self._scroll_momentum = max(self._scroll_momentum - 0.3, 1.0)
        speed = base * self._scroll_momentum
        direction = -1 if delta > 0 else 1
        amount = int(direction * speed)

        widget = event.widget
        if isinstance(widget, tk.Listbox):
            widget.yview_scroll(amount, "units")
            return "break"
        parent = widget
        while parent:
            if hasattr(parent, '_parent_canvas'):
                parent._parent_canvas.yview_scroll(amount, "units")
                return "break"
            if isinstance(parent, tk.Canvas) and hasattr(parent, 'yview_scroll'):
                parent.yview_scroll(amount, "units")
                return "break"
            parent = parent.master
        if hasattr(self, 'browse_ui') and hasattr(self.browse_ui, 'bcv') and self.browse_ui.bcv.winfo_ismapped():
            self.browse_ui.bcv._parent_canvas.yview_scroll(amount, "units")
        elif 'ASSETS' in self.tabs and self.tabs['ASSETS'].winfo_ismapped():
            sf = self.tabs['ASSETS'].winfo_children()[0]
            if hasattr(sf, '_parent_canvas'):
                sf._parent_canvas.yview_scroll(amount, "units")
        return "break"

    # ------------------------------------------------------------------
    # UI Build (unchanged)
    # ------------------------------------------------------------------
    def _build_ui(self):
        tb = tk.Frame(self, bg=DARK_RED, height=40)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        try:
            if LOGO_PATH.exists():
                img = tk.PhotoImage(file=str(LOGO_PATH)).subsample(4,4)
                tk.Label(tb, image=img, bg=DARK_RED).pack(side="left", padx=(12,4), pady=2)
                self._logo_img = img
        except: pass
        tk.Label(tb, text="FLOODGATE", font=self.fonts["title"], fg=WHITE, bg=DARK_RED).pack(side="left", pady=6)
        self.proj_var = tk.StringVar(value="Default")
        self.proj_menu = tk.OptionMenu(tb, self.proj_var, "Default", command=self._on_project)
        self.proj_menu.config(font=self.fonts["small"], bg=DARK_RED, fg=WHITE, activebackground=CARD_BG, bd=0, highlightthickness=1, highlightcolor=BORDER)
        self.proj_menu["menu"].config(font=self.fonts["body"], bg=CARD_BG, fg=WHITE, activebackground=DARK_RED, bd=0)
        self.proj_menu.pack(side="left", padx=6)
        tk.Button(tb, text="+", font=("Courier New",8,"bold"), fg=BLACK, bg=WHITE, activebackground=GRAY, bd=0, padx=8, pady=1, cursor="hand2", command=self._new_project).pack(side="left", padx=2)
        self.tab_btns = {}
        for name, icon in [("ASSETS","⬡"), ("BROWSE","▹"), ("UPLOAD","↑")]:
            btn = tk.Button(tb, text=f" {icon} {name} ", font=self.fonts["button"], fg=TAB_INACTIVE, bg=DARK_RED, activebackground=DARK_RED, activeforeground=WHITE, bd=0, cursor="hand2", relief="flat", command=lambda n=name: self.show_tab(n))
            btn.pack(side="left", ipady=8)
            self.tab_btns[name] = btn

        self.content = tk.Frame(self, bg=BG_RED)
        self.content.pack(fill="both", expand=True)
        self.tabs = {}

        self.asset_ui = AssetUI(self)
        self.browse_ui = BrowseUI(self)

        self.tabs["ASSETS"] = self.asset_ui.build_tab(self.content)
        self.tabs["BROWSE"] = self.browse_ui.build_tab(self.content)
        self._build_upload()

        self.show_tab("ASSETS")

        status_frame = tk.Frame(self, bg=DARK_RED)
        status_frame.pack(fill="x", padx=12, pady=4)
        self.status_var = tk.StringVar(value="Ready  •  Ctrl+R  •  F11")
        tk.Label(status_frame, textvariable=self.status_var, font=self.fonts["small"], fg=GRAY, bg=DARK_RED, anchor="w").pack(side="left", fill="x", expand=True)
        self.progress_bar = ctk.CTkProgressBar(status_frame, width=150, height=12, fg_color="#6B1010", progress_color=ACCENT)
        self.progress_bar.pack(side="right", padx=(10,0))
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()

    def show_tab(self, name):
        for n, f in self.tabs.items():
            f.pack_forget()
        if name in self.tabs:
            self.tabs[name].pack(fill="both", expand=True)
        for n, b in self.tab_btns.items():
            b.config(fg=TAB_ACTIVE if n == name else TAB_INACTIVE)
        if name == "BROWSE" and not hasattr(self.browse_ui, '_browse_loaded'):
            self.browse_ui._refresh_browse()

    # ------------------------------------------------------------------
    # Upload Tab
    # ------------------------------------------------------------------
    def _build_upload(self):
        tab = tk.Frame(self.content, bg=BG_RED)
        self.tabs["UPLOAD"] = tab
        hdr = tk.Frame(tab, bg=BG_RED)
        hdr.pack(fill="x", padx=20, pady=(14,8))
        tk.Label(hdr, text="UPLOAD QUEUE", font=self.fonts["title"], fg=WHITE, bg=BG_RED).pack(side="left")
        st = tk.Frame(tab, bg=BG_RED)
        st.pack(fill="x", padx=20, pady=(0,8))
        self.ig_lbl = tk.Label(st, text="IG: NOT PAIRED", font=("Courier New",7,"bold"), fg=GRAY, bg=BG_RED)
        self.ig_lbl.pack(side="left", padx=(0,14))
        HoverButton(st, text="PAIR IG", font=("Courier New",7,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=8, pady=1,
                    command=lambda: (setattr(self.upload, 'paired_ig', True), self.ig_lbl.config(text="IG: PAIRED", fg=UPLOAD_GREEN), messagebox.showinfo("Instagram", "Paired!"))).pack(side="left", padx=2)
        self.tt_lbl = tk.Label(st, text="TT: NOT PAIRED", font=("Courier New",7,"bold"), fg=GRAY, bg=BG_RED)
        self.tt_lbl.pack(side="left", padx=(14,0))
        HoverButton(st, text="PAIR TT", font=("Courier New",7,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=8, pady=1,
                    command=lambda: (setattr(self.upload, 'paired_tt', True), self.tt_lbl.config(text="TT: PAIRED", fg=UPLOAD_GREEN), messagebox.showinfo("TikTok", "Paired!"))).pack(side="left", padx=2)
        self.ulb_frame = ctk.CTkScrollableFrame(tab, fg_color=DARK_RED)
        self.ulb_frame.pack(fill="both", expand=True, padx=20, pady=(6,6))
        self.ulb = tk.Listbox(self.ulb_frame, bg=DARK_RED, fg=WHITE, selectbackground=WHITE, selectforeground=BLACK, font=self.fonts["body"], bd=0, height=20)
        self.ulb.pack(fill="both", expand=True)
        br = tk.Frame(tab, bg=BG_RED)
        br.pack(fill="x", padx=20, pady=(0,14))
        HoverButton(br, text="REMOVE", font=("Courier New",8,"bold"), fg=BLACK, bg=ACCENT, bd=0, padx=10, pady=4, command=self._remove_draft).pack(side="left")
        HoverButton(br, text="UPLOAD ALL", font=("Courier New",8,"bold"), fg=BLACK, bg=UPLOAD_GREEN, bd=0, padx=10, pady=4, command=self._upload_all).pack(side="right")
        self._refresh_upload()

    def _refresh_upload(self):
        self.ulb.delete(0, "end")
        for d in self.upload.get():
            self.ulb.insert("end", f"  [{d['status'].upper()}] {Path(d['video']).name[:45]} → {','.join(d['platforms'])}")

    def _remove_draft(self):
        sel = self.ulb.curselection()
        if sel:
            self.upload.remove(sel[0])
            self._refresh_upload()

    def _upload_all(self):
        drafts = self.upload.get()
        if not drafts:
            messagebox.showinfo("Queue", "No drafts.")
            return
        for d in drafts:
            d["status"] = "uploaded"
        self._refresh_upload()
        messagebox.showinfo("Upload", f"{len(drafts)} uploaded!")

    # ------------------------------------------------------------------
    # Project / Settings / Templates
    # ------------------------------------------------------------------
    def _on_project(self, choice):
        if not choice:
            return
        self._save_proj()
        proj = self.projects.get(choice)
        if proj:
            a = proj.get("assets", {})
            for key in SLOTS:
                self.config[key] = list(a.get(key, []))
            self.config["logo"] = a.get("logo", "")
            self.config["captions"] = dict(proj.get("captions", {}))
            self.config["settings"].update(proj.get("settings", {}))
            self.config["num_renders"] = proj.get("settings", {}).get("num_renders", 10)
            self.config["caption_font"] = proj.get("settings", {}).get("caption_font", "Impact")
            self.fmt_var.set(proj.get("settings", {}).get("format", "Reel / TikTok (9:16)"))
            self.template_var.set(proj.get("settings", {}).get("template", "SAD CLIP / HAPPY CLIP"))
            self.len_var.set(proj.get("settings", {}).get("clip_length", 30))
            self.projects.current = choice
            self._refresh_all()
            self._set_status(f"Loaded: {choice}")

    def _save_proj(self):
        if self.projects.current:
            data = {
                "name": self.projects.current,
                "assets": {
                    "act_a_videos": self.config.get("act_a_videos", []),
                    "act_b_videos": self.config.get("act_b_videos", []),
                    "act_a_music": self.config.get("act_a_music", []),
                    "act_b_music": self.config.get("act_b_music", []),
                    "voiceover_clips": self.config.get("voiceover_clips", []),
                    "longform_source": self.config.get("longform_source", []),
                    "logo": self.config.get("logo", "")
                },
                "captions": dict(self.config.get("captions", {})),
                "settings": dict(self.config.get("settings", {}))
            }
            data["settings"]["num_renders"] = self.config.get("num_renders", 10)
            data["settings"]["caption_font"] = self.config.get("caption_font", "Impact")
            data["settings"]["format"] = self.fmt_var.get()
            data["settings"]["clip_length"] = self.len_var.get()
            data["settings"]["template"] = self.template_var.get()
            self.projects.save(self.projects.current, data)

    def _new_project(self):
        self._save_proj()
        name = simpledialog.askstring("New Project", "Artist / Project name:")
        if name:
            if self.projects.create(name):
                self._refresh_project_menu()
                self.proj_var.set(name)
                self._on_project(name)
            else:
                messagebox.showerror("Error", "Project already exists.")

    def _refresh_project_menu(self):
        menu = self.proj_menu["menu"]
        menu.delete(0, "end")
        for name in self.projects.list_names():
            menu.add_command(label=name, command=lambda v=name: (self.proj_var.set(v), self._on_project(v)))

    def _refresh_all(self):
        self.asset_ui.refresh_all()
        self.browse_ui._refresh_browse()
        self._refresh_project_menu()

    # ------------------------------------------------------------------
    # Template / Format methods
    # ------------------------------------------------------------------
    def _on_template_change(self, choice):
        self.template_var.set(choice)
        self._show_template(choice)
        self.config["settings"]["template"] = choice
        self._save_config()

    def _show_template(self, template_name):
        for key, meta in SLOTS.items():
            if key not in self.listboxes:
                continue
            lb = self.listboxes[key]
            card = lb.master
            if key == "longform_source" or meta.get("subfolder") == "assets/longform":
                if template_name == "LONGFORM CLIPS":
                    card.pack(fill="x", pady=(0,6), ipady=4)
                else:
                    card.pack_forget()
            elif key in ["act_a_videos","act_b_videos","act_a_music","act_b_music"]:
                if template_name == "SAD CLIP / HAPPY CLIP":
                    card.pack(fill="x", pady=(0,6), ipady=4)
                else:
                    card.pack_forget()

    def _save_template(self):
        name = simpledialog.askstring("Add Template", "Template name:")
        if not name:
            return
        if name in self.templates:
            messagebox.showinfo("Exists", "Already exists.")
            return
        self.templates[name] = ["act_a_videos","act_b_videos","act_a_music","act_b_music","voiceover_clips"]
        self._rebuild_template_menu()
        self.template_var.set(name)
        self._persist_templates()
        self._set_status(f"Added: {name}")

    def _remove_template_popup(self):
        name = self.template_var.get()
        if name in ["SAD CLIP / HAPPY CLIP", "LONGFORM CLIPS"]:
            messagebox.showinfo("Protected", "Cannot remove defaults.")
            return
        p = tk.Toplevel(self)
        p.title("Remove")
        p.configure(bg=DARK_RED)
        p.geometry("340x180")
        p.resizable(False, False)
        p.transient(self)
        p.grab_set()
        p.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 340) // 2
        y = self.winfo_y() + (self.winfo_height() - 180) // 2
        p.geometry(f"+{x}+{y}")
        tk.Label(p, text="REMOVE TEMPLATE", font=("Consolas", 12, "bold"), fg=WHITE, bg=DARK_RED).pack(pady=(16,8))
        tk.Label(p, text=name, font=("Consolas", 10), fg=ACCENT, bg=DARK_RED).pack()
        bf = tk.Frame(p, bg=DARK_RED)
        bf.pack(pady=(12,8))
        tk.Button(bf, text="DELETE", font=("Consolas", 10, "bold"), fg=WHITE, bg=TRASH_RED, bd=0, padx=14, pady=4,
                  command=lambda: (self.templates.pop(name, None), self._persist_templates(),
                                   self._rebuild_template_menu(), self.template_var.set("SAD CLIP / HAPPY CLIP"),
                                   p.destroy())).pack(side="left", padx=4)
        tk.Button(bf, text="ARCHIVE", font=("Consolas", 10, "bold"), fg=BLACK, bg=ACCENT, bd=0, padx=14, pady=4,
                  command=p.destroy).pack(side="left", padx=4)
        tk.Button(bf, text="CANCEL", font=("Consolas", 10), fg=WHITE, bg="#6B1010", bd=0, padx=14, pady=4,
                  command=p.destroy).pack(side="left", padx=4)

    def _rebuild_template_menu(self):
        m = self.template_menu["menu"]
        m.delete(0, "end")
        for t in self.templates.keys():
            m.add_command(label=t, command=lambda v=t: self._on_template_change(v))

    def _persist_templates(self):
        self.config["templates"] = self.templates
        self._save_config()

    def _on_format_change(self, choice):
        if choice == "Custom":
            self._open_custom_dialog()
            return
        self.fmt_var.set(choice)
        if choice in FORMAT_PRESETS:
            p = FORMAT_PRESETS[choice]
            self.config["settings"]["target_w"] = p["w"]
            self.config["settings"]["target_h"] = p["h"]
            self.config["settings"]["target_fps"] = p["fps"]
        self.config["settings"]["format"] = choice
        self._save_config()

    def _open_custom_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Custom Format")
        dialog.configure(bg=DARK_RED)
        dialog.geometry("300x280")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.attributes("-topmost", True)
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 300) // 2
        y = self.winfo_y() + (self.winfo_height() - 280) // 2
        dialog.geometry(f"+{x}+{y}")
        tk.Label(dialog, text="CUSTOM FORMAT", font=("Helvetica Neue", 12, "bold"), fg=WHITE, bg=DARK_RED).pack(pady=(16,12))
        wf = tk.Frame(dialog, bg=DARK_RED)
        wf.pack(fill="x", padx=30, pady=6)
        tk.Label(wf, text="Width (px):", font=("Courier New", 10), fg=GRAY, bg=DARK_RED).pack(side="left")
        wv = tk.IntVar(value=1080)
        tk.Entry(wf, textvariable=wv, font=("Courier New", 10), bg="#6B1010", fg=WHITE, insertbackground=WHITE, bd=0, width=8, justify="center").pack(side="right")
        hf = tk.Frame(dialog, bg=DARK_RED)
        hf.pack(fill="x", padx=30, pady=6)
        tk.Label(hf, text="Height (px):", font=("Courier New", 10), fg=GRAY, bg=DARK_RED).pack(side="left")
        hv = tk.IntVar(value=1920)
        tk.Entry(hf, textvariable=hv, font=("Courier New", 10), bg="#6B1010", fg=WHITE, insertbackground=WHITE, bd=0, width=8, justify="center").pack(side="right")
        ff = tk.Frame(dialog, bg=DARK_RED)
        ff.pack(fill="x", padx=30, pady=6)
        tk.Label(ff, text="FPS:", font=("Courier New", 10), fg=GRAY, bg=DARK_RED).pack(side="left")
        fv = tk.IntVar(value=30)
        tk.Entry(ff, textvariable=fv, font=("Courier New", 10), bg="#6B1010", fg=WHITE, insertbackground=WHITE, bd=0, width=8, justify="center").pack(side="right")
        def save():
            try:
                w, h, fps = wv.get(), hv.get(), fv.get()
            except tk.TclError:
                messagebox.showerror("Custom Format", "Width, height and FPS must be whole numbers.", parent=dialog)
                return
            if not (16 <= w <= 7680 and 16 <= h <= 7680 and 1 <= fps <= 120):
                messagebox.showerror("Custom Format", "Width/height must be 16-7680 px and FPS 1-120.", parent=dialog)
                return
            # libx264 with yuv420p needs even dimensions
            w, h = w - w % 2, h - h % 2
            self.config["settings"]["target_w"] = w
            self.config["settings"]["target_h"] = h
            self.config["settings"]["target_fps"] = fps
            self.config["settings"]["format"] = "Custom"
            self.fmt_var.set("Custom")
            self._save_config()
            dialog.destroy()
        def cancel():
            self.fmt_var.set("Reel / TikTok (9:16)")
            dialog.destroy()
        btn_frame = tk.Frame(dialog, bg=DARK_RED)
        btn_frame.pack(pady=(16,12))
        tk.Button(btn_frame, text="APPLY", font=("Courier New", 10, "bold"), fg=BLACK, bg=WHITE, bd=0, padx=16, pady=4, cursor="hand2", command=save).pack(side="left", padx=4)
        tk.Button(btn_frame, text="CANCEL", font=("Courier New", 10), fg=WHITE, bg="#6B1010", bd=0, padx=16, pady=4, cursor="hand2", command=cancel).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.wait_window()

    def _save_format_preset(self):
        name = simpledialog.askstring("Save Format", "Preset name (e.g. 'My Custom 4K'):")
        if not name:
            return
        if name in BUILTIN_FORMATS:
            messagebox.showinfo("Exists", "A built-in format already uses that name.")
            return
        FORMAT_PRESETS[name] = {"w": self.config["settings"].get("target_w", 1080),
                                 "h": self.config["settings"].get("target_h", 1920),
                                 "fps": self.config["settings"].get("target_fps", 30)}
        self.config.setdefault("custom_formats", {})[name] = FORMAT_PRESETS[name]
        self._save_config()
        menu = self.fmt_menu["menu"]
        menu.delete(0, "end")
        for f in FORMAT_PRESETS.keys():
            menu.add_command(label=f, command=lambda v=f: self._on_format_change(v))
        self.fmt_var.set(name)
        self._set_status(f"Format saved: {name}")

    def _remove_format_preset(self):
        name = self.fmt_var.get()
        if name in BUILTIN_FORMATS:
            messagebox.showinfo("Protected", "Cannot remove default formats.")
            return
        if messagebox.askyesno("Remove", f"Delete format '{name}'?"):
            del FORMAT_PRESETS[name]
            self.config.get("custom_formats", {}).pop(name, None)
            self._save_config()
            menu = self.fmt_menu["menu"]
            menu.delete(0, "end")
            for f in FORMAT_PRESETS.keys():
                menu.add_command(label=f, command=lambda v=f: self._on_format_change(v))
            self.fmt_var.set("Widescreen (16:9)")
            self._set_status(f"Removed: {name}")

    def _save_length_preset(self):
        name = simpledialog.askstring("Save Length", "Preset name (e.g. '45 secs'):")
        if not name:
            return
        if name in BUILTIN_LENGTHS:
            messagebox.showinfo("Exists", "A built-in length already uses that name.")
            return
        CLIP_LENGTHS[name] = self.len_var.get()
        self.config.setdefault("custom_lengths", {})[name] = CLIP_LENGTHS[name]
        self._save_config()
        menu = self.len_menu["menu"]
        menu.delete(0, "end")
        for k, v in CLIP_LENGTHS.items():
            menu.add_command(label=k, command=lambda v=v, k=k: (self.len_var.set(v), self._save_config()))
        self._set_status(f"Length saved: {name}")

    def _remove_length_preset(self):
        current = self.len_var.get()
        to_remove = None
        for k, v in CLIP_LENGTHS.items():
            if v == current and k not in BUILTIN_LENGTHS:
                to_remove = k
                break
        if not to_remove:
            messagebox.showinfo("Protected", "Cannot remove default lengths.")
            return
        if messagebox.askyesno("Remove", f"Delete length '{to_remove}'?"):
            del CLIP_LENGTHS[to_remove]
            self.config.get("custom_lengths", {}).pop(to_remove, None)
            self._save_config()
            menu = self.len_menu["menu"]
            menu.delete(0, "end")
            for k, v in CLIP_LENGTHS.items():
                menu.add_command(label=k, command=lambda v=v, k=k: (self.len_var.set(v), self._save_config()))
            self._set_status(f"Removed: {to_remove}")

    # ------------------------------------------------------------------
    # Render / Remixer
    # ------------------------------------------------------------------
    def _show_progress(self, show=True):
        if show:
            self.progress_bar.pack(side="right", padx=(10,0))
            self.progress_bar.set(0)
        else:
            self.progress_bar.pack_forget()

    def _update_progress(self, value):
        self.progress_bar.set(value)

    def _start_live_polling(self):
        pass

    def _poll_browse(self):
        pass

    def _stop_live_polling(self):
        pass

    def _job_running(self):
        if self._process and self._process.poll() is None:
            self._set_status("A job is already running — wait for it to finish.")
            return True
        return False

    def _job_finished(self, name, return_code):
        if return_code == 0:
            self.asset_ui.log(f"=== {name} finished successfully ===")
            self._set_status(f"✅ {name} complete.")
            self.browse_ui._refresh_browse()
        else:
            self.asset_ui.log(f"=== {name} exited with code {return_code} ===")
            self._set_status(f"⚠️ {name} failed (code {return_code})")

    def _run_script(self, script, args, name):
        """Run a helper script in the background and stream its output into the log panel."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._process = subprocess.Popen(
            [sys.executable, "-u", str(script), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creation_flags,
            cwd=str(self.BASE_DIR),
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        process = self._process

        def read_output():
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.asset_ui.log(line.rstrip())
                    else:
                        break
            except Exception as e:
                self.asset_ui.log(f"Log reader error: {e}")
            finally:
                if process.stdout:
                    process.stdout.close()
                return_code = process.wait()
                self.after(0, lambda: self._job_finished(name, return_code))

        threading.Thread(target=read_output, daemon=True).start()

    def _run_remixer(self):
        if self._job_running():
            return
        rp = self.BASE_DIR / "remixer.py"
        if not rp.exists():
            messagebox.showerror("Error", "remixer.py not found.")
            return

        self._save_proj()
        self.config["num_renders"] = self.asset_ui.render_count_var.get()
        self.config["caption_font"] = self.asset_ui.cap_font_var.get()
        self.config["captions"]["act_a"] = self.asset_ui.cap_a_var.get()
        self.config["captions"]["act_b"] = self.asset_ui.cap_b_var.get()
        self.config["settings"]["preview_mode"] = self.asset_ui.preview_var.get()
        fmt = self.fmt_var.get()
        if fmt == "Custom":
            pass
        elif fmt in FORMAT_PRESETS:
            p = FORMAT_PRESETS[fmt]
            self.config["settings"]["target_w"] = p["w"]
            self.config["settings"]["target_h"] = p["h"]
            self.config["settings"]["target_fps"] = p["fps"]
        self.config["settings"]["format"] = fmt
        self.config["settings"]["clip_length"] = self.len_var.get()
        self._save_config()

        self.asset_ui.clear_log()
        self.asset_ui.log("=== Starting remixer ===")
        self.asset_ui.log(f"Rendering {self.config['num_renders']} clips...")
        self.asset_ui.log(f"Format: {fmt}, Length: {self.config['settings']['clip_length']}s")

        try:
            self._run_script(rp, [], "Remixer")
            self._set_status(f"Remixer launched — {self.config['num_renders']} renders.")
        except Exception as e:
            self.asset_ui.log(f"ERROR: {e}")
            self._set_status("Remixer failed to start.")

    def _run_subtitles(self):
        if self._job_running():
            return
        sp = self.BASE_DIR / "subtitles.py"
        if not sp.exists():
            messagebox.showerror("Error", "subtitles.py not found.")
            return
        src = filedialog.askopenfilename(
            title="Choose a video or audio file to subtitle",
            filetypes=[("Video / Audio", "*.mp4 *.mov *.mkv *.avi *.webm *.mp3 *.wav *.m4a *.aac"), ("All files", "*.*")])
        if not src:
            return
        ui = self.asset_ui
        style = SUBTITLE_STYLES[ui.sub_style_var.get()]
        model = SUBTITLE_MODELS[ui.sub_model_var.get()]
        args = [src, "--style", style, "--model", model, "--font", ui.cap_font_var.get()]
        if ui.sub_srt_only_var.get():
            args.append("--srt-only")
        self.config["settings"]["subtitle_style"] = ui.sub_style_var.get()
        self.config["settings"]["subtitle_model"] = ui.sub_model_var.get()
        self._save_config()

        ui.clear_log()
        ui.log(f"=== Subtitles: {Path(src).name} ===")
        try:
            self._run_script(sp, args, "Subtitles")
            self._set_status(f"Subtitling {Path(src).name}...")
        except Exception as e:
            ui.log(f"ERROR: {e}")
            self._set_status("Subtitles failed to start.")

    # ------------------------------------------------------------------
    # Application close
    # ------------------------------------------------------------------
    def on_close(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._stop_live_polling()
        self._save_proj()
        self.destroy()

if __name__ == "__main__":
    app = FloodGate()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()