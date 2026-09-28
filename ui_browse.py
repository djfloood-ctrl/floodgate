"""
ui_browse.py – Browse tab UI and logic for FloodGate
"""

import os, shutil, subprocess, sys, threading, tkinter as tk, platform
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
from core import *

class BrowseUI:
    def __init__(self, app):
        self.app = app
        # shortcuts
        self.meta = app.meta
        self.upload = app.upload
        self.fonts = app.fonts
        self.config = app.config
        self.projects = app.projects
        self.browse_sort = app.browse_sort
        self.browse_tag = app.browse_tag
        self.browse_folder = app.browse_folder
        self.browse_search = app.browse_search
        self._star_labels = {}
        self._card_widgets = {}
        self._browse_loaded = False
        self.bframe = None
        self.flb = None
        self.tlb = None
        self.bcv = None
        # remember sort per folder
        self._folder_sort = {}

    def build_tab(self, parent):
        """Build the BROWSE tab inside the given parent."""
        tab = tk.Frame(parent, bg=BG_RED)
        self.tab = tab

        sidebar = tk.Frame(tab, bg=DARK_RED, width=160)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(True)
        tk.Label(sidebar, text="FOLDERS", font=self.fonts["subheading"], fg=WHITE, bg=DARK_RED).pack(pady=(10,4), padx=10)
        self.flb = tk.Listbox(sidebar, bg=DARK_RED, fg=WHITE, selectbackground=ACCENT, selectforeground=WHITE, font=self.fonts["body"], bd=0, height=8)
        self.flb.pack(fill="both", padx=6, pady=(0,4), expand=True)
        self.flb.bind("<<ListboxSelect>>", self._on_folder)
        tk.Button(sidebar, text="+ FOLDER", font=("Courier New",7,"bold"), fg=BLACK, bg=WHITE, activebackground=GRAY, bd=0, padx=8, pady=2, cursor="hand2", command=self._new_folder).pack(padx=6, pady=2)
        tk.Label(sidebar, text="TAGS", font=self.fonts["subheading"], fg=WHITE, bg=DARK_RED).pack(pady=(12,4), padx=10)
        self.tlb = tk.Listbox(sidebar, bg=DARK_RED, fg=WHITE, selectbackground=ACCENT, selectforeground=WHITE, font=self.fonts["body"], bd=0, height=6)
        self.tlb.pack(fill="both", padx=6, pady=(0,4), expand=True)
        self.tlb.bind("<<ListboxSelect>>", self._on_tag)

        ma = tk.Frame(tab, bg=BG_RED)
        ma.pack(side="left", fill="both", expand=True)
        ctr = tk.Frame(ma, bg=BG_RED)
        ctr.pack(fill="x", padx=12, pady=(8,4))
        tk.Label(ctr, text="BROWSE", font=self.fonts["title"], fg=WHITE, bg=BG_RED).pack(side="left")
        HoverButton(ctr, text="↻", font=self.fonts["button"], fg=BLACK, bg=WHITE, bd=0, padx=10, pady=3, cursor="hand2", command=self._refresh_browse).pack(side="right", padx=2)
        tk.Entry(ctr, textvariable=self.browse_search, font=self.fonts["body"], bg=DARK_RED, fg=WHITE, insertbackground=WHITE, bd=0, width=18, highlightthickness=1, highlightcolor=BORDER).pack(side="right", padx=2, ipady=2)
        sr = tk.Frame(ma, bg=BG_RED)
        sr.pack(fill="x", padx=12, pady=(0,4))
        for l, v in [("DATE ↓","date_desc"), ("★","favs_first"), ("NAME","name_asc")]:
            tk.Radiobutton(sr, text=l, variable=self.browse_sort, value=v, font=self.fonts["tiny"], fg=WHITE, bg=BG_RED, selectcolor=DARK_RED, activebackground=BG_RED, activeforeground=WHITE, bd=0, indicatoron=0, padx=4, pady=1, command=self._full_rebuild).pack(side="left")
        tk.Label(sr, text="SORT:", font=("Courier New",6,"bold"), fg=GRAY, bg=BG_RED).pack(side="left")

        self.bcv = ctk.CTkScrollableFrame(ma, fg_color=BG_RED)
        self.bcv.pack(side="left", fill="both", expand=True)
        self.bframe = self.bcv
        self._refresh_browse()
        return tab

    def _apply_filters(self):
        folder = self.browse_folder.get()
        tag = self.browse_tag.get()
        query = self.browse_search.get().lower()
        for vname, wdata in list(self._card_widgets.items()):
            card = wdata['frame']
            if not card.winfo_exists():
                continue
            show = True
            if folder == "favorites":
                show = self.meta.is_favorite(vname)
            elif folder == "trash":
                show = False
            elif folder not in ("all", "favorites"):
                show = (self.meta.get_folder(vname) == folder)
            if show and tag != "all":
                show = (tag in self.meta.get_tags(vname))
            if show and query:
                show = (query in vname.lower())
            if show:
                card.pack(side="left", padx=4, fill="x", expand=True)
                card.master.pack(fill="x", padx=8, pady=4)
            else:
                card.pack_forget()
        self._refresh_folders_tags()

    def _refresh_folders_tags(self):
        self.flb.delete(0, "end")
        for f in self.meta.get_all_folders():
            d = f"[TRASH] {f}" if f == "trash" else f"  {f}"
            self.flb.insert("end", d)
        cur = self.browse_folder.get()
        folds = self.meta.get_all_folders()
        if cur in folds:
            idx = folds.index(cur)
            self.flb.selection_clear(0, "end")
            self.flb.selection_set(idx)
            self.flb.see(idx)
        self.tlb.delete(0, "end")
        self.tlb.insert("end", "  all")
        for t in self.meta.get_all_tags():
            self.tlb.insert("end", f"  {t}")

    def _on_folder(self, event=None):
        sel = self.flb.curselection()
        if sel:
            ft = self.flb.get(sel[0]).strip()
            f = ft.replace("[TRASH]", "").strip()
            
            # Save current sort for the old folder before switching
            current_folder = self.browse_folder.get()
            if current_folder in self._folder_sort:
                self._folder_sort[current_folder] = self.browse_sort.get()
            
            self.browse_folder.set(f)
            self.browse_tag.set("all")
            
            # Apply saved sort for the new folder, or set a default
            if f in self._folder_sort:
                self.browse_sort.set(self._folder_sort[f])
            else:
                # Default: "favs_first" for favorites, "date_desc" for others
                if f == "favorites":
                    self.browse_sort.set("favs_first")
                else:
                    self.browse_sort.set("date_desc")
            
            # FULL REBUILD to apply new sort
            self._refresh_browse()

    def _on_tag(self, event=None):
        sel = self.tlb.curselection()
        if sel:
            self.browse_tag.set(self.tlb.get(sel[0]).strip())
            self._apply_filters()

    def _new_folder(self):
        n = simpledialog.askstring("New Folder", "Folder name:")
        if n and n.lower() != "trash":
            self.browse_folder.set(n)
            self._refresh_folders_tags()

    def _full_rebuild(self):
        # Save current sort for the current folder
        current_folder = self.browse_folder.get()
        self._folder_sort[current_folder] = self.browse_sort.get()
        self._refresh_browse()

    def _refresh_browse(self):
        self._star_labels.clear()
        self._card_widgets.clear()
        self._browse_loaded = True
        for w in self.bframe.winfo_children():
            w.destroy()
        folder = self.browse_folder.get()
        tag = self.browse_tag.get()
        output_dir = self.app.OUTPUT_DIR
        trash_dir = self.app.TRASH_DIR
        if folder == "trash":
            videos = list(trash_dir.glob("*.mp4"))
            tm = True
        else:
            videos = list(output_dir.glob("*.mp4"))
            tm = False
        if not tm and folder not in ("all","favorites"):
            videos = [v for v in videos if self.meta.get_folder(v.name) == folder]
        if folder == "favorites":
            videos = [v for v in videos if self.meta.is_favorite(v.name)]
        if tag and tag != "all":
            videos = [v for v in videos if tag in self.meta.get_tags(v.name)]
        q = self.browse_search.get().lower()
        if q:
            videos = [v for v in videos if q in v.stem.lower()]
        sort = self.browse_sort.get()
        if sort == "date_desc":
            videos.sort(key=lambda v: v.stat().st_mtime, reverse=True)
        elif sort == "favs_first":
            videos.sort(key=lambda v: not self.meta.is_favorite(v.name))
        elif sort == "name_asc":
            videos.sort(key=lambda v: v.stem.lower())
        if not videos:
            tk.Label(self.bframe, text="Trash is empty." if tm else "No clips.", font=("Courier New",9), fg=GRAY, bg=BG_RED).pack(expand=True, pady=40)
            self._apply_filters()
            return
        if tm:
            tb = tk.Frame(self.bframe, bg=BG_RED)
            tb.pack(fill="x", padx=12, pady=(4,6))
            HoverButton(tb, text="DELETE ALL FOREVER", font=("Courier New",8,"bold"), fg=WHITE, bg=TRASH_RED, bd=0, padx=12, pady=4, cursor="hand2", command=self._empty_trash).pack(side="left")

        rf = None
        for i, vid in enumerate(videos):
            if i % 4 == 0:
                rf = tk.Frame(self.bframe, bg=BG_RED)
                rf.pack(pady=4)

            is_fav = self.meta.is_favorite(vid.name)
            tl = self.meta.get_tags(vid.name)
            views = self.meta.get_views(vid.name)
            fn = self.meta.get_folder(vid.name)

            card = tk.Frame(rf, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER, width=180, height=210)

            def on_enter(e, c=card):
                c.config(highlightbackground=ACCENT, highlightthickness=2)
            def on_leave(e, c=card):
                c.config(highlightbackground=BORDER, highlightthickness=1)
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)

            card.pack(side="left", padx=4)
            card.pack_propagate(False)
            card.video_name = vid.name
            card_data = {'frame': card}

            tr = tk.Frame(card, bg=CARD_BG)
            tr.pack(fill="x", padx=8, pady=(8,0))
            sc = "★" if is_fav else "☆"
            sco = STAR_GOLD if is_fav else GRAY
            sl = tk.Label(tr, text=sc, font=("Helvetica Neue",12), fg=sco, bg=CARD_BG, cursor="hand2")
            sl.pack(side="left")
            sl.bind("<Button-1>", lambda e, v=vid: self._toggle_fav(v))
            self._star_labels[vid.name] = sl
            card_data['star'] = sl
            db = tk.Label(tr, text="✖", font=("Helvetica Neue",12,"bold"), fg=TRASH_RED, bg=CARD_BG, cursor="hand2")
            db.pack(side="right")
            if tm:
                db.bind("<Button-1>", lambda e, v=vid: self._delete_forever_confirm(v))
            else:
                db.bind("<Button-1>", lambda e, v=vid: self._move_trash_instant(v))

            nm = vid.stem[:18] + ("..." if len(vid.stem) > 18 else "")
            tk.Label(card, text=nm, font=("Courier New",8,"bold"), fg=WHITE, bg=CARD_BG, wraplength=140).pack(pady=(4,1))
            dt = datetime.fromtimestamp(vid.stat().st_mtime).strftime("%m/%d/%y %H:%M")
            tk.Label(card, text=dt, font=self.fonts["small"], fg=GRAY, bg=CARD_BG).pack()
            tk.Label(card, text=f"{human_size(vid.stat().st_size)}  •  {views} views", font=self.fonts["small"], fg=GRAY, bg=CARD_BG).pack()

            if fn and fn != "all" and not tm:
                flbl = tk.Label(card, text=f"[{fn}]", font=self.fonts["small"], fg=ACCENT, bg=CARD_BG)
                flbl.pack()
                card_data['folder'] = flbl
            if tl and not tm:
                tr2 = tk.Frame(card, bg=CARD_BG)
                tr2.pack(pady=(4,2))
                card_data['tags'] = tr2
                for t in tl[:3]:
                    ci = hash(t) % len(TAG_COLORS)
                    TagChip(tr2, t, TAG_COLORS[ci], on_remove=lambda tag, v=vid: self._remove_tag(v, tag)).pack(side="left", padx=1)

            br2 = tk.Frame(card, bg=CARD_BG)
            br2.pack(pady=(6,10))
            self._card_widgets[vid.name] = card_data
            if not tm:
                HoverButton(br2, text="VIEW", font=("Courier New",7,"bold"), fg=BLACK, bg=WHITE, bd=0, padx=8, pady=2, command=lambda p=vid: self._view(p)).pack(side="left", padx=2)
                HoverButton(br2, text="TAG", font=("Courier New",7,"bold"), fg=BLACK, bg=UPLOAD_BLUE, bd=0, padx=8, pady=2, command=lambda p=vid: self._tag(p)).pack(side="left", padx=2)
                HoverButton(br2, text="MOVE", font=("Courier New",7,"bold"), fg=BLACK, bg=ACCENT, bd=0, padx=8, pady=2, command=lambda p=vid: self._move(p)).pack(side="left", padx=2)
                HoverButton(br2, text="↑", font=("Courier New",7,"bold"), fg=BLACK, bg=UPLOAD_GREEN, bd=0, padx=8, pady=2, command=lambda p=vid: self._queue_up(p)).pack(side="left", padx=2)
            else:
                HoverButton(br2, text="RESTORE", font=("Courier New",7,"bold"), fg=BLACK, bg=UPLOAD_GREEN, bd=0, padx=8, pady=2, command=lambda p=vid: self._restore(p)).pack(side="left", padx=2)
                HoverButton(br2, text="DELETE", font=("Courier New",7,"bold"), fg=WHITE, bg=TRASH_RED, bd=0, padx=8, pady=2, command=lambda p=vid: self._delete_forever(p)).pack(side="left", padx=2)
        self._apply_filters()

    def _move_trash_instant(self, vp):
        trash_dir = self.app.TRASH_DIR
        trash_dir.mkdir(parents=True, exist_ok=True)
        d = trash_dir / vp.name
        if vp.exists():
            shutil.move(str(vp), str(d))
        self.meta.set_folder(vp.name, "trash")
        self._refresh_browse()

    def _restore(self, vp):
        output_dir = self.app.OUTPUT_DIR
        d = output_dir / vp.name
        if vp.exists():
            shutil.move(str(vp), str(d))
        self.meta.set_folder(vp.name, "all")
        self._refresh_browse()

    def _delete_forever(self, vp):
        if messagebox.askyesno("Delete Forever", f"Permanently delete {vp.name}?"):
            if vp.exists():
                vp.unlink()
            if vp.name in self.meta.data:
                del self.meta.data[vp.name]
                self.meta._save()
            self._refresh_browse()

    def _delete_forever_confirm(self, vp):
        if messagebox.askyesno("Delete Forever", f"Permanently delete {vp.name}?\nThis cannot be undone."):
            self._delete_forever(vp)

    def _empty_trash(self):
        trash_dir = self.app.TRASH_DIR
        if messagebox.askyesno("Empty Trash", "Delete ALL trash forever?"):
            for v in trash_dir.glob("*.mp4"):
                v.unlink()
                if v.name in self.meta.data:
                    del self.meta.data[v.name]
            self.meta._save()
            self._refresh_browse()

    def _toggle_fav(self, vp):
        self.meta.toggle_favorite(vp.name)
        is_fav = self.meta.is_favorite(vp.name)
        if vp.name in self._star_labels:
            lbl = self._star_labels[vp.name]
            if lbl.winfo_exists():
                lbl.config(text="★" if is_fav else "☆", fg=STAR_GOLD if is_fav else GRAY)
        self._apply_filters()

    def _view(self, vp):
        self.meta.increment_views(vp.name)
        open_path(vp)
        self._apply_filters()

    def _tag(self, vp):
        ex = ", ".join(self.meta.get_all_tags())
        tag = simpledialog.askstring("Add Tag", f"Tag for {vp.name}:\nExisting: {ex}")
        if tag:
            self.meta.add_tag(vp.name, tag.strip())
            self._update_tags_inplace(vp)

    def _remove_tag(self, vp, tag):
        self.meta.remove_tag(vp.name, tag)
        if vp.name in self._card_widgets and 'tags' in self._card_widgets[vp.name]:
            tf = self._card_widgets[vp.name]['tags']
            for w in tf.winfo_children():
                w.destroy()
            for t in self.meta.get_tags(vp.name)[:3]:
                ci = hash(t) % len(TAG_COLORS)
                TagChip(tf, t, TAG_COLORS[ci], on_remove=lambda tag, v=vp: self._remove_tag(v, tag)).pack(side="left", padx=1)
        self._refresh_folders_tags()

    def _move(self, vp):
        folds = ", ".join([f for f in self.meta.get_all_folders() if f not in ["trash","favorites"]])
        f = simpledialog.askstring("Move", f"Folder for {vp.name}:\nExisting: {folds}")
        if f:
            self.meta.set_folder(vp.name, f.strip())
            self._update_folder_inplace(vp, f.strip())

    def _queue_up(self, vp):
        cap = simpledialog.askstring("Upload queue", f"Caption for {vp.name}\n(text, hashtags, @mentions):")
        if cap is None:
            return
        self.upload.queue(str(vp), cap)
        self.app._refresh_upload()
        self.app._set_status(f"Queued {vp.name} — export it from the Upload tab.")

    def _update_tags_inplace(self, vp):
        if vp.name in self._card_widgets and 'tags' in self._card_widgets[vp.name]:
            tf = self._card_widgets[vp.name]['tags']
            for w in tf.winfo_children():
                w.destroy()
            for t in self.meta.get_tags(vp.name)[:3]:
                ci = hash(t) % len(TAG_COLORS)
                TagChip(tf, t, TAG_COLORS[ci], on_remove=lambda tag, v=vp: self._remove_tag(v, tag)).pack(side="left", padx=1)
        self._refresh_folders_tags()

    def _update_folder_inplace(self, vp, folder):
        if vp.name in self._card_widgets and 'folder' in self._card_widgets[vp.name]:
            flbl = self._card_widgets[vp.name]['folder']
            flbl.config(text=f"[{folder}]")

    def refresh_browse(self):
        self._refresh_browse()