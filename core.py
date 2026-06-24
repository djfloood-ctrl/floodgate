"""
core.py – Shared utilities for FloodGate
"""

import json, os, shutil, subprocess, sys, threading, tkinter as tk, platform
from pathlib import Path
from datetime import datetime

# Constants (shared across modules)
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
"Reel / TikTok (9:16)":{"w":1080,"h":1920,"fps":30},
"YouTube Shorts (9:16)":{"w":1080,"h":1920,"fps":30},
"Instagram Story (9:16)":{"w":1080,"h":1920,"fps":30},
"Snapchat (9:16)":{"w":1080,"h":1920,"fps":30},
"Square Post (1:1)":{"w":1080,"h":1080,"fps":30},
"LinkedIn (1:1)":{"w":1080,"h":1080,"fps":30},
"Widescreen (16:9)":{"w":1920,"h":1080,"fps":30},
"Twitter / X (16:9)":{"w":1280,"h":720,"fps":30},
"Facebook (16:9)":{"w":1280,"h":720,"fps":30},
"Cinematic (21:9)":{"w":2560,"h":1080,"fps":24},
"Pinterest (2:3)":{"w":1000,"h":1500,"fps":30},
"Custom":{"w":1080,"h":1920,"fps":30},
}

DEFAULT_TEMPLATES = {
    "SAD CLIP / HAPPY CLIP": ["act_a_videos","act_b_videos","act_a_music","act_b_music","voiceover_clips"],
    "LONGFORM CLIPS": ["longform_source","voiceover_clips"],
}

CLIP_LENGTHS = {"2 secs":2,"5 secs":5,"10 secs":10,"15 secs":15,"30 secs":30,"60 secs":60,"90 secs":90,"3 min":180,"5 min":300}

SLOTS = {
    "act_a_videos": {"label":"Act A — Sad / Bleak Clips","subfolder":"assets/act_a","types":[("Video","*.mp4 *.mov *.avi *.mkv")],"hint":"Sad, bleak, melancholic, rainy day footage","side":"left"},
    "act_b_videos": {"label":"Act B — Heat / Energy Clips","subfolder":"assets/act_b","types":[("Video","*.mp4 *.mov *.avi *.mkv")],"hint":"Hype, energy, heat, crowds, lights, action","side":"right"},
    "act_a_music": {"label":"Act A — Sad Music","subfolder":"assets/music/sad","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"Sad instrumentals, ambient sounds, quiet tracks","side":"left"},
    "act_b_music": {"label":"Act B — Bangers","subfolder":"assets/music/heat","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"Your tracks, beats, remixes, produced music","side":"right"},
    "longform_source": {"label":"Longform Source","subfolder":"assets/longform","types":[("Video","*.mp4 *.mov *.avi *.mkv"),("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"Movies, podcasts, TV, comedy","side":"center"},
    "voiceover_clips": {"label":"Voiceover — AI Clips","subfolder":"assets/voiceovers","types":[("Audio","*.mp3 *.wav *.aac *.m4a")],"hint":"AI-generated voice clips for your videos","side":"center"},
}
LOGO_SLOT = {"label":"Logo — Final Frame","subfolder":"assets/logo","types":[("Image","*.png *.jpg *.jpeg")],"hint":"Your brand logo with transparent background","side":"center"}

# Utility functions
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

# Data models
class ClipMeta:
    def __init__(self,p, output_dir, trash_dir):
        self.path=p
        self.output_dir = output_dir
        self.trash_dir = trash_dir
        self.data=load_json(p,{})
        self._migrate()
    def _migrate(self):
        ch=False
        for v in self.output_dir.glob("*.mp4"):
            if v.name not in self.data: self.data[v.name]={"fav":False,"tags":[],"views":0,"folder":"all"};ch=True
        self.trash_dir.mkdir(parents=True,exist_ok=True)
        for v in self.trash_dir.glob("*.mp4"):
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

class ProjectManager:
    def __init__(self, projects_dir):
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True,exist_ok=True)
        self.projects=self._load()
        if "Default" not in self.projects: self._mkdefault()
        self.current="Default"
    def _mkdefault(self):
        save_json(self.projects_dir/"Default"/"project.json",{"name":"Default","assets":{"act_a_videos":[],"act_b_videos":[],"act_a_music":[],"act_b_music":[],"voiceover_clips":[],"logo":""},"captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"},"settings":{"preview_mode":True,"music_volume":0.35,"caption_font":"Impact","num_renders":10,"format":"Reel / TikTok (9:16)","clip_length":15}})
        self.projects["Default"]=load_json(self.projects_dir/"Default"/"project.json")
    def _load(self):
        p={}
        for d in self.projects_dir.iterdir():
            if d.is_dir() and (d/"project.json").exists(): p[d.name]=load_json(d/"project.json")
        return p
    def create(self,name):
        if name in self.projects: return False
        data={"name":name,"assets":{"act_a_videos":[],"act_b_videos":[],"act_a_music":[],"act_b_music":[],"voiceover_clips":[],"logo":""},"captions":{"act_a":"Without DJ FLOOD","act_b":"With DJ FLOOD"},"settings":{"preview_mode":True,"music_volume":0.35,"caption_font":"Impact","num_renders":10,"format":"Reel / TikTok (9:16)","clip_length":15}}
        save_json(self.projects_dir/name/"project.json",data);self.projects[name]=data;return True
    def list_names(self): return sorted(self.projects.keys())
    def get(self,name): return self.projects.get(name)
    def save(self,name,data): self.projects[name]=data;save_json(self.projects_dir/name/"project.json",data)

class UploadManager:
    def __init__(self): self.drafts=[];self.paired_ig=False;self.paired_tt=False
    def queue(self,vp,caption,platforms): self.drafts.append({"video":vp,"caption":caption,"platforms":platforms,"status":"queued"})
    def get(self): return self.drafts
    def remove(self,i):
        if 0<=i<len(self.drafts): self.drafts.pop(i)

# Custom UI components
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