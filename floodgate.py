"""
FLOODGATE v2.2 — Working Build
Uniform browse cards. Scrolling. Favorites. Tags. Trash. Upload. Projects.
"""

import json, os, shutil, subprocess, sys, threading, tkinter as tk, platform
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "config.json"
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUT_DIR = BASE_DIR / "output"
TRASH_DIR = BASE_DIR / "trash"
META_PATH = BASE_DIR / "clip_meta.json"
LOGO_PATH = BASE_DIR / "floodgate_icon.png"

BG_RED = "#8B1A1A"
CARD_BG = "#A52222"
DARK_RED = "#6B1010"
BORDER = "#C84040"
WHITE = "#F0E8E0"
BLACK = "#1A1A1A"
ACCENT = "#FF4444"
GRAY = "#C8B0B0"
STAR_GOLD = "#F1C40F"
TAB_ACTIVE = "#FFFFFF"
TAB_INACTIVE = "#C8B0B0"
UPLOAD_GREEN = "#2ECC71"
UPLOAD_BLUE = "#3498DB"
TRASH_RED = "#E74C3C"
TAG_COLORS = ["#E74C3C","#3498DB","#2ECC71","#9B59B6","#F39C12","#1ABC9C"]

FORMAT_PRESETS = {
    "Reel / TikTok (9:16)":  {"w":1080,"h":1920,"fps":30},
    "Square Post (1:1)":     {"w":1080,"h":1080,"fps":30},
    "Widescreen (16:9)":     {"w":1920,"h":1080,"fps":30},
    "Cinematic (21:9)":      {"w":2560,"h":1080,"fps":24},
}

CLIP_LENGTHS = {"15s":15,"30s":30,"60s":60,"90s":90,"3min":180,"5min":300}

SLOTS = {
    "act_a_videos": {"label":"Act A — Sad / Bleak Clips","subfolder":"assets/act_a","types":[("Video","*.mp4 *.mov *.avi *.mkv")],"hint":"Sad, bleak, melancholic, rainy day footage","side":"left"},
    "act_b_videos": {"label":"Act B — Heat / Energy Clips","subfolder":"assets/act_b","types":[("Video","*.mp4 *.mov *.avi *.mkv")],"hint":"Hype, energy, heat, crowds, lights, action","side":"right"},
    "act_a_music": {"label":"Act A — Sad Music","subfolder":"assets/music/sad","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"Sad instrumentals, ambient sounds, quiet tracks","side":"left"},
    "act_b_music": {"label":"Act B — Bangers","subfolder":"assets/music/heat","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"Your tracks, beats, remixes, produced music","side":"right"},
    "voiceover_clips": {"label":"Voiceover — AI Clips","subfolder":"assets/voiceovers","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"AI-generated voice clips for your videos","side":"center"},
}
LOGO_SLOT = {"label":"Logo — Final Frame","subfolder":"assets/logo","types":[("Image","*.png *.jpg *.jpeg")],"hint":"Your brand logo with transparent background","side":"center"}

def load_json(p, d=None):
    if Path(p).exists():
        with open(p,"r") as f: return json.load(f)
    return d if d is not None else {}
def save_json(p, data):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with open(p,"w") as f: json.dump(data,f,indent=2)
def human_size(b):
    for u in ["B","KB","MB","GB","TB"]:
        if b<1024: return f"{b:.1f} {u}"
        b/=1024
    return f"{b:.1f} PB"

def scan_fonts():
    fonts=set(); s=platform.system()
    if s=="Windows":
        fd=Path(os.environ.get("WINDIR","C:\\Windows"))/"Fonts"
        if fd.exists():
            for f in fd.glob("*.ttf"): fonts.add(f.stem)
            for f in fd.glob("*.otf"): fonts.add(f.stem)
    fonts.update(["Impact","Arial","Arial Black","Helvetica","Futura","Georgia","Times New Roman","Verdana","Courier New","Bahnschrift","Calibri","Segoe UI","Tahoma","Consolas"])
    return sorted(fonts)

def valid_fonts(all_fonts):
    t=tk.Tk();t.withdraw();l=tk.Label(t);v=[]
    for f in all_fonts:
        try:l.config(font=(f,10));v.append(f)
        except:pass
    t.destroy()
    return sorted(v) if v else ["Arial","Courier New","Impact"]

class ClipMeta:
    def __init__(self,p): self.path=p; self.data=load_json(p,{}); self._migrate()
    def _migrate(self):
        ch=False
        for v in OUTPUT_DIR.glob("*.mp4"):
            if v.name not in self.data: self.data[v.name]={"fav":False,"tags":[],"views":0,"folder":"all"};ch=True
        TRASH_DIR.mkdir(parents=True,exist_ok=True)
        for v in TRASH_DIR.glob("*.mp4"):
            if v.name not in self.data: self.data[v.name]={"fav":False,"tags":[],"views":0,"folder":"trash"};ch=True
        if ch:self._save()
    def _save(self): save_json(self.path,self.data)
    def toggle_favorite(self,fn):
        if fn not in self.data or "fav" not in self.data[fn]:
            self.data[fn]={"fav":False,"tags":[],"views":0,"folder":"all"}
        self.data[fn]["fav"]=not self.data[fn].get("fav",False);self._save()
    def is_favorite(self,fn): return self.data.get(fn,{}).get("fav",False)
    def add_tag(self,fn,tag):
        tag=tag.strip()
        if not tag: return
        if fn not in self.data: self.data[fn]={"fav":False,"tags":[],"views":0,"folder":"all"}
        if tag not in self.data[fn]["tags"]: self.data[fn]["tags"].append(tag);self._save()
    def remove_tag(self,fn,tag):
        if fn in self.data and tag in self.data[fn]["tags"]: self.data[fn]["tags"].remove(tag);self._save()
    def get_tags(self,fn): return self.data.get(fn,{}).get("tags",[])
    def increment_views(self,fn):
        if fn not in self.data: self.data[fn]={"fav":False,"tags":[],"views":0,"folder":"all"}
        self.data[fn]["views"]=self.data[fn].get("views",0)+1;self._save()
    def get_views(self,fn): return self.data.get(fn,{}).get("views",0)
    def set_folder(self,fn,folder):
        if fn not in self.data: self.data[fn]={"fav":False,"tags":[],"views":0,"folder":"all"}
        self.data[fn]["folder"]=folder;self._save()
    def get_folder(self,fn): return self.data.get(fn,{}).get("folder","all")
    def get_all_tags(self):
        tags=set()
        for v in self.data.values():
            for t in v.get("tags",[]): tags.add(t)
        return sorted(tags)
    def get_all_folders(self):
        folders={"all","favorites","trash"}
        for v in self.data.values(): folders.add(v.get("folder","all"))
        return sorted(folders)

class HoverButton(tk.Button):
    def __init__(self,p,hover_bg=WHITE,hover_fg=BLACK,**kw):
        self.db=kw.get("bg",DARK_RED);self.df=kw.get("fg",WHITE);self.hb=hover_bg;self.hf=hover_fg
        super().__init__(p,**kw)
        self.bind("<Enter>",lambda e:self.config(bg=self.hb,fg=self.hf))
        self.bind("<Leave>",lambda e:self.config(bg=self.db,fg=self.df))

class TagChip(tk.Frame):
    def __init__(self,p,text,color,on_remove=None,**kw):
        super().__init__(p,bg=color,**kw)
        fm={"#E74C3C":WHITE,"#3498DB":WHITE,"#2ECC71":BLACK,"#9B59B6":WHITE,"#F39C12":BLACK,"#1ABC9C":BLACK}
        fg=fm.get(color,WHITE)
        tk.Label(self,text=text,font=("Courier New",7,"bold"),fg=fg,bg=color,padx=5,pady=1).pack(side="left")
        if on_remove:
            x=tk.Label(self,text=" x",font=("Courier New",7,"bold"),fg=fg,bg=color,cursor="hand2",padx=2)
            x.pack(side="left");x.bind("<Button-1>",lambda e:on_remove(text))

class ProjectManager:
    def __init__(self):
        PROJECTS_DIR.mkdir(parents=True,exist_ok=True);self.projects=self._load()
        if "Default" not in self.projects: self._mkdefault()
        self.current="Default"
    def _mkdefault(self):
        save_json(PROJECTS_DIR/"Default"/"project.json",{"name":"Default","assets":{"act_a_videos":[],"act_b_videos":[],"act_a_music":[],"act_b_music":[],"voiceover_clips":[],"logo":""},"captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"},"settings":{"preview_mode":True,"music_volume":0.35,"caption_font":"Impact","num_renders":10,"format":"Reel / TikTok (9:16)","clip_length":30}})
        self.projects["Default"]=load_json(PROJECTS_DIR/"Default"/"project.json")
    def _load(self):
        p={}
        for d in PROJECTS_DIR.iterdir():
            if d.is_dir() and (d/"project.json").exists(): p[d.name]=load_json(d/"project.json")
        return p
    def create(self,name):
        if name in self.projects: return False
        data={"name":name,"assets":{"act_a_videos":[],"act_b_videos":[],"act_a_music":[],"act_b_music":[],"voiceover_clips":[],"logo":""},"captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"},"settings":{"preview_mode":True,"music_volume":0.35,"caption_font":"Impact","num_renders":10,"format":"Reel / TikTok (9:16)","clip_length":30}}
        save_json(PROJECTS_DIR/name/"project.json",data);self.projects[name]=data;return True
    def list_names(self): return sorted(self.projects.keys())
    def get(self,name): return self.projects.get(name)
    def save(self,name,data): self.projects[name]=data;save_json(PROJECTS_DIR/name/"project.json",data)

class UploadManager:
    def __init__(self): self.drafts=[];self.paired_ig=False;self.paired_tt=False
    def queue(self,vp,caption,platforms): self.drafts.append({"video":vp,"caption":caption,"platforms":platforms,"status":"queued"})
    def get(self): return self.drafts
    def remove(self,i):
        if 0<=i<len(self.drafts): self.drafts.pop(i)

class FloodGate(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("FLOODGATE")
        self.configure(fg_color=BG_RED)
        self.geometry("960x680")
        self.minsize(800,600)

        self.config=self._load_config()
        self.projects=ProjectManager()
        self.meta=ClipMeta(META_PATH)
        self.upload=UploadManager()
        self.fonts_all=scan_fonts()
        self.fonts_ok=valid_fonts(self.fonts_all)
        self.listboxes={}
        self._busy=False
        self._logo_img=None

        self.browse_sort=tk.StringVar(value="date_desc")
        self.browse_tag=tk.StringVar(value="all")
        self.browse_folder=tk.StringVar(value="all")
        self.browse_search=tk.StringVar(value="")
        self.browse_search.trace_add("write", lambda *a: self._filter_search())
        self.fmt_var=tk.StringVar(value=self.config.get("settings",{}).get("format","Reel / TikTok (9:16)"))
        self.len_var=tk.IntVar(value=self.config.get("settings",{}).get("clip_length",30))

        OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
        TRASH_DIR.mkdir(parents=True,exist_ok=True)
        for s in SLOTS.values(): (BASE_DIR/s["subfolder"]).mkdir(parents=True,exist_ok=True)
        (BASE_DIR/LOGO_SLOT["subfolder"]).mkdir(parents=True,exist_ok=True)

        self.bind("<F11>",lambda e:self.attributes("-fullscreen",not self.attributes("-fullscreen")))
        self.bind_all("<MouseWheel>", self._global_scroll)

        self._live_polling = False
        self._last_browse_state = None
        self._star_labels = {}
        self._card_widgets = {}  # video_name -> {star, tags_frame, folder_label, card_frame}
        self._build_ui()
        self.bind("<Control-r>",lambda e:self._run_remixer())
        self.bind("<Control-R>",lambda e:self._run_remixer())
        self._refresh_all()
        self._refresh_project_menu()

    def _load_config(self):
        c=load_json(CONFIG_PATH,{"act_a_videos":[],"act_b_videos":[],"act_a_music":[],"act_b_music":[],"voiceover_clips":[],"logo":"","num_renders":10,"caption_font":"Impact","captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"},"settings":{"preview_mode":True,"music_volume":0.35,"format":"Reel / TikTok (9:16)","clip_length":30}})
        if "caption_font" not in c: c["caption_font"]="Impact"
        return c
    def _save_config(self): save_json(CONFIG_PATH,self.config)
    def _set_status(self,msg): self.after(0,lambda:self.status_var.set(msg))

    def _global_scroll(self, event):
        # Momentum scroll: tracks speed between events for fluid acceleration
        now = event.time
        delta = event.delta
        
        # Calculate scroll velocity (higher = user is scrolling faster)
        if not hasattr(self, '_last_scroll_time'):
            self._last_scroll_time = now
            self._scroll_momentum = 0
        
        time_diff = max(now - self._last_scroll_time, 1)
        self._last_scroll_time = now
        
        # Base speed: 2x faster than before
        base = abs(delta) / 15
        
        # Build momentum on consecutive fast scrolls
        if time_diff < 80:
            self._scroll_momentum = min(self._scroll_momentum + 0.5, 4.0)
        else:
            self._scroll_momentum = max(self._scroll_momentum - 0.3, 1.0)
        
        speed = base * self._scroll_momentum
        direction = -1 if delta > 0 else 1
        amount = int(direction * speed)
        
        if isinstance(event.widget, tk.Listbox):
            event.widget.yview_scroll(amount, "units")
            return "break"
        if hasattr(self, 'bcv') and self.bcv.winfo_ismapped():
            self.bcv._parent_canvas.yview_scroll(amount, "units")
        elif hasattr(self, 'tabs') and 'ASSETS' in self.tabs:
            sf = self.tabs['ASSETS'].winfo_children()[0]
            if hasattr(sf, '_parent_canvas'):
                sf._parent_canvas.yview_scroll(amount, "units")

    def _build_ui(self):
        tb=tk.Frame(self,bg=DARK_RED,height=40);tb.pack(fill="x");tb.pack_propagate(False)
        try:
            if LOGO_PATH.exists():
                img=tk.PhotoImage(file=str(LOGO_PATH)).subsample(4,4)
                tk.Label(tb,image=img,bg=DARK_RED).pack(side="left",padx=(12,4),pady=2);self._logo_img=img
        except: pass
        tk.Label(tb,text="FLOODGATE",font=("Helvetica Neue",14,"bold"),fg=WHITE,bg=DARK_RED).pack(side="left",pady=6)
        self.proj_var=tk.StringVar(value="Default")
        self.proj_menu=tk.OptionMenu(tb,self.proj_var,"Default",command=self._on_project)
        self.proj_menu.config(font=("Courier New",7),bg=DARK_RED,fg=WHITE,activebackground=CARD_BG,bd=0,highlightthickness=1,highlightcolor=BORDER)
        self.proj_menu["menu"].config(font=("Courier New",8),bg=CARD_BG,fg=WHITE,activebackground=DARK_RED,bd=0)
        self.proj_menu.pack(side="left",padx=6)
        tk.Button(tb,text="+",font=("Courier New",8,"bold"),fg=BLACK,bg=WHITE,activebackground=GRAY,bd=0,padx=8,pady=1,cursor="hand2",command=self._new_project).pack(side="left",padx=2)
        self.tab_btns={}
        for name,icon in [("ASSETS","⬡"),("BROWSE","▹"),("UPLOAD","↑")]:
            btn=tk.Button(tb,text=f" {icon} {name} ",font=("Courier New",9,"bold"),fg=TAB_INACTIVE,bg=DARK_RED,activebackground=DARK_RED,activeforeground=WHITE,bd=0,cursor="hand2",relief="flat",command=lambda n=name:self.show_tab(n))
            btn.pack(side="left",ipady=8);self.tab_btns[name]=btn
        self.content=tk.Frame(self,bg=BG_RED);self.content.pack(fill="both",expand=True)
        self.tabs={}
        self._build_assets();self._build_browse();self._build_upload()
        self.show_tab("ASSETS")
        self.status_var=tk.StringVar(value="Ready  •  Ctrl+R  •  F11")
        tk.Label(self,textvariable=self.status_var,font=("Courier New",7),fg=GRAY,bg=DARK_RED,anchor="w").pack(fill="x",padx=12,pady=4)

    def show_tab(self,name):
        for n,f in self.tabs.items(): f.pack_forget()
        if name in self.tabs: self.tabs[name].pack(fill="both",expand=True)
        for n,b in self.tab_btns.items(): b.config(fg=TAB_ACTIVE if n==name else TAB_INACTIVE)
        if name=="BROWSE" and not hasattr(self, '_browse_loaded'):
            self._refresh_browse()  # first load only

    def _build_assets(self):
        tab=tk.Frame(self.content,bg=BG_RED);self.tabs["ASSETS"]=tab
        sf=ctk.CTkScrollableFrame(tab,fg_color=BG_RED)
        sf.pack(side="left",fill="both",expand=True)


        fb=tk.Frame(sf,bg=DARK_RED,height=34);fb.pack(fill="x",padx=14,pady=(6,4));fb.pack_propagate(False)
        tk.Label(fb,text="FORMAT:",font=("Courier New",8,"bold"),fg=GRAY,bg=DARK_RED).pack(side="left",padx=(10,4))
        fm=tk.OptionMenu(fb,self.fmt_var,*FORMAT_PRESETS.keys(),command=lambda c:[self.fmt_var.set(c),self._save_config()])
        fm.config(font=("Courier New",8),bg=DARK_RED,fg=WHITE,activebackground=CARD_BG,bd=0,highlightthickness=0)
        fm["menu"].config(font=("Courier New",8),bg=CARD_BG,fg=WHITE,bd=0);fm.pack(side="left",padx=2)
        tk.Label(fb,text="LENGTH:",font=("Courier New",8,"bold"),fg=GRAY,bg=DARK_RED).pack(side="left",padx=(14,4))
        lm=tk.OptionMenu(fb,self.len_var,30,*CLIP_LENGTHS.values(),command=lambda c:[self.len_var.set(int(c)),self._save_config()])
        lm.config(font=("Courier New",8),bg=DARK_RED,fg=WHITE,activebackground=CARD_BG,bd=0,highlightthickness=0)
        lm["menu"].config(font=("Courier New",8),bg=CARD_BG,fg=WHITE,bd=0);lm.pack(side="left",padx=2)

        af=tk.Frame(sf,bg=BG_RED);af.pack(fill="x",padx=60,pady=(4,0))
        af.columnconfigure(0,weight=1);af.columnconfigure(1,weight=1)
        lc=tk.Frame(af,bg=BG_RED);lc.grid(row=0,column=0,sticky="nsew",padx=(0,3))
        rc=tk.Frame(af,bg=BG_RED);rc.grid(row=0,column=1,sticky="nsew",padx=(3,0))
        for key in ["act_a_videos","act_a_music","act_b_videos","act_b_music"]:
            m=SLOTS[key]
            if m["side"]=="left": self._slot(lc,key,m)
            else: self._slot(rc,key,m)
        ct=tk.Frame(sf,bg=BG_RED);ct.pack(fill="x",padx=80,pady=(4,0))
        self._slot(ct,"voiceover_clips",SLOTS["voiceover_clips"])
        self._logo_card(ct);self._settings_card(ct);self._render_card(ct)
        note=tk.Frame(ct,bg=DARK_RED,highlightthickness=1,highlightbackground=BORDER)
        note.pack(fill="x",pady=(6,0))
        tk.Label(note,text="◈  RENDER OUTPUT → EXTERNAL TERMINAL",font=("Courier New",7,"bold"),fg=WHITE,bg=DARK_RED).pack(pady=8)
        tk.Label(ct,text="Ready  •  Ctrl+R  •  F11",font=("Courier New",7),fg=GRAY,bg=BG_RED).pack(pady=(6,20))

    def _build_browse(self):
        tab=tk.Frame(self.content,bg=BG_RED);self.tabs["BROWSE"]=tab
        sidebar=tk.Frame(tab,bg=DARK_RED,width=160);sidebar.pack(side="left",fill="y");sidebar.pack_propagate(True)
        tk.Label(sidebar,text="FOLDERS",font=("Helvetica Neue",9,"bold"),fg=WHITE,bg=DARK_RED).pack(pady=(10,4),padx=10)
        self.flb=tk.Listbox(sidebar,bg=DARK_RED,fg=WHITE,selectbackground=ACCENT,selectforeground=WHITE,font=("Courier New",8),bd=0,height=8)
        self.flb.pack(fill="both",padx=6,pady=(0,4),expand=True);self.flb.bind("<<ListboxSelect>>",self._on_folder)
        tk.Button(sidebar,text="+ FOLDER",font=("Courier New",7,"bold"),fg=BLACK,bg=WHITE,activebackground=GRAY,bd=0,padx=8,pady=2,cursor="hand2",command=self._new_folder).pack(padx=6,pady=2)
        tk.Label(sidebar,text="TAGS",font=("Helvetica Neue",9,"bold"),fg=WHITE,bg=DARK_RED).pack(pady=(12,4),padx=10)
        self.tlb=tk.Listbox(sidebar,bg=DARK_RED,fg=WHITE,selectbackground=ACCENT,selectforeground=WHITE,font=("Courier New",8),bd=0,height=6)
        self.tlb.pack(fill="both",padx=6,pady=(0,4),expand=True);self.tlb.bind("<<ListboxSelect>>",self._on_tag)

        ma=tk.Frame(tab,bg=BG_RED);ma.pack(side="left",fill="both",expand=True)
        ctr=tk.Frame(ma,bg=BG_RED);ctr.pack(fill="x",padx=12,pady=(8,4))
        tk.Label(ctr,text="BROWSE",font=("Helvetica Neue",14,"bold"),fg=WHITE,bg=BG_RED).pack(side="left")
        HoverButton(ctr,text="↻",font=("Courier New",9,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=10,pady=3,cursor="hand2",command=lambda:self._refresh_browse()).pack(side="right",padx=2)  # MANUAL REFRESH ONLY
        tk.Entry(ctr,textvariable=self.browse_search,font=("Courier New",8),bg=DARK_RED,fg=WHITE,insertbackground=WHITE,bd=0,width=18,highlightthickness=1,highlightcolor=BORDER).pack(side="right",padx=2,ipady=2)
        sr=tk.Frame(ma,bg=BG_RED);sr.pack(fill="x",padx=12,pady=(0,4))
        for l,v in [("DATE ↓","date_desc"),("★","favs_first"),("NAME","name_asc")]:
            tk.Radiobutton(sr,text=l,variable=self.browse_sort,value=v,font=("Courier New",6),fg=WHITE,bg=BG_RED,selectcolor=DARK_RED,activebackground=BG_RED,activeforeground=WHITE,bd=0,indicatoron=0,padx=4,pady=1,command=lambda:self._full_rebuild()).pack(side="left")
        tk.Label(sr,text="SORT:",font=("Courier New",6,"bold"),fg=GRAY,bg=BG_RED).pack(side="left")

        self.bcv=ctk.CTkScrollableFrame(ma,fg_color=BG_RED)
        self.bcv.pack(side="left",fill="both",expand=True)
        self.bframe=self.bcv

        self._refresh_browse()  # initial load

    def _filter_search(self):
        q = self.browse_search.get().lower()
        for vname, wdata in list(self._card_widgets.items()):
            card = wdata['frame']
            if not card.winfo_exists(): continue
            if not q or q in vname.lower():
                card.pack(side="left",padx=4,fill="x",expand=True)
                card.master.pack(fill="x",padx=8,pady=4)
            else:
                card.pack_forget()

    def _refresh_folders_tags(self):
        self.flb.delete(0,"end")
        for f in self.meta.get_all_folders():
            d=f"[TRASH] {f}" if f=="trash" else f"  {f}";self.flb.insert("end",d)
        cur=self.browse_folder.get();folds=self.meta.get_all_folders()
        if cur in folds:
            idx=folds.index(cur);self.flb.selection_clear(0,"end");self.flb.selection_set(idx);self.flb.see(idx)
        self.tlb.delete(0,"end");self.tlb.insert("end","  all")
        for t in self.meta.get_all_tags(): self.tlb.insert("end",f"  {t}")

    def _on_folder(self,event=None):
        sel=self.flb.curselection()
        if sel:
            ft=self.flb.get(sel[0]).strip();f=ft.replace("[TRASH]","").strip()
            self.browse_folder.set(f);self.browse_tag.set("all")
            # Filter cards in-place instead of rebuilding
            folder = self.browse_folder.get()
            for vname, wdata in list(self._card_widgets.items()):
                card = wdata['frame']
                if not card.winfo_exists(): continue
                if folder == "all":
                    card.pack(side="left",padx=4,fill="x",expand=True)
                    card.master.pack(fill="x",padx=8,pady=4)
                elif folder == "favorites":
                    if self.meta.is_favorite(vname):
                        card.pack(side="left",padx=4,fill="x",expand=True)
                        card.master.pack(fill="x",padx=8,pady=4)
                    else:
                        card.pack_forget()
                elif folder == "trash":
                    card.pack_forget()
                elif self.meta.get_folder(vname) == folder:
                    card.pack(side="left",padx=4,fill="x",expand=True)
                    card.master.pack(fill="x",padx=8,pady=4)
                else:
                    card.pack_forget()
            self._refresh_folders_tags()

    def _on_tag(self,event=None):
        sel=self.tlb.curselection()
        if sel:
            self.browse_tag.set(self.tlb.get(sel[0]).strip())
            tag = self.browse_tag.get()
            for vname, wdata in list(self._card_widgets.items()):
                card = wdata['frame']
                if not card.winfo_exists(): continue
                if tag == "all" or tag in self.meta.get_tags(vname):
                    card.pack(side="left",padx=4,fill="x",expand=True)
                    card.master.pack(fill="x",padx=8,pady=4)
                else:
                    card.pack_forget()
            self._refresh_folders_tags()

    def _new_folder(self):
        n=simpledialog.askstring("New Folder","Folder name:")
        if n and n.lower()!="trash": self.browse_folder.set(n);self._refresh_folders_tags()

    def _full_rebuild(self):
        self._refresh_browse()

    def _filter_folder(self):
        folder = self.browse_folder.get()
        tag = self.browse_tag.get()
        for vname, wdata in list(self._card_widgets.items()):
            card = wdata['frame']
            if not card.winfo_exists(): continue
            show = True
            if folder == "favorites" and not self.meta.is_favorite(vname): show = False
            elif folder == "trash": show = False
            elif folder not in ("all","favorites") and self.meta.get_folder(vname) != folder: show = False
            if tag != "all" and tag not in self.meta.get_tags(vname): show = False
            if show:
                card.pack(side="left",padx=4,fill="x",expand=True)
                card.master.pack(fill="x",padx=8,pady=4)
            else:
                card.pack_forget()
        self._refresh_folders_tags()

    def _update_tags_inplace(self, vp):
        if vp.name in self._card_widgets and 'tags' in self._card_widgets[vp.name]:
            tf = self._card_widgets[vp.name]['tags']
            for w in tf.winfo_children(): w.destroy()
            for t in self.meta.get_tags(vp.name)[:3]:
                ci=hash(t)%len(TAG_COLORS)
                TagChip(tf,t,TAG_COLORS[ci],on_remove=lambda tag,v=vp:self._remove_tag(v,tag)).pack(side="left",padx=1)
        self._refresh_folders_tags()

    def _update_folder_inplace(self, vp, folder):
        if vp.name in self._card_widgets and 'folder' in self._card_widgets[vp.name]:
            flbl = self._card_widgets[vp.name]['folder']
            flbl.config(text=f"[{folder}]")

    def _refresh_browse(self):
        self._star_labels.clear()
        self._card_widgets.clear()
        self._browse_loaded = True
        for w in self.bframe.winfo_children(): w.destroy()
        folder=self.browse_folder.get();tag=self.browse_tag.get()
        if folder=="trash": videos=list(TRASH_DIR.glob("*.mp4"));tm=True
        else: videos=list(OUTPUT_DIR.glob("*.mp4"));tm=False
        if not tm and folder and folder!="all" and folder!="favorites":
            videos=[v for v in videos if self.meta.get_folder(v.name)==folder]
        if folder=="favorites": videos=[v for v in videos if self.meta.is_favorite(v.name)]
        if tag and tag!="all": videos=[v for v in videos if tag in self.meta.get_tags(v.name)]
        q=self.browse_search.get().lower()
        if q: videos=[v for v in videos if q in v.stem.lower()]
        sort=self.browse_sort.get()
        if sort=="date_desc": videos.sort(key=lambda v:v.stat().st_mtime,reverse=True)
        elif sort=="favs_first": videos.sort(key=lambda v:not self.meta.is_favorite(v.name))
        elif sort=="name_asc": videos.sort(key=lambda v:v.stem.lower())
        if not videos:
            tk.Label(self.bframe,text="Trash is empty." if tm else "No clips.",font=("Courier New",9),fg=GRAY,bg=BG_RED).pack(expand=True,pady=40)
            self._refresh_folders_tags();return
        if tm:
            tb=tk.Frame(self.bframe,bg=BG_RED);tb.pack(fill="x",padx=12,pady=(4,6))
            HoverButton(tb,text="DELETE ALL FOREVER",font=("Courier New",8,"bold"),fg=WHITE,bg=TRASH_RED,bd=0,padx=12,pady=4,cursor="hand2",command=self._empty_trash).pack(side="left")

        rf=None
        for i,vid in enumerate(videos):
            if i%4==0: rf=tk.Frame(self.bframe,bg=BG_RED);rf.pack(pady=4)

            is_fav=self.meta.is_favorite(vid.name);tl=self.meta.get_tags(vid.name)
            views=self.meta.get_views(vid.name);fn=self.meta.get_folder(vid.name)

            card=tk.Frame(rf,bg=CARD_BG,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER,width=180,height=210)
            card.pack(side="left",padx=4)
            card.pack_propagate(False)
            card.video_name = vid.name
            card_data = {'frame': card}

            tr=tk.Frame(card,bg=CARD_BG);tr.pack(fill="x",padx=8,pady=(8,0))
            sc="★" if is_fav else "☆";sco=STAR_GOLD if is_fav else GRAY
            sl=tk.Label(tr,text=sc,font=("Helvetica Neue",12),fg=sco,bg=CARD_BG,cursor="hand2")
            sl.pack(side="left");sl.bind("<Button-1>",lambda e,v=vid:self._toggle_fav(v))
            self._star_labels[vid.name] = sl
            card_data['star'] = sl
            db=tk.Label(tr,text="✖",font=("Helvetica Neue",12,"bold"),fg=TRASH_RED,bg=CARD_BG,cursor="hand2")
            db.pack(side="right")
            if tm:db.bind("<Button-1>",lambda e,v=vid:self._delete_forever_confirm(v))
            else:db.bind("<Button-1>",lambda e,v=vid:self._move_trash_instant(v))

            nm=vid.stem[:18]+("..." if len(vid.stem)>18 else "")
            tk.Label(card,text=nm,font=("Courier New",8,"bold"),fg=WHITE,bg=CARD_BG,wraplength=140).pack(pady=(4,1))
            dt=datetime.fromtimestamp(vid.stat().st_mtime).strftime("%m/%d/%y %H:%M")
            tk.Label(card,text=dt,font=("Courier New",7),fg=GRAY,bg=CARD_BG).pack()
            tk.Label(card,text=f"{human_size(vid.stat().st_size)}  •  {views} views",font=("Courier New",7),fg=GRAY,bg=CARD_BG).pack()

            if fn and fn!="all" and not tm:
                flbl=tk.Label(card,text=f"[{fn}]",font=("Courier New",7),fg=ACCENT,bg=CARD_BG)
                flbl.pack();card_data['folder']=flbl
            if tl and not tm:
                tr2=tk.Frame(card,bg=CARD_BG);tr2.pack(pady=(4,2));card_data['tags']=tr2
                for t in tl[:3]:
                    ci=hash(t)%len(TAG_COLORS)
                    TagChip(tr2,t,TAG_COLORS[ci],on_remove=lambda tag,v=vid:self._remove_tag(v,tag)).pack(side="left",padx=1)

            br2=tk.Frame(card,bg=CARD_BG);br2.pack(pady=(6,10))
            self._card_widgets[vid.name] = card_data
            if not tm:
                HoverButton(br2,text="VIEW",font=("Courier New",7,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=8,pady=2,command=lambda p=vid:self._view(p)).pack(side="left",padx=2)
                HoverButton(br2,text="TAG",font=("Courier New",7,"bold"),fg=BLACK,bg=UPLOAD_BLUE,bd=0,padx=8,pady=2,command=lambda p=vid:self._tag(p)).pack(side="left",padx=2)
                HoverButton(br2,text="MOVE",font=("Courier New",7,"bold"),fg=BLACK,bg=ACCENT,bd=0,padx=8,pady=2,command=lambda p=vid:self._move(p)).pack(side="left",padx=2)
                HoverButton(br2,text="↑",font=("Courier New",7,"bold"),fg=BLACK,bg=UPLOAD_GREEN,bd=0,padx=8,pady=2,command=lambda p=vid:self._queue_up(p)).pack(side="left",padx=2)
            else:
                HoverButton(br2,text="RESTORE",font=("Courier New",7,"bold"),fg=BLACK,bg=UPLOAD_GREEN,bd=0,padx=8,pady=2,command=lambda p=vid:self._restore(p)).pack(side="left",padx=2)
                HoverButton(br2,text="DELETE",font=("Courier New",7,"bold"),fg=WHITE,bg=TRASH_RED,bd=0,padx=8,pady=2,command=lambda p=vid:self._delete_forever(p)).pack(side="left",padx=2)
        self._refresh_folders_tags()

    def _move_trash_instant(self, vp):
        TRASH_DIR.mkdir(parents=True,exist_ok=True);d=TRASH_DIR/vp.name
        if vp.exists(): shutil.move(str(vp),str(d))
        self.meta.set_folder(vp.name,"trash")
        # Remove card in-place
        if vp.name in self._card_widgets:
            card = self._card_widgets[vp.name]['frame']
            if card.winfo_exists():
                parent = card.master
                card.destroy()
                if vp.name in self._star_labels: del self._star_labels[vp.name]
                del self._card_widgets[vp.name]
                # If parent row is now empty, remove it
                if len(parent.winfo_children()) == 0:
                    parent.destroy()
        self._refresh_folders_tags()

    def _delete_forever_confirm(self, vp):
        if messagebox.askyesno("Delete Forever",f"Permanently delete {vp.name}?\nThis cannot be undone."):
            self._delete_forever(vp)

    def _move_trash(self,vp):
        self._move_trash_instant(vp)
    def _restore(self,vp):
        d=OUTPUT_DIR/vp.name
        if vp.exists(): shutil.move(str(vp),str(d))
        self.meta.set_folder(vp.name,"all")
        # In-place remove from trash view
        if vp.name in self._card_widgets:
            card = self._card_widgets[vp.name]['frame']
            if card.winfo_exists():
                parent = card.master
                card.destroy()
                if vp.name in self._star_labels: del self._star_labels[vp.name]
                del self._card_widgets[vp.name]
                if len(parent.winfo_children()) == 0:
                    parent.destroy()
        self._refresh_folders_tags()
    def _delete_forever(self,vp):
        if messagebox.askyesno("Delete Forever",f"Permanently delete {vp.name}?"):
            if vp.exists(): vp.unlink()
            if vp.name in self.meta.data: del self.meta.data[vp.name];self.meta._save()
            self._filter_folder()
    def _empty_trash(self):
        if messagebox.askyesno("Empty Trash","Delete ALL trash forever?"):
            for v in TRASH_DIR.glob("*.mp4"):
                v.unlink()
                if v.name in self.meta.data: del self.meta.data[v.name]
            self.meta._save();self._filter_folder()
    def _toggle_fav(self,vp):
        self.meta.toggle_favorite(vp.name)
        is_fav = self.meta.is_favorite(vp.name)
        # Update star in-place if card exists
        if vp.name in self._star_labels:
            lbl = self._star_labels[vp.name]
            if lbl.winfo_exists():
                lbl.config(text="★" if is_fav else "☆", fg=STAR_GOLD if is_fav else GRAY)
        # If in favorites folder and unfavorited, refresh the folder view
        if self.browse_folder.get() == "favorites" and not is_fav:
            self._filter_folder()
    def _view(self,vp):
        self.meta.increment_views(vp.name)
        if platform.system()=="Windows": os.startfile(str(vp))
        elif platform.system()=="Darwin": subprocess.Popen(["open",str(vp)])
        else: subprocess.Popen(["xdg-open",str(vp)])
        self._filter_folder()
    def _tag(self,vp):
        ex=", ".join(self.meta.get_all_tags())
        tag=simpledialog.askstring("Add Tag",f"Tag for {vp.name}:\nExisting: {ex}")
        if tag: self.meta.add_tag(vp.name,tag.strip());self._update_tags_inplace(vp)
    def _remove_tag(self,vp,tag):
        self.meta.remove_tag(vp.name,tag)
        if vp.name in self._card_widgets and 'tags' in self._card_widgets[vp.name]:
            tf = self._card_widgets[vp.name]['tags']
            for w in tf.winfo_children(): w.destroy()
            for t in self.meta.get_tags(vp.name)[:3]:
                ci=hash(t)%len(TAG_COLORS)
                TagChip(tf,t,TAG_COLORS[ci],on_remove=lambda tag,v=vp:self._remove_tag(v,tag)).pack(side="left",padx=1)
        self._refresh_folders_tags()
    def _move(self,vp):
        folds=", ".join([f for f in self.meta.get_all_folders() if f not in["trash","favorites"]])
        f=simpledialog.askstring("Move",f"Folder for {vp.name}:\nExisting: {folds}")
        if f: self.meta.set_folder(vp.name,f.strip());self._update_folder_inplace(vp,f.strip())
    def _queue_up(self,vp):
        cap=simpledialog.askstring("Upload",f"Caption for {vp.name}:")
        if cap is None: return
        plats=[]
        if messagebox.askyesno("Instagram","Upload to Instagram?"): plats.append("instagram")
        if messagebox.askyesno("TikTok","Upload to TikTok?"): plats.append("tiktok")
        if plats: self.upload.queue(str(vp),cap,plats);self._refresh_upload();messagebox.showinfo("Queued","Added!")

    def _build_upload(self):
        tab=tk.Frame(self.content,bg=BG_RED);self.tabs["UPLOAD"]=tab
        hdr=tk.Frame(tab,bg=BG_RED);hdr.pack(fill="x",padx=20,pady=(14,8))
        tk.Label(hdr,text="UPLOAD QUEUE",font=("Helvetica Neue",14,"bold"),fg=WHITE,bg=BG_RED).pack(side="left")
        st=tk.Frame(tab,bg=BG_RED);st.pack(fill="x",padx=20,pady=(0,8))
        self.ig_lbl=tk.Label(st,text="IG: NOT PAIRED",font=("Courier New",7,"bold"),fg=GRAY,bg=BG_RED);self.ig_lbl.pack(side="left",padx=(0,14))
        HoverButton(st,text="PAIR IG",font=("Courier New",7,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=8,pady=1,command=lambda:[setattr(self.upload,'paired_ig',True),self.ig_lbl.config(text="IG: PAIRED",fg=UPLOAD_GREEN),messagebox.showinfo("Instagram","Paired!")]).pack(side="left",padx=2)
        self.tt_lbl=tk.Label(st,text="TT: NOT PAIRED",font=("Courier New",7,"bold"),fg=GRAY,bg=BG_RED);self.tt_lbl.pack(side="left",padx=(14,0))
        HoverButton(st,text="PAIR TT",font=("Courier New",7,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=8,pady=1,command=lambda:[setattr(self.upload,'paired_tt',True),self.tt_lbl.config(text="TT: PAIRED",fg=UPLOAD_GREEN),messagebox.showinfo("TikTok","Paired!")]).pack(side="left",padx=2)
        self.ulb_frame=ctk.CTkScrollableFrame(tab,fg_color=DARK_RED)
        self.ulb_frame.pack(fill="both",expand=True,padx=20,pady=(6,6))
        self.ulb=tk.Listbox(self.ulb_frame,bg=DARK_RED,fg=WHITE,selectbackground=WHITE,selectforeground=BLACK,font=("Courier New",8),bd=0,height=20)
        self.ulb.pack(fill="both",expand=True)
        br=tk.Frame(tab,bg=BG_RED);br.pack(fill="x",padx=20,pady=(0,14))
        HoverButton(br,text="REMOVE",font=("Courier New",8,"bold"),fg=BLACK,bg=ACCENT,bd=0,padx=10,pady=4,command=self._remove_draft).pack(side="left")
        HoverButton(br,text="UPLOAD ALL",font=("Courier New",8,"bold"),fg=BLACK,bg=UPLOAD_GREEN,bd=0,padx=10,pady=4,command=self._upload_all).pack(side="right")
        self._refresh_upload()
    def _refresh_upload(self):
        self.ulb.delete(0,"end")
        for d in self.upload.get(): self.ulb.insert("end",f"  [{d['status'].upper()}] {Path(d['video']).name[:45]} → {','.join(d['platforms'])}")
    def _remove_draft(self):
        sel=self.ulb.curselection()
        if sel: self.upload.remove(sel[0]);self._refresh_upload()
    def _upload_all(self):
        drafts=self.upload.get()
        if not drafts: messagebox.showinfo("Queue","No drafts.");return
        for d in drafts: d["status"]="uploaded"
        self._refresh_upload();messagebox.showinfo("Upload",f"{len(drafts)} uploaded!")

    def _slot(self,parent,key,meta):
        card=tk.Frame(parent,bg=CARD_BG,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        card.pack(fill="x",pady=(0,6),ipady=2)
        tk.Label(card,text=meta["label"],font=("Helvetica Neue",9,"bold"),fg=WHITE,bg=CARD_BG).pack(pady=(8,1))
        tk.Label(card,text=meta["hint"],font=("Courier New",7),fg="#E8DDD4",bg=CARD_BG).pack(pady=(0,4))
        lb=tk.Listbox(card,bg=DARK_RED,fg=WHITE,selectbackground=WHITE,selectforeground=BLACK,font=("Courier New",8),height=3,bd=0,highlightthickness=0,activestyle="none")
        lb.pack(fill="x",padx=12,pady=(0,4));self.listboxes[key]=lb
        lb.bind("<Delete>",lambda e,k=key:self._remove_selected(k))
        lb.bind("<BackSpace>",lambda e,k=key:self._remove_selected(k))
        br=tk.Frame(card,bg=CARD_BG);br.pack(pady=(0,6))
        HoverButton(br,text="ADD",font=("Courier New",8,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=10,pady=2,cursor="hand2",command=lambda k=key,m=meta:self._add_files(k,m)).pack(side="left",padx=2)
        HoverButton(br,text="REMOVE",font=("Courier New",8),fg=WHITE,bg=DARK_RED,hover_bg="#7A0000",bd=0,padx=10,pady=2,cursor="hand2",command=lambda k=key:self._remove_selected(k)).pack(side="left",padx=2)

    def _logo_card(self,parent):
        card=tk.Frame(parent,bg=CARD_BG,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        card.pack(fill="x",pady=(0,6),ipady=2)
        tk.Label(card,text=LOGO_SLOT["label"],font=("Helvetica Neue",8,"bold"),fg=WHITE,bg=CARD_BG).pack(pady=(8,1))
        tk.Label(card,text=LOGO_SLOT["hint"],font=("Courier New",6),fg=GRAY,bg=CARD_BG).pack(pady=(0,4))
        self.logo_var=tk.StringVar()
        tk.Entry(card,textvariable=self.logo_var,font=("Courier New",8),bg=DARK_RED,fg=WHITE,insertbackground=WHITE,bd=0,justify="center").pack(fill="x",padx=16,ipady=3)
        HoverButton(card,text="SELECT LOGO",font=("Courier New",8,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=12,pady=3,cursor="hand2",command=self._add_logo).pack(pady=(4,8))

    def _settings_card(self,parent):
        card=tk.Frame(parent,bg=CARD_BG,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        card.pack(fill="x",pady=(0,6),ipady=2)
        tk.Label(card,text="SETTINGS",font=("Helvetica Neue",8,"bold"),fg=WHITE,bg=CARD_BG).pack(pady=(8,4))
        self.preview_var=tk.BooleanVar(value=self.config["settings"].get("preview_mode",True))
        tk.Checkbutton(card,text="Preview Mode (1080p)",variable=self.preview_var,font=("Courier New",7),fg=WHITE,bg=CARD_BG,selectcolor=DARK_RED,activebackground=CARD_BG,activeforeground=WHITE,relief="flat",command=self._save_settings).pack(pady=(0,4))
        tk.Label(card,text="CAPTION FONT",font=("Courier New",7,"bold"),fg=GRAY,bg=CARD_BG).pack(pady=(6,0))
        cf=self.config.get("caption_font","Impact")
        if cf not in self.fonts_ok: cf="Impact"
        self.font_preview=tk.Label(card,text="Aa Bb Cc 123",font=(cf,14),fg=WHITE,bg=DARK_RED)
        self.font_preview.pack(pady=(2,4),ipadx=20,ipady=2)
        self.cap_font_var=tk.StringVar(value=cf)
        fd=tk.OptionMenu(card,self.cap_font_var,cf,*self.fonts_ok,command=lambda c:[self.cap_font_var.set(c),self.config.update({"caption_font":c}),self._save_config(),self.font_preview.config(font=(c,14))])
        fd.config(font=("Courier New",8),bg=DARK_RED,fg=WHITE,activebackground=CARD_BG,bd=0,highlightthickness=1,highlightcolor=BORDER,highlightbackground=CARD_BG,width=28)
        fd["menu"].config(font=("Courier New",8),bg=CARD_BG,fg=WHITE,activebackground=DARK_RED,bd=0)
        fd.pack(fill="x",padx=8,pady=(2,6))
        caps=self.config.get("captions",{})
        for act,vn,lb in [("act_a","cap_a_var","ACT A"),("act_b","cap_b_var","ACT B")]:
            tk.Label(card,text=lb,font=("Courier New",7,"bold"),fg=GRAY,bg=CARD_BG).pack(pady=(3,1))
            e=tk.Entry(card,font=("Courier New",8),bg=DARK_RED,fg=WHITE,insertbackground=WHITE,bd=0,highlightthickness=1,highlightcolor=BORDER,highlightbackground=CARD_BG,justify="center")
            e.pack(fill="x",padx=16,ipady=2)
            sv=tk.StringVar(value=caps.get(act,""));e.configure(textvariable=sv);setattr(self,vn,sv)
        HoverButton(card,text="SAVE",font=("Courier New",8,"bold"),fg=BLACK,bg=WHITE,bd=0,padx=12,pady=3,command=self._save_settings).pack(pady=(8,8))

    def _render_card(self,parent):
        card=tk.Frame(parent,bg=CARD_BG,highlightthickness=1,highlightbackground=BORDER,highlightcolor=BORDER)
        card.pack(fill="x",pady=(0,6),ipady=2)
        tk.Label(card,text="RENDER",font=("Helvetica Neue",8,"bold"),fg=WHITE,bg=CARD_BG).pack(pady=(8,2))
        self.render_count_var=tk.IntVar(value=self.config.get("num_renders",10))
        self.count_label=tk.Label(card,text=str(self.render_count_var.get()),font=("Helvetica Neue",28,"bold"),fg=WHITE,bg=CARD_BG)
        self.count_label.pack()
        tk.Scale(card,from_=1,to=100,orient="horizontal",variable=self.render_count_var,command=lambda v:[self.count_label.config(text=str(int(float(v)))),self.config.update({"num_renders":int(float(v))}),self._save_config()],bg=CARD_BG,fg=WHITE,troughcolor=DARK_RED,highlightthickness=0,bd=0,length=240,showvalue=False).pack(pady=(0,3))
        pr=tk.Frame(card,bg=CARD_BG);pr.pack(pady=(0,4))
        for n in[5,10,25,50,100]:
            HoverButton(pr,text=str(n),font=("Courier New",8,"bold"),fg=GRAY,bg=DARK_RED,hover_bg=ACCENT,hover_fg=WHITE,bd=0,padx=8,pady=1,cursor="hand2",command=lambda v=n:[self.render_count_var.set(v),self.count_label.config(text=str(v)),self.config.update({"num_renders":v}),self._save_config()]).pack(side="left",padx=1)
        HoverButton(card,text="▶  RUN REMIXER  (Ctrl+R)",font=("Helvetica Neue",11,"bold"),fg=BLACK,bg=WHITE,hover_bg=ACCENT,hover_fg=WHITE,bd=0,padx=24,pady=6,cursor="hand2",command=self._run_remixer).pack(pady=(0,8))

    def _add_files(self,key,meta):
        if self._busy: return
        paths=filedialog.askopenfilenames(title=f"Select files for {meta['label']}",filetypes=meta["types"]+[("All files","*.*")])
        if not paths: return
        threading.Thread(target=self._process_files,args=(key,meta,paths),daemon=True).start()
    def _process_files(self,key,meta,paths):
        self._busy=True;added=0
        for path in paths:
            src=Path(path);size=src.stat().st_size
            if size>200*1024*1024: rel=str(src).replace("\\","/")
            else:
                dd=BASE_DIR/meta["subfolder"];dd.mkdir(parents=True,exist_ok=True)
                dest=dd/src.name
                if str(dest)!=str(src): shutil.copy2(str(src),str(dest))
                rel=str(dest.relative_to(BASE_DIR)).replace("\\","/")
            cur=self.config.get(key,[])
            if rel not in cur: cur.append(rel);added+=1
            self.config[key]=cur
        self._save_config();self.after(0,lambda:self._refresh_listbox(key));self._set_status(f"{added} file(s) added.");self._busy=False
    def _remove_selected(self,key):
        lb=self.listboxes.get(key)
        if not lb: return
        sel=lb.curselection()
        if not sel: return
        items=list(self.config.get(key,[]))
        for i in reversed(sel):
            if i<len(items): items.pop(i)
        self.config[key]=items;self._save_config();self._refresh_listbox(key);self._set_status("Removed.")
    def _add_logo(self):
        if self._busy: return
        p=filedialog.askopenfilename(title="Select Logo",filetypes=LOGO_SLOT["types"]+[("All files","*.*")])
        if not p: return
        threading.Thread(target=self._process_logo,args=(p,),daemon=True).start()
    def _process_logo(self,path):
        self._busy=True;src=Path(path);size=src.stat().st_size
        if size>200*1024*1024: rel=str(src).replace("\\","/")
        else:
            dd=BASE_DIR/LOGO_SLOT["subfolder"];dd.mkdir(parents=True,exist_ok=True)
            dest=dd/src.name
            if str(dest)!=str(src): shutil.copy2(str(src),str(dest))
            rel=str(dest.relative_to(BASE_DIR)).replace("\\","/")
        self.config["logo"]=rel;self._save_config();self.after(0,lambda:self.logo_var.set(rel));self._set_status(f"Logo: {src.name}");self._busy=False
    def _save_settings(self):
        self.config["settings"]["preview_mode"]=self.preview_var.get()
        self.config["captions"]["act_a"]=self.cap_a_var.get()
        self.config["captions"]["act_b"]=self.cap_b_var.get()
        self.config["caption_font"]=self.cap_font_var.get()
        self.config["settings"]["format"]=self.fmt_var.get()
        self.config["settings"]["clip_length"]=self.len_var.get()
        self._save_config();self._set_status("Settings saved.")
    def _refresh_listbox(self,key):
        lb=self.listboxes.get(key)
        if not lb: return
        lb.delete(0,"end")
        for path in self.config.get(key,[]):
            full=Path(path)
            sz=f"[{human_size(full.stat().st_size)}]"
            name=full.name
            if len(name)>38: name=name[:18]+"..."+name[-15:]
            entry=f" {sz:>10}  {name}"
            lb.insert("end",entry)
    def _refresh_all(self):
        for key in self.listboxes: self._refresh_listbox(key)
        self.logo_var.set(self.config.get("logo",""));self._refresh_project_menu()

    def _on_project(self,choice):
        if not choice: return
        self._save_proj();proj=self.projects.get(choice)
        if proj:
            a=proj.get("assets",{})
            for key in["act_a_videos","act_b_videos","act_a_music","act_b_music","voiceover_clips"]: self.config[key]=a.get(key,[])
            self.config["logo"]=a.get("logo","");self.config["captions"]=proj.get("captions",{})
            self.config["settings"].update(proj.get("settings",{}))
            self.config["num_renders"]=proj.get("settings",{}).get("num_renders",10)
            self.config["caption_font"]=proj.get("settings",{}).get("caption_font","Impact")
            self.fmt_var.set(proj.get("settings",{}).get("format","Reel / TikTok (9:16)"))
            self.len_var.set(proj.get("settings",{}).get("clip_length",30))
            self.projects.current=choice;self._refresh_all();self._set_status(f"Loaded: {choice}")
    def _save_proj(self):
        if self.projects.current:
            data={"name":self.projects.current,"assets":{"act_a_videos":self.config.get("act_a_videos",[]),"act_b_videos":self.config.get("act_b_videos",[]),"act_a_music":self.config.get("act_a_music",[]),"act_b_music":self.config.get("act_b_music",[]),"voiceover_clips":self.config.get("voiceover_clips",[]),"logo":self.config.get("logo","")},"captions":self.config.get("captions",{}),"settings":self.config.get("settings",{})}
            data["settings"]["num_renders"]=self.config.get("num_renders",10);data["settings"]["caption_font"]=self.config.get("caption_font","Impact")
            data["settings"]["format"]=self.fmt_var.get();data["settings"]["clip_length"]=self.len_var.get()
            self.projects.save(self.projects.current,data)
    def _new_project(self):
        self._save_proj();name=simpledialog.askstring("New Project","Artist / Project name:")
        if name:
            if self.projects.create(name): self._refresh_project_menu();self.proj_var.set(name);self._on_project(name)
            else: messagebox.showerror("Error","Project already exists.")
    def _refresh_project_menu(self):
        menu=self.proj_menu["menu"];menu.delete(0,"end")
        for name in self.projects.list_names(): menu.add_command(label=name,command=lambda v=name:(self.proj_var.set(v),self._on_project(v)))

    def _start_live_polling(self):
        if not self._live_polling:
            self._live_polling = True
            self._poll_browse()

    def _poll_browse(self):
        if not self._live_polling: return
        # Auto-stop if render complete
        if (BASE_DIR / "_render_complete.txt").exists():
            self._stop_live_polling()
            self._filter_folder()
            return
        if hasattr(self, 'bframe'):
            try:
                current_count = len(list(OUTPUT_DIR.glob("*.mp4")))
                if not hasattr(self, '_last_video_count') or current_count != self._last_video_count:
                    self._filter_folder()
                    self._last_video_count = current_count
            except: pass
            self.after(1500, self._poll_browse)

    def _stop_live_polling(self):
        self._live_polling = False
        self._last_browse_state = None
        if hasattr(self, '_last_video_count'): del self._last_video_count

    def _run_remixer(self):
        rp=BASE_DIR/"remixer.py"
        if not rp.exists(): messagebox.showerror("Error","remixer.py not found.");return
        self._save_proj()
        self.config["num_renders"]=self.render_count_var.get()
        self.config["caption_font"]=self.cap_font_var.get()
        self.config["captions"]["act_a"]=self.cap_a_var.get()
        self.config["captions"]["act_b"]=self.cap_b_var.get()
        self.config["settings"]["preview_mode"]=self.preview_var.get()
        fmt=self.fmt_var.get()
        if fmt in FORMAT_PRESETS:
            p=FORMAT_PRESETS[fmt];self.config["settings"]["target_w"]=p["w"];self.config["settings"]["target_h"]=p["h"];self.config["settings"]["target_fps"]=p["fps"]
        self.config["settings"]["format"]=fmt;self.config["settings"]["clip_length"]=self.len_var.get()
        self._save_config()
        bp=BASE_DIR/"_run_remixer.bat"
        with open(bp,"w",encoding="ascii") as f:
            f.write("@echo off\ntitle FLOODGATE TERMINAL\necho.\necho   ====================================\necho     FLOODGATE - RENDERING\necho   ====================================\necho.\n")
            f.write(f'"{sys.executable}" "{rp}"\n')
            f.write("echo.\necho   ====================================\necho     COMPLETE - Close this window.\necho   ====================================\necho.\n")
            f.write(f'echo DONE > "{BASE_DIR}\\_render_complete.txt"\n')
            f.write("pause\n")
        # Clear completion signal
        done_file = BASE_DIR / "_render_complete.txt"
        if done_file.exists(): done_file.unlink()
        self._start_live_polling()
        subprocess.Popen(["cmd","/k",str(bp)],creationflags=subprocess.CREATE_NEW_CONSOLE)
        self._set_status(f"Remixer launched — {self.render_count_var.get()} renders.")
    def on_close(self): self._stop_live_polling();self._save_proj();self.destroy()

if __name__=="__main__":
    app=FloodGate();app.protocol("WM_DELETE_WINDOW",app.on_close);app.mainloop()