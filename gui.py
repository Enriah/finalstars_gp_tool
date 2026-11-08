# -*- coding: utf-8 -*-
"""
IOM GYM - Giao diện Desktop Tkinter (Native GUI với thanh trượt).
Chạy: python gui.py
Hỗ trợ chỉnh sửa cả hệ thống hiệu ứng và custom chỉ số từng bên (Đội A vs Đội B).
"""
import copy
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import load_cfg, Sim  # noqa: E402
from gym import run_batch, soft_check, resolve_team, uptime_rows, pct  # noqa: E402
from ui import SLIDERS_META, CUSTOM_STATS_META, RULES_PATH, get_baseline_rules, get_current_rules, save_rules, get_entity_default_stats  # noqa: E402


class IOMGymGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IOM GYM - Cân Bằng Hiệu Ứng & Custom Chỉ Số")
        self.geometry("1040x760")
        self.minsize(880, 600)

        self.colors = {
            "bg": "#111420",
            "card_bg": "#181d2c",
            "fg": "#f1f5f9",
            "muted": "#94a3b8",
            "accent": "#38bdf8",
            "border": "#28324a",
            "team_a": "#ef4444",
            "team_b": "#3b82f6"
        }
        self.configure(bg=self.colors["bg"])

        self.current_rules = get_current_rules()
        self.baseline_rules = get_baseline_rules()
        self.slider_vars = {}

        self.team_a_vars = {}
        self.team_b_vars = {}

        self.cfg = load_cfg()
        self.setup_styles()
        self.build_ui()
        self.update_diff_status()

    def setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=self.colors["bg"], foreground=self.colors["fg"])
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e2436", foreground="#cbd5e1", padding=[10, 5], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Card.TFrame", background=self.colors["card_bg"], relief="flat")
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["fg"], font=("Segoe UI", 9))
        style.configure("Muted.TLabel", foreground=self.colors["muted"], font=("Segoe UI", 8))
        style.configure("Bold.TLabel", font=("Segoe UI", 9, "bold"))

    def get_val(self, obj, path):
        parts = path.split(".")
        curr = obj
        for p in parts:
            if not isinstance(curr, dict) or p not in curr:
                return None
            curr = curr[p]
        return curr

    def set_val(self, obj, path, val):
        parts = path.split(".")
        curr = obj
        for p in parts[:-1]:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        curr[parts[-1]] = val

    def build_ui(self):
        # 1. Header Toolbar
        header = tk.Frame(self, bg="#161c2c", pady=10, padx=16, highlightthickness=1, highlightbackground=self.colors["border"])
        header.pack(fill="x", side="top")

        lbl_title = tk.Label(header, text="✦ IOM GYM BALANCE STUDIO", font=("Segoe UI", 12, "bold"), fg=self.colors["accent"], bg="#161c2c")
        lbl_title.pack(side="left")

        self.lbl_diff_count = tk.Label(header, text="0 chỉ số đã đổi", font=("Segoe UI", 9, "bold"), fg="#fbbf24", bg="#1e293b", padx=8, pady=2)
        self.lbl_diff_count.pack(side="left", padx=12)

        btn_save = tk.Button(header, text="💾 Lưu Cấu Hình", bg="#0284c7", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, cursor="hand2", command=self.save_config)
        btn_save.pack(side="right", padx=4)

        btn_reset = tk.Button(header, text="↺ Khôi Phục Gốc", bg="#334155", fg="#cbd5e1", font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2", command=self.reset_all)
        btn_reset.pack(side="right", padx=4)

        btn_copy_cli = tk.Button(header, text="📋 Sao Chép --set", bg="#334155", fg="#cbd5e1", font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2", command=self.copy_cli)
        btn_copy_cli.pack(side="right", padx=4)

        # 2. Main Tabbed Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)

        # TAB 1: CUSTOM CHỈ SỐ ĐỘI A & ĐỘI B (Được đặt lên đầu để dễ truy cập nhất!)
        tab_custom = ttk.Frame(self.notebook)
        self.notebook.add(tab_custom, text="⚔️ Tùy Chỉnh Chỉ Số Đội A & B")
        self.build_custom_teams_tab(tab_custom)

        # Các tab hiệu ứng magic khác
        categories = {}
        for m in SLIDERS_META:
            cat = m["category"]
            if cat not in categories:
                categories[cat] = {"name": m["cat_name"], "items": []}
            categories[cat]["items"].append(m)

        for cat_id, cat_info in categories.items():
            tab_frame = ttk.Frame(self.notebook)
            tab_label = cat_info["name"].split(" ")[0] + " " + cat_info["name"].split("(")[-1].replace(")", "")
            self.notebook.add(tab_frame, text=tab_label)
            self.populate_category_tab(tab_frame, cat_info["items"])

    def build_custom_teams_tab(self, parent):
        # Frame chia 2 cột Đội A và Đội B
        main_split = tk.Frame(parent, bg=self.colors["bg"])
        main_split.pack(fill="both", expand=True, padx=8, pady=8)

        # Left: Đội A
        frame_a = tk.LabelFrame(main_split, text=" 🔴 ĐỘI A (Chiến Binh) ", font=("Segoe UI", 10, "bold"), fg=self.colors["team_a"], bg="#141826", padx=8, pady=6)
        frame_a.pack(side="left", fill="both", expand=True, padx=4)

        # Right: Đội B
        frame_b = tk.LabelFrame(main_split, text=" 🔵 ĐỘI B (Đối Thủ / Dummy) ", font=("Segoe UI", 10, "bold"), fg=self.colors["team_b"], bg="#141826", padx=8, pady=6)
        frame_b.pack(side="left", fill="both", expand=True, padx=4)

        # Build dropdowns
        build_ids = [k for k in self.cfg["builds"] if not k.startswith("_")]
        dummy_ids = ["dummy:" + k for k in self.cfg["scenarios"]["dummies"] if not k.startswith("_")]

        # Header Đội A
        top_a = tk.Frame(frame_a, bg="#141826")
        top_a.pack(fill="x", pady=4)
        tk.Label(top_a, text="Nhân vật:", bg="#141826", fg=self.colors["muted"]).pack(side="left")
        self.cb_team_a = ttk.Combobox(top_a, values=build_ids, width=16)
        self.cb_team_a.set("amgar" if "amgar" in build_ids else build_ids[0])
        self.cb_team_a.pack(side="left", padx=6)
        self.cb_team_a.bind("<<ComboboxSelected>>", lambda e: self.on_select_team_a())

        btn_rst_a = tk.Button(top_a, text="↺ Về gốc", font=("Segoe UI", 8), bg="#222b40", fg="#cbd5e1", relief="flat", command=self.on_select_team_a)
        btn_rst_a.pack(side="left", padx=2)

        # Header Đội B
        top_b = tk.Frame(frame_b, bg="#141826")
        top_b.pack(fill="x", pady=4)
        tk.Label(top_b, text="Đối thủ:", bg="#141826", fg=self.colors["muted"]).pack(side="left")
        self.cb_team_b = ttk.Combobox(top_b, values=dummy_ids + build_ids, width=18)
        self.cb_team_b.set("baseline" if "baseline" in build_ids else dummy_ids[0])
        self.cb_team_b.pack(side="left", padx=6)
        self.cb_team_b.bind("<<ComboboxSelected>>", lambda e: self.on_select_team_b())

        btn_rst_b = tk.Button(top_b, text="↺ Về gốc", font=("Segoe UI", 8), bg="#222b40", fg="#cbd5e1", relief="flat", command=self.on_select_team_b)
        btn_rst_b.pack(side="left", padx=2)

        # Presets Đội B
        preset_row_b = tk.Frame(frame_b, bg="#141826")
        preset_row_b.pack(fill="x", pady=2)
        tk.Label(preset_row_b, text="Preset nhanh:", bg="#141826", fg=self.colors["muted"], font=("Segoe UI", 8)).pack(side="left")
        for p_name, p_val in [("Tank 1k", 1000), ("Tank 3k", 3000), ("Tank 10k", 10000)]:
            tk.Button(preset_row_b, text=p_name, font=("Segoe UI", 7), bg="#1e2436", fg="#94a3b8", relief="flat",
                      command=lambda v=p_val: self.apply_tank_preset_b(v)).pack(side="left", padx=2)

        # Sliders container A & B
        self.box_sliders_a = tk.Frame(frame_a, bg="#141826")
        self.box_sliders_a.pack(fill="both", expand=True, pady=4)

        self.box_sliders_b = tk.Frame(frame_b, bg="#141826")
        self.box_sliders_b.pack(fill="both", expand=True, pady=4)

        self.populate_team_sliders("a", self.box_sliders_a)
        self.populate_team_sliders("b", self.box_sliders_b)

        self.on_select_team_a()
        self.on_select_team_b()

        # Bottom Match Controls & Result
        ctrl_bot = tk.Frame(parent, bg="#141826", pady=6, padx=12, highlightthickness=1, highlightbackground=self.colors["border"])
        ctrl_bot.pack(fill="x", side="bottom", padx=12, pady=6)

        bar_row = tk.Frame(ctrl_bot, bg="#141826")
        bar_row.pack(fill="x")

        tk.Label(bar_row, text="Chế độ:", bg="#141826", fg=self.colors["muted"]).pack(side="left")
        self.cb_mode = ttk.Combobox(bar_row, values=["fight", "dps"], width=7)
        self.cb_mode.set("fight")
        self.cb_mode.pack(side="left", padx=6)

        tk.Label(bar_row, text="Thời gian (s):", bg="#141826", fg=self.colors["muted"]).pack(side="left", padx=6)
        self.sp_time = ttk.Spinbox(bar_row, from_=10, to=180, width=5)
        self.sp_time.set("60")
        self.sp_time.pack(side="left")

        tk.Label(bar_row, text="Số trận (runs):", bg="#141826", fg=self.colors["muted"]).pack(side="left", padx=6)
        self.sp_runs = ttk.Spinbox(bar_row, from_=5, to=200, width=5)
        self.sp_runs.set("50")
        self.sp_runs.pack(side="left")

        btn_run = tk.Button(bar_row, text="🚀 BẮT ĐẦU MÔ PHỎNG", bg="#0284c7", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", padx=16, pady=3, cursor="hand2", command=self.run_custom_sim)
        btn_run.pack(side="right", padx=4)

        # Output text
        self.txt_sim_result = tk.Text(ctrl_bot, height=4, bg="#0b0e14", fg="#e2e8f0", font=("Consolas", 9), relief="flat")
        self.txt_sim_result.pack(fill="x", pady=4)
        self.txt_sim_result.insert("1.0", "Tùy chỉnh chỉ số của Đội A & Đội B bằng các thanh trượt trên rồi nhấn 'BẮT ĐẦU MÔ PHỎNG'.")

    def populate_team_sliders(self, team, container):
        vars_dict = self.team_a_vars if team == "a" else self.team_b_vars
        color = self.colors["team_a"] if team == "a" else self.colors["team_b"]

        for m in CUSTOM_STATS_META:
            k = m["key"]
            var = tk.DoubleVar(value=m["min"])
            vars_dict[k] = {"var": var, "meta": m}

            row = tk.Frame(container, bg="#141826", pady=2)
            row.pack(fill="x")

            lbl = tk.Label(row, text=m["label"], width=17, anchor="w", bg="#141826", fg="#cbd5e1", font=("Segoe UI", 8, "bold"))
            lbl.pack(side="left")

            scale = ttk.Scale(row, from_=m["min"], to=m["max"], variable=var, orient="horizontal")
            scale.pack(side="left", fill="x", expand=True, padx=4)

            ent = tk.Entry(row, width=7, bg="#1b2030", fg="#fff", relief="solid", justify="right", font=("Segoe UI", 8))
            ent.pack(side="left", padx=4)
            ent.insert(0, str(m["min"]))

            tk.Label(row, text=m["unit"], width=4, anchor="w", bg="#141826", fg=self.colors["muted"], font=("Segoe UI", 8)).pack(side="left")

            vars_dict[k]["entry"] = ent

            def make_sync(v, e, meta):
                def on_sc(val):
                    fval = round(float(val) / meta["step"]) * meta["step"]
                    if meta["format"] == "int":
                        fval = int(round(fval))
                    else:
                        fval = round(fval, 2)
                    e.delete(0, "end")
                    e.insert(0, str(fval))

                def on_en(event=None):
                    try:
                        fval = float(e.get())
                        v.set(fval)
                    except ValueError:
                        pass
                return on_sc, on_en

            sc_fn, en_fn = make_sync(var, ent, m)
            scale.configure(command=sc_fn)
            ent.bind("<Return>", en_fn)
            ent.bind("<FocusOut>", en_fn)

    def on_select_team_a(self):
        ent_id = self.cb_team_a.get()
        defs = get_entity_default_stats(self.cfg, ent_id)
        for k, info in self.team_a_vars.items():
            val = defs.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    def on_select_team_b(self):
        ent_id = self.cb_team_b.get()
        defs = get_entity_default_stats(self.cfg, ent_id)
        for k, info in self.team_b_vars.items():
            val = defs.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    def apply_tank_preset_b(self, def_val):
        hp_map = {1000: 6000, 3000: 20000, 10000: 50000}
        self.team_b_vars["defense"]["var"].set(def_val)
        self.team_b_vars["defense"]["entry"].delete(0, "end")
        self.team_b_vars["defense"]["entry"].insert(0, str(def_val))

        hp_val = hp_map.get(def_val, 10000)
        self.team_b_vars["hp"]["var"].set(hp_val)
        self.team_b_vars["hp"]["entry"].delete(0, "end")
        self.team_b_vars["hp"]["entry"].insert(0, str(hp_val))

    def run_custom_sim(self):
        team_a_id = self.cb_team_a.get()
        team_b_id = self.cb_team_b.get()
        mode = self.cb_mode.get()
        time_limit = float(self.sp_time.get() or 60)
        runs = int(self.sp_runs.get() or 50)

        custom_a = {k: v["var"].get() for k, v in self.team_a_vars.items()}
        custom_b = {k: v["var"].get() for k, v in self.team_b_vars.items()}

        self.txt_sim_result.delete("1.0", "end")
        self.txt_sim_result.insert("1.0", f"Đang mô phỏng {team_a_id} vs {team_b_id} ({runs} lượt)...\n")
        self.update_idletasks()

        try:
            cfg = copy.deepcopy(self.cfg)
            cfg["rules"] = self.current_rules

            # Build custom A
            custom_id_a = "custom_team_a"
            if team_a_id.startswith("dummy:"):
                d = copy.deepcopy(cfg["scenarios"]["dummies"].get(team_a_id[6:], {}))
                d["hp"] = float(custom_a["hp"])
                d["defense"] = float(custom_a["defense"])
                d["guard_q"] = float(custom_a["guard_q"])
                if custom_a["res"] > 0:
                    d.setdefault("res", {})
                    d["res"]["*"] = float(custom_a["res"])
                cfg["scenarios"]["dummies"][custom_id_a] = d
                actual_a = ["dummy:" + custom_id_a]
            else:
                b = copy.deepcopy(cfg["builds"].get(team_a_id, {}))
                b["label"] = f"{team_a_id} (Custom A)"
                b.setdefault("stats", {})
                for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr"]:
                    b["stats"][k] = float(custom_a[k])
                b["guard_q"] = float(custom_a["guard_q"])
                if custom_a["res"] > 0:
                    b.setdefault("res", {})
                    b["res"]["*"] = float(custom_a["res"])
                cfg["builds"][custom_id_a] = b
                actual_a = [custom_id_a]

            # Build custom B
            custom_id_b = "custom_team_b"
            if team_b_id.startswith("dummy:"):
                d = copy.deepcopy(cfg["scenarios"]["dummies"].get(team_b_id[6:], {}))
                d["hp"] = float(custom_b["hp"])
                d["defense"] = float(custom_b["defense"])
                d["guard_q"] = float(custom_b["guard_q"])
                if custom_b["res"] > 0:
                    d.setdefault("res", {})
                    d["res"]["*"] = float(custom_b["res"])
                cfg["scenarios"]["dummies"][custom_id_b] = d
                actual_b = ["dummy:" + custom_id_b]
            else:
                b = copy.deepcopy(cfg["builds"].get(team_b_id, {}))
                b["label"] = f"{team_b_id} (Custom B)"
                b.setdefault("stats", {})
                for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr"]:
                    b["stats"][k] = float(custom_b[k])
                b["guard_q"] = float(custom_b["guard_q"])
                if custom_b["res"] > 0:
                    b.setdefault("res", {})
                    b["res"]["*"] = float(custom_b["res"])
                cfg["builds"][custom_id_b] = b
                actual_b = [custom_id_b]

            A = resolve_team(cfg, actual_a, "A")
            B = resolve_team(cfg, actual_b, "B")
            soft_check(cfg, A + B)

            agg, logs = run_batch(cfg, A, B, mode=mode, T=time_limit, runs=runs, seed=42)
            n = max(1, agg.n)
            wa, wb, wd = agg.wins["A"], agg.wins["B"], agg.wins[None]

            out_text = f"=== KẾT QUẢ: {team_a_id} vs {team_b_id} ({runs} lượt, {mode.upper()}) ===\n"
            out_text += f"Đội A thắng: {pct(wa / n, 1)} ({wa}) | Đội B thắng: {pct(wb / n, 1)} ({wb}) | Hòa: {pct(wd / n, 1)} ({wd})\n"
            out_text += f"Damage Đội A: {agg.dmg['A'] / n:.0f} | Damage Đội B: {agg.dmg['B'] / n:.0f} | Thời gian trung bình: {sum(agg.t_end) / n:.1f}s"

            self.txt_sim_result.delete("1.0", "end")
            self.txt_sim_result.insert("1.0", out_text)
        except Exception as ex:
            self.txt_sim_result.delete("1.0", "end")
            self.txt_sim_result.insert("1.0", f"Lỗi mô phỏng: {ex}")

    def populate_category_tab(self, parent, items):
        canvas = tk.Canvas(parent, bg=self.colors["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors["bg"])

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        for item in items:
            path = item["path"]
            init_val = self.get_val(self.current_rules, path)
            if init_val is None:
                init_val = item["min"]

            var = tk.DoubleVar(value=init_val)
            self.slider_vars[path] = var

            row_frame = tk.Frame(scrollable_frame, bg=self.colors["card_bg"], padx=14, pady=8, highlightthickness=1, highlightbackground=self.colors["border"])
            row_frame.pack(fill="x", expand=True, padx=8, pady=4)

            top_box = tk.Frame(row_frame, bg=self.colors["card_bg"])
            top_box.pack(fill="x")

            lbl_name = tk.Label(top_box, text=item["label"], font=("Segoe UI", 9, "bold"), fg="#ffffff", bg=self.colors["card_bg"])
            lbl_name.pack(side="left")

            lbl_key = tk.Label(top_box, text=f"({path})", font=("Consolas", 8), fg="#64748b", bg=self.colors["card_bg"])
            lbl_key.pack(side="left", padx=8)

            lbl_val_display = tk.Label(top_box, text=self.format_display(init_val, item), font=("Segoe UI", 9, "bold"), fg=self.colors["accent"], bg=self.colors["card_bg"])
            lbl_val_display.pack(side="right")

            ctrl_box = tk.Frame(row_frame, bg=self.colors["card_bg"])
            ctrl_box.pack(fill="x", pady=4)

            tk.Label(ctrl_box, text=f"{item['min']}", font=("Segoe UI", 8), fg="#64748b", bg=self.colors["card_bg"]).pack(side="left", padx=2)
            scale = ttk.Scale(ctrl_box, from_=item["min"], to=item["max"], variable=var, orient="horizontal")
            scale.pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(ctrl_box, text=f"{item['max']}", font=("Segoe UI", 8), fg="#64748b", bg=self.colors["card_bg"]).pack(side="left", padx=2)

            entry = tk.Entry(ctrl_box, width=7, bg="#111522", fg="#ffffff", insertbackground="#ffffff", relief="solid", justify="right", font=("Segoe UI", 9))
            entry.pack(side="left", padx=8)
            entry.insert(0, str(init_val))

            tk.Label(ctrl_box, text=item["unit"], font=("Segoe UI", 8), fg=self.colors["muted"], bg=self.colors["card_bg"], width=5).pack(side="left")

            btn_reset_one = tk.Button(ctrl_box, text="↺", font=("Segoe UI", 8), bg="#222b40", fg="#94a3b8", relief="flat", cursor="hand2",
                                      command=lambda p=path, e=entry, lbl=lbl_val_display, meta=item: self.reset_single(p, e, lbl, meta))
            btn_reset_one.pack(side="left", padx=2)

            desc_lbl = tk.Label(row_frame, text=item["desc"], font=("Segoe UI", 8), fg=self.colors["muted"], bg=self.colors["card_bg"], wraplength=760, justify="left")
            desc_lbl.pack(anchor="w")

            def make_callbacks(p, meta, v, ent, dlbl):
                def on_scale(val):
                    fval = round(float(val) / meta["step"]) * meta["step"]
                    if meta.get("format") == "int":
                        fval = int(round(fval))
                    else:
                        fval = round(fval, 3)
                    self.set_val(self.current_rules, p, fval)
                    ent.delete(0, "end")
                    ent.insert(0, str(fval))
                    dlbl.config(text=self.format_display(fval, meta))
                    self.update_diff_status()

                def on_entry(event=None):
                    try:
                        fval = float(ent.get())
                        fval = max(meta["min"], min(meta["max"], fval))
                        v.set(fval)
                        on_scale(fval)
                    except ValueError:
                        pass
                return on_scale, on_entry

            sc_cb, ent_cb = make_callbacks(path, item, var, entry, lbl_val_display)
            scale.configure(command=sc_cb)
            entry.bind("<Return>", ent_cb)
            entry.bind("<FocusOut>", ent_cb)

    def format_display(self, v, meta):
        fmt = meta.get("format")
        if fmt == "percent":
            return f"{round(v * 100)}%"
        if fmt == "percent_fine":
            return f"{round(v * 100, 1)}%"
        if fmt == "int":
            return f"{int(round(v))} {meta['unit']}"
        return f"{round(v, 2)} {meta['unit']}"

    def reset_single(self, path, entry, dlbl, meta):
        base = self.get_val(self.baseline_rules, path)
        if base is not None:
            self.set_val(self.current_rules, path, base)
            self.slider_vars[path].set(base)
            entry.delete(0, "end")
            entry.insert(0, str(base))
            dlbl.config(text=self.format_display(base, meta))
            self.update_diff_status()

    def update_diff_status(self):
        count = 0
        for m in SLIDERS_META:
            cur = self.get_val(self.current_rules, m["path"])
            base = self.get_val(self.baseline_rules, m["path"])
            if cur is not None and base is not None and abs(cur - base) > 0.00001:
                count += 1
        self.lbl_diff_count.config(text=f"{count} chỉ số đã đổi")

    def save_config(self):
        try:
            save_rules(self.current_rules)
            self.baseline_rules = copy.deepcopy(self.current_rules)
            self.update_diff_status()
            messagebox.showinfo("Thành công", "Đã lưu toàn bộ cấu hình mới vào config/rules.json!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu: {e}")

    def reset_all(self):
        if not messagebox.askyesno("Xác nhận", "Khôi phục toàn bộ các thanh trượt về cấu hình mặc định?"):
            return
        self.current_rules = copy.deepcopy(self.baseline_rules)
        self.destroy()
        app = IOMGymGUI()
        app.mainloop()

    def copy_cli(self):
        sets = []
        for m in SLIDERS_META:
            cur = self.get_val(self.current_rules, m["path"])
            base = self.get_val(self.baseline_rules, m["path"])
            if cur is not None and base is not None and abs(cur - base) > 0.00001:
                sets.append(f"--set {m['path']}={cur}")

        if not sets:
            messagebox.showinfo("Thông báo", "Không có chỉ số nào khác với mặc định.")
            return

        cmd = " ".join(sets)
        self.clipboard_clear()
        self.clipboard_append(cmd)
        messagebox.showinfo("Đã sao chép", f"Đã sao chép {len(sets)} tham số --set vào Clipboard!\nBạn có thể dán vào lệnh python gym.py.")


def main():
    app = IOMGymGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
