# -*- coding: utf-8 -*-
"""
IOM GYM - Ứng dụng Desktop Windows (Giao diện đen trắng tối giản).
Hỗ trợ:
1. Chọn chế độ trước (Fight: 1v1; DPS: thêm tối đa 6 Dummy, MỖI DUMMY ĐỀU CUSTOM ĐƯỢC CHỈ SỐ NHƯ BÊN A).
2. Tab Advanced: Chỉnh sửa công thức tính damage (Raw, Defense, Resistance) kèm sandbox thử nghiệm.
3. Khung log kết quả mở rộng chiều đứng, co giãn linh hoạt, thanh cuộn mượt mà.
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


DEFAULT_FORMULAS = {
    "raw_expr": "(atk + base) * damage_mult",
    "def_k": 100.0,
    "def_expr": "d / (def_k + d)",
    "res_expr": "1 - min(r, caps_res) if r >= 0 else 1 - r / 2"
}

ELEMENT_CATEGORY_NAMES = {
    "amgar": "NHAM (AMGAR - MOLTEN CORE)",
    "glacia": "BĂNG (GLACIA - FRIGID CORE)",
    "cruor": "HUYẾT (CRUOR - BLOOD LOSS)",
    "ether": "LINH (ETHER - VAGUE DRAIN)",
    "gale": "PHONG (GALE - ZEPHYR CORE)",
    "fulgur": "LÔI (FULGUR - FULGUR CHAIN)",
    "sable": "CÁT (SABLE - SHADOW SCREEP)",
    "entropy": "HỖN LOẠN (ENTROPY - ERUPTIVE CORE)",
    "timeflow": "THỜI GIAN (TIMEFLOW - CHRONOMANCY)",
    "agenet": "KIM (AGENET - BREAK & STURD)",
    "elements": "NGUYÊN TỐ THỦY(WET & REACTION)",
    "combat": "QUY TẮC CHIẾN ĐẤU CHUNG (COMBAT RULES)",
}

ELEMENT_DISPLAY_MAP = {
    "Amgar": "Nham (Amgar)",
    "Glacia": "Băng (Glacia)",
    "Cruor": "Huyết (Cruor)",
    "Ether": "Linh (Ether)",
    "Gale": "Phong (Gale)",
    "Fulgur": "Lôi (Fulgur)",
    "Sable": "Cát (Sable)",
    "Entropy": "Hỗn Loạn (Entropy)",
    "TimeFlow": "Thời Gian (TimeFlow)",
    "Agenet": "Kim (Agenet)",
    "Aqua": "Thủy (Aqua)",
    "Sylva": "Mộc (Sylva)",
    "Petra": "Thổ (Petra)",
    "Ignis": "Hỏa (Ignis)",
}
ELEMENTS_LIST = list(ELEMENT_DISPLAY_MAP.keys())


class IOMGymMonoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IOM")
        self.geometry("1120x840")
        self.minsize(980, 700)

        # Bảng màu đen trắng tối giản
        self.c_bg = "#121212"
        self.c_surface = "#1a1a1a"
        self.c_sub = "#242424"
        self.c_border = "#3a3a3a"
        self.c_fg = "#ffffff"
        self.c_muted = "#a0a0a0"
        self.c_dim = "#666666"

        self.configure(bg=self.c_bg)

        self.current_rules = get_current_rules()
        self.baseline_rules = get_baseline_rules()
        self.slider_vars = {}

        self.team_a_vars = {}
        self.team_b_fight_vars = {}
        self.target_type_b = tk.StringVar(value="build")

        # Cấu trúc lưu trữ nhiều Dummy trong chế độ DPS (tối đa 6 dummy)
        # Mỗi phần tử: {"base_id": "dummy:std", "stats": {...}}
        self.cfg = load_cfg()
        init_stats = get_entity_default_stats(self.cfg, "dummy:std")
        self.dps_dummies = [
            {"base_id": "dummy:std", "stats": dict(init_stats)}
        ]
        self.current_dps_idx = 0
        self.dps_dummy_vars = {}

        # Hệ thống Scenario (Kịch bản 1v1 người chơi)
        self.current_scenario_key = tk.StringVar(value="equal_standard")
        self.scen_player_vars = {"team_a": {}, "team_b": {}}
        self.editing_scenario_key = None

        # Hệ thống Build Preset (Tùy biến & Lưu trữ Preset)
        self.build_presets_path = os.path.join(HERE, "config", "build_presets.json")
        self.build_presets = self.load_build_presets()
        self.selected_relics_a = []
        self.selected_relics_b = []
        self.current_preset_key_a = tk.StringVar(value="(Tùy chỉnh)")
        self.current_preset_key_b = tk.StringVar(value="(Tùy chỉnh)")
        self.editing_preset_key = None
        self.preset_form_vars = {}
        self.preset_form_relics = set()

        # Hệ thống Relic & Nội Tại Custom
        self.editing_relic_key = None
        self.relic_search_var = tk.StringVar()
        self.relic_filter_type = tk.StringVar(value="all")

        self.setup_styles()
        self.build_ui()
        self.update_diff_status()

    def setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=self.c_bg, foreground=self.c_fg)
        style.configure("TNotebook", background=self.c_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background="#222222", foreground="#cccccc",
                        padding=[14, 6], font=("Segoe UI", 9, "bold"), borderwidth=1)
        style.map("TNotebook.Tab",
                  background=[("selected", "#383838")],
                  foreground=[("selected", "#ffffff")])

        style.configure("TFrame", background=self.c_bg)
        style.configure("TLabel", background=self.c_bg, foreground=self.c_fg, font=("Segoe UI", 9))
        style.configure("Muted.TLabel", foreground=self.c_muted, font=("Segoe UI", 8))
        style.configure("TCombobox", fieldbackground="#1e1e1e", background="#333333", foreground="#ffffff")
        style.configure("TScale", background=self.c_surface, troughcolor="#2c2c2c")

        style.configure("Treeview",
                        background="#1a1a1a",
                        foreground="#ffffff",
                        fieldbackground="#1a1a1a",
                        borderwidth=0,
                        rowheight=24,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background="#2a2a2a",
                        foreground="#ffffff",
                        borderwidth=1,
                        relief="flat",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", "#383838")],
                  foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading",
                  background=[("active", "#333333")])

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
        header = tk.Frame(self, bg=self.c_surface, pady=8, padx=16,
                          highlightthickness=1, highlightbackground=self.c_border)
        header.pack(fill="x", side="top")

        lbl_title = tk.Label(header, text="IOM GYM  |  BỘ CÂN BẰNG HIỆU ỨNG",
                             font=("Segoe UI", 12, "bold"), fg=self.c_fg, bg=self.c_surface)
        lbl_title.pack(side="left")

        self.lbl_diff_count = tk.Label(header, text="0 chỉ số đã đổi",
                                       font=("Segoe UI", 9, "bold"),
                                       fg="#ffffff", bg="#2a2a2a", padx=8, pady=2,
                                       relief="solid", bd=1)
        self.lbl_diff_count.pack(side="left", padx=16)

        btn_save = tk.Button(header, text="💾 Lưu Cấu Hình", bg="#ffffff", fg="#000000",
                             font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4,
                             cursor="hand2", activebackground="#dddddd", command=self.save_config)
        btn_save.pack(side="right", padx=4)

        btn_reset = tk.Button(header, text="↺ Khôi Phục Gốc", bg="#282828", fg="#ffffff",
                              font=("Segoe UI", 9), relief="solid", bd=1, padx=10, pady=4,
                              cursor="hand2", activebackground="#383838", command=self.reset_all)
        btn_reset.pack(side="right", padx=4)

        btn_copy_cli = tk.Button(header, text="📋 Sao Chép --set", bg="#282828", fg="#ffffff",
                                 font=("Segoe UI", 9), relief="solid", bd=1, padx=10, pady=4,
                                 cursor="hand2", activebackground="#383838", command=self.copy_cli)
        btn_copy_cli.pack(side="right", padx=4)

        # 2. Main Tabbed Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        # TAB 1: THỬ NGHIỆM ĐẤU
        tab_combat = ttk.Frame(self.notebook)
        self.notebook.add(tab_combat, text="  ⚔  THỬ NGHIỆM ĐẤU  ")
        self.build_combat_tab(tab_combat)

        # TAB 2: CHỈ SỐ HIỆU ỨNG (RULES & PASSIVES)
        tab_rules = ttk.Frame(self.notebook)
        self.notebook.add(tab_rules, text="  ⚙  CHỈ SỐ HIỆU ỨNG  ")
        self.build_rules_tab(tab_rules)

        # TAB 3: ADVANCED (CÔNG THỨC DAMAGE & TÙY BIẾN)
        tab_adv = ttk.Frame(self.notebook)
        self.notebook.add(tab_adv, text="  ⚡  ADVANCED (CÔNG THỨC)  ")
        self.build_advanced_tab(tab_adv)

        # TAB 4: CUSTOM & EDIT SKILLS (QUẢN LÝ, TẠO MỚI & SỬA SKILL)
        tab_skills = ttk.Frame(self.notebook)
        self.notebook.add(tab_skills, text="  🛠  CUSTOM & EDIT SKILLS  ")
        self.build_skills_tab(tab_skills)

        # TAB 5: KỊCH BẢN 1v1 (SCENARIOS & HỒ SƠ NGƯỜI CHƠI)
        tab_scen = ttk.Frame(self.notebook)
        self.notebook.add(tab_scen, text="  📋  KỊCH BẢN 1v1 (SCENARIOS)  ")
        self.build_scenario_tab(tab_scen)

        # TAB 6: PRESET BUILDS (TÙY BIẾN & LƯU TRỮ PRESET)
        tab_presets = ttk.Frame(self.notebook)
        self.notebook.add(tab_presets, text="  📦  PRESET BUILDS  ")
        self.build_preset_tab(tab_presets)

        # TAB 7: CUSTOM RELICS & NỘI TẠI
        tab_relics = ttk.Frame(self.notebook)
        self.notebook.add(tab_relics, text="  💎  CUSTOM RELICS & NỘI TẠI  ")
        self.build_relics_tab(tab_relics)

    # -------------------------------------------------------------------------
    # TAB 1: THỬ NGHIỆM ĐẤU (CHỌN CHẾ ĐỘ TRƯỚC, DPS TỐI ĐA 6 DUMMY VÀ CUSTOM ĐƯỢC HẾT)
    # -------------------------------------------------------------------------
    def build_combat_tab(self, parent):
        # 1. HÀNG ĐẦU TIÊN: CHỌN CHẾ ĐỘ TRƯỚC (FIGHT / DPS)
        mode_bar = tk.Frame(parent, bg=self.c_surface, pady=8, padx=14,
                            highlightthickness=1, highlightbackground=self.c_border)
        mode_bar.pack(fill="x", side="top", padx=8, pady=(4, 6))

        tk.Label(mode_bar, text="CHẾ ĐỘ MÔ PHỎNG:", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_surface).pack(side="left", padx=(0, 10))

        self.mode_var = tk.StringVar(value="fight")

        rb_fight = tk.Radiobutton(mode_bar, text=" FIGHT MODE ", variable=self.mode_var,
                                  value="fight", bg=self.c_surface, fg="#ffffff", selectcolor="#000000",
                                  activebackground=self.c_surface, activeforeground="#ffffff",
                                  font=("Segoe UI", 9, "bold"), cursor="hand2", command=self.on_mode_change)
        rb_fight.pack(side="left", padx=8)

        rb_dps = tk.Radiobutton(mode_bar, text=" DPS MODE ",
                                variable=self.mode_var, value="dps", bg=self.c_surface, fg="#ffffff", selectcolor="#000000",
                                activebackground=self.c_surface, activeforeground="#ffffff",
                                font=("Segoe UI", 9, "bold"), cursor="hand2", command=self.on_mode_change)
        rb_dps.pack(side="left", padx=8)

        # Match params
        self.frame_time_dps = tk.Frame(mode_bar, bg=self.c_surface)

        self.lbl_time_desc = tk.Label(self.frame_time_dps, text="|  Thời gian:", bg=self.c_surface, fg=self.c_muted)
        self.lbl_time_desc.pack(side="left", padx=(0, 4))
        self.sp_time = ttk.Spinbox(self.frame_time_dps, from_=10, to=300, width=5)
        self.sp_time.set("60")
        self.sp_time.pack(side="left")
        self.lbl_time_unit = tk.Label(self.frame_time_dps, text="giây", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 8))
        self.lbl_time_unit.pack(side="left", padx=(2, 6))

        self.lbl_fight_mode_notice = tk.Label(mode_bar, text="|  Thời gian: Sinh tử (Đến khi có bên thua)",
                                              bg=self.c_surface, fg="#00e676", font=("Segoe UI", 9, "bold"))
        self.lbl_fight_mode_notice.pack(side="left", padx=(8, 8))

        self.lbl_runs_desc = tk.Label(mode_bar, text="Số trận (runs):", bg=self.c_surface, fg=self.c_muted)
        self.lbl_runs_desc.pack(side="left", padx=(8, 4))
        self.sp_runs = ttk.Spinbox(mode_bar, from_=5, to=300, width=5)
        self.sp_runs.set("50")
        self.sp_runs.pack(side="left")

        btn_run = tk.Button(mode_bar, text="▶  BẮT ĐẦU MÔ PHỎNG", bg="#ffffff", fg="#000000",
                            font=("Segoe UI", 9, "bold"), relief="flat", padx=18, pady=3,
                            cursor="hand2", activebackground="#dddddd", command=self.run_simulation)
        btn_run.pack(side="right", padx=4)

        # 1.5. HÀNG KỊCH BẢN CHIẾN ĐẤU (CHỈ HOẠT ĐỘNG Ở CHẾ ĐỘ FIGHT GIỮA 2 ĐỘI)
        self.build_scenario_bar(parent)

        # 2. KHUNG CHÍNH (CỘT ĐỘI A VÀ CỘT ĐỘI B)
        self.combat_split = tk.Frame(parent, bg=self.c_bg)
        self.combat_split.pack(fill="x", padx=8, pady=2)

        # Cột Trái: Đội A
        self.frame_a = tk.LabelFrame(self.combat_split, text=" [ ĐỘI A - BUILD ] ",
                                     font=("Segoe UI", 9, "bold"), fg=self.c_fg, bg=self.c_surface,
                                     padx=8, pady=6, bd=1, relief="solid")
        self.frame_a.pack(side="left", fill="both", expand=True, padx=4)

        # Hàng 1: Chọn 2 Nguyên Tố tạo Build
        top_a = tk.Frame(self.frame_a, bg=self.c_surface)
        top_a.pack(fill="x", pady=2)

        tk.Label(top_a, text="Nhánh 1:", bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.cb_elem1_a = ttk.Combobox(top_a, values=ELEMENTS_LIST, width=9, state="readonly")
        self.cb_elem1_a.set("Amgar")
        self.cb_elem1_a.pack(side="left", padx=2)
        self.cb_elem1_a.bind("<<ComboboxSelected>>", lambda e: self.on_elem_change_a())

        btn_swap_a = tk.Button(top_a, text="⇄", font=("Segoe UI", 8, "bold"),
                               bg="#262626", fg="#ffffff", relief="solid", bd=1, padx=4,
                               cursor="hand2", command=self.swap_elements_a)
        btn_swap_a.pack(side="left", padx=2)

        tk.Label(top_a, text="Nhánh 2:", bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(3, 0))
        self.cb_elem2_a = ttk.Combobox(top_a, values=ELEMENTS_LIST, width=9, state="readonly")
        self.cb_elem2_a.set("Gale")
        self.cb_elem2_a.pack(side="left", padx=2)
        self.cb_elem2_a.bind("<<ComboboxSelected>>", lambda e: self.on_elem_change_a())

        btn_pure_a = tk.Button(top_a, text="★ Pure", font=("Segoe UI", 7, "bold"),
                               bg="#333333", fg="#ffffff", relief="solid", bd=1, padx=4,
                               cursor="hand2", command=self.make_pure_a)
        btn_pure_a.pack(side="left", padx=2)

        btn_rst_a = tk.Button(top_a, text="↺ Gốc", font=("Segoe UI", 7),
                              bg="#242424", fg="#aaaaaa", relief="solid", bd=1, padx=4,
                              cursor="hand2", command=self.reset_stats_a)
        btn_rst_a.pack(side="left", padx=2)

        # Hàng 2: Trạng thái Loại Build & Presets
        status_row_a = tk.Frame(self.frame_a, bg=self.c_surface)
        status_row_a.pack(fill="x", pady=2)

        self.lbl_status_a = tk.Label(status_row_a, text="", font=("Segoe UI", 8, "bold"),
                                     bg="#222222", fg="#ffffff", padx=6, pady=1, relief="solid", bd=1)
        self.lbl_status_a.pack(side="left", padx=(0, 4))

        for p_name, p_key in [("Dồn Dame", "dps"), ("Pháp Sư", "caster"), ("Đỡ Đòn", "tank")]:
            tk.Button(status_row_a, text=p_name, font=("Segoe UI", 7),
                      bg="#262626", fg="#dddddd", relief="solid", bd=1, padx=4,
                      command=lambda k=p_key: self.apply_preset_a(k)).pack(side="left", padx=2)

        # Hàng Preset & Relics cho Đội A
        p_row_a = tk.Frame(self.frame_a, bg="#1e1e1e", padx=6, pady=3, relief="solid", bd=1)
        p_row_a.pack(fill="x", pady=(2, 3))

        tk.Label(p_row_a, text="📦 Preset:", font=("Segoe UI", 8, "bold"),
                 bg="#1e1e1e", fg="#ffffff").pack(side="left", padx=(0, 4))
        p_names_init_a = ["(Tùy chỉnh)"] + [p.get("name", pid) for pid, p in self.build_presets.items()]
        self.cb_preset_a = ttk.Combobox(p_row_a, values=p_names_init_a, width=13, state="readonly")
        self.cb_preset_a.set("(Tùy chỉnh)")
        self.cb_preset_a.pack(side="left", padx=2)
        self.cb_preset_a.bind("<<ComboboxSelected>>", lambda e: self.on_select_preset_a())

        self.btn_relics_a = tk.Button(p_row_a, text="🛡 Relics: 0", font=("Segoe UI", 7, "bold"),
                                      bg="#2a2a2a", fg="#00e676", relief="solid", bd=1, padx=5,
                                      cursor="hand2", command=self.open_relics_dialog_a)
        self.btn_relics_a.pack(side="left", padx=3)

        btn_save_p_a = tk.Button(p_row_a, text="💾 Lưu Preset...", font=("Segoe UI", 7),
                                 bg="#242424", fg="#dddddd", relief="solid", bd=1, padx=4,
                                 cursor="hand2", command=self.save_current_as_preset_a)
        btn_save_p_a.pack(side="right", padx=2)

        # KHUNG LOADOUT KỸ NĂNG (5 SKILLS)
        self.box_loadout_a = tk.LabelFrame(self.frame_a, text=" [ LOADOUT KỸ NĂNG (5 SKILLS) ] ",
                                           font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface,
                                           padx=6, pady=4, bd=1, relief="solid")
        self.box_loadout_a.pack(fill="x", pady=2)

        r1_a = tk.Frame(self.box_loadout_a, bg=self.c_surface)
        r1_a.pack(fill="x", pady=1)

        self.lbl_l1_a = tk.Label(r1_a, text="Nhánh 1:", width=9, anchor="w",
                                 bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_l1_a.pack(side="left")

        tk.Label(r1_a, text="Basic:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_basic_a = ttk.Combobox(r1_a, width=12, state="readonly")
        self.cb_basic_a.pack(side="left", padx=(1, 3))
        self.cb_basic_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        tk.Label(r1_a, text="S1:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s1_a = ttk.Combobox(r1_a, width=11, state="readonly")
        self.cb_s1_a.pack(side="left", padx=(1, 3))
        self.cb_s1_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        tk.Label(r1_a, text="S2:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s2_a = ttk.Combobox(r1_a, width=11, state="readonly")
        self.cb_s2_a.pack(side="left", padx=(1, 2))
        self.cb_s2_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        r2_a = tk.Frame(self.box_loadout_a, bg=self.c_surface)
        r2_a.pack(fill="x", pady=1)

        self.lbl_l2_a = tk.Label(r2_a, text="Nhánh 2:", width=9, anchor="w",
                                 bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_l2_a.pack(side="left")

        tk.Label(r2_a, text="S3:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s3_a = ttk.Combobox(r2_a, width=11, state="readonly")
        self.cb_s3_a.pack(side="left", padx=(1, 3))
        self.cb_s3_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        tk.Label(r2_a, text="S4:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s4_a = ttk.Combobox(r2_a, width=11, state="readonly")
        self.cb_s4_a.pack(side="left", padx=(1, 3))
        self.cb_s4_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        tk.Label(r2_a, text="S5:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s5_a = ttk.Combobox(r2_a, width=11, state="readonly")
        self.cb_s5_a.pack(side="left", padx=(1, 2))
        self.cb_s5_a.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_a())

        btn_rst_loadout_a = tk.Button(r2_a, text="↺", font=("Segoe UI", 7),
                                      bg="#242424", fg="#aaaaaa", relief="solid", bd=1, padx=3,
                                      cursor="hand2", command=self.reset_loadout_a)
        btn_rst_loadout_a.pack(side="left", padx=2)

        self.box_sliders_a = tk.Frame(self.frame_a, bg=self.c_surface)
        self.box_sliders_a.pack(fill="both", expand=True, pady=2)
        self.populate_team_sliders("a", self.box_sliders_a, self.team_a_vars)
        self.on_elem_change_a()

        # Cột Phải: Container chứa hoặc Đội B đơn lẻ (Fight) hoặc Danh Sách Nhiều Dummy Custom (DPS)
        self.frame_b_container = tk.Frame(self.combat_split, bg=self.c_bg)
        self.frame_b_container.pack(side="left", fill="both", expand=True, padx=4)

        # Xây dựng cả 2 giao diện cho Đội B
        self.build_team_b_fight_view()
        self.build_team_b_dps_view()

        # Khởi tạo hiển thị theo mode mặc định (fight)
        self.on_mode_change()

        # 3. KHUNG LOG KẾT QUẢ MỞ RỘNG CHIỀU ĐỨNG
        res_frame = tk.LabelFrame(parent, text=" [ KẾT QUẢ MÔ PHỎNG ] ",
                                  font=("Segoe UI", 9, "bold"), fg=self.c_fg, bg=self.c_surface,
                                  padx=8, pady=4, bd=1, relief="solid")
        res_frame.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        scroll_res = ttk.Scrollbar(res_frame, orient="vertical")
        self.txt_sim_result = tk.Text(res_frame, height=14, bg="#0d0d0d", fg="#f0f0f0",
                                      font=("Consolas", 9), relief="solid", bd=1,
                                      padx=8, pady=6, yscrollcommand=scroll_res.set)
        scroll_res.config(command=self.txt_sim_result.yview)
        scroll_res.pack(side="right", fill="y")
        self.txt_sim_result.pack(side="left", fill="both", expand=True)

        self.txt_sim_result.insert("1.0", "Chọn chế độ (Fight hoặc DPS), tinh chỉnh build/dummy và nhấn 'BẮT ĐẦU MÔ PHỎNG'.\nLog kết quả chi tiết từng mục tiêu sẽ xuất hiện ở đây.")

    # -------------------------------------------------------------------------
    # HÀNG KỊCH BẢN 1v1 (CHỈ HOẠT ĐỘNG Ở CHẾ ĐỘ FIGHT)
    # -------------------------------------------------------------------------
    def build_scenario_bar(self, parent):
        self.scenario_bar = tk.Frame(parent, bg=self.c_sub, pady=6, padx=12,
                                     highlightthickness=1, highlightbackground=self.c_border)
        self.scenario_bar.pack(fill="x", side="top", padx=8, pady=(0, 6))

        top_row = tk.Frame(self.scenario_bar, bg=self.c_sub)
        top_row.pack(fill="x")

        tk.Label(top_row, text="📋 KỊCH BẢN 1v1:", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(side="left", padx=(0, 8))

        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        self.scenario_keys = list(scens_dict.keys())
        scen_display_vals = [f"{scens_dict[k].get('name', k)}" for k in self.scenario_keys]

        self.cb_scenario = ttk.Combobox(top_row, values=scen_display_vals, width=44, state="readonly", font=("Segoe UI", 9))
        if scen_display_vals:
            self.cb_scenario.current(0)
            self.current_scenario_key.set(self.scenario_keys[0])
        self.cb_scenario.pack(side="left", padx=(0, 8))
        self.cb_scenario.bind("<<ComboboxSelected>>", self.on_scenario_bar_select)

        btn_edit_scen = tk.Button(top_row, text="⚙ Chi Tiết / Sửa Kịch Bản", font=("Segoe UI", 8, "bold"),
                                  bg="#2a2a2a", fg="#ffffff", relief="solid", bd=1, padx=10, pady=2,
                                  cursor="hand2", activebackground="#3d3d3d", command=self.open_scenario_tab)
        btn_edit_scen.pack(side="left", padx=4)

        # Hàng tóm tắt hồ sơ người chơi
        bot_row = tk.Frame(self.scenario_bar, bg=self.c_sub)
        bot_row.pack(fill="x", pady=(4, 0))

        self.lbl_scen_p_a = tk.Label(bot_row, text="", font=("Segoe UI", 8),
                                     bg="#181818", fg="#ffffff", relief="solid", bd=1, padx=6, pady=2)
        self.lbl_scen_p_a.pack(side="left", padx=(0, 6))

        self.lbl_scen_p_b = tk.Label(bot_row, text="", font=("Segoe UI", 8),
                                     bg="#181818", fg="#ffffff", relief="solid", bd=1, padx=6, pady=2)
        self.lbl_scen_p_b.pack(side="left")

        self.update_scenario_bar_badges()

    def on_scenario_bar_select(self, event=None):
        idx = self.cb_scenario.current()
        if 0 <= idx < len(self.scenario_keys):
            self.current_scenario_key.set(self.scenario_keys[idx])
            self.update_scenario_bar_badges()
            if hasattr(self, "lb_scenarios"):
                try:
                    self.lb_scenarios.selection_clear(0, "end")
                    self.lb_scenarios.selection_set(idx)
                    self.on_scenario_list_select()
                except Exception:
                    pass

    def update_scenario_bar_badges(self):
        scen_k = self.current_scenario_key.get()
        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        scen = scens_dict.get(scen_k, {})
        if not scen and scens_dict:
            scen_k = list(scens_dict.keys())[0]
            scen = scens_dict[scen_k]
            self.current_scenario_key.set(scen_k)

        pa = scen.get("team_a", {})
        pb = scen.get("team_b", {})

        rt_a = pa.get("reaction_time", 0.22) * 1000
        dg_a = pa.get("dodge", {}).get("rate", 0.40) * 100
        py_a = pa.get("parry", {}).get("rate", 0.20) * 100
        cp_a = pa.get("psychology", {}).get("composure", 0.60) * 100
        rank_a = pa.get("rank_title", "Đội A")

        rt_b = pb.get("reaction_time", 0.22) * 1000
        dg_b = pb.get("dodge", {}).get("rate", 0.40) * 100
        py_b = pb.get("parry", {}).get("rate", 0.20) * 100
        cp_b = pb.get("psychology", {}).get("composure", 0.60) * 100
        rank_b = pb.get("rank_title", "Đội B")

        self.lbl_scen_p_a.config(text=f"[A] {rank_a}: Phản xạ {rt_a:.0f}ms | Né {dg_a:.0f}% | Parry {py_a:.0f}% | Tâm lý {cp_a:.0f}%")
        self.lbl_scen_p_b.config(text=f"[B] {rank_b}: Phản xạ {rt_b:.0f}ms | Né {dg_b:.0f}% | Parry {py_b:.0f}% | Tâm lý {cp_b:.0f}%")

    def open_scenario_tab(self):
        self.notebook.select(4)

    def refresh_combat_tab_scenarios(self):
        if not hasattr(self, "cb_scenario"):
            return
        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        self.scenario_keys = list(scens_dict.keys())
        scen_display_vals = [f"{scens_dict[k].get('name', k)}" for k in self.scenario_keys]
        self.cb_scenario["values"] = scen_display_vals

        cur_k = self.current_scenario_key.get()
        if cur_k in self.scenario_keys:
            self.cb_scenario.current(self.scenario_keys.index(cur_k))
        elif self.scenario_keys:
            self.cb_scenario.current(0)
            self.current_scenario_key.set(self.scenario_keys[0])

        self.update_scenario_bar_badges()

    # --- Đội B khi ở chế độ FIGHT (1v1) ---
    def build_team_b_fight_view(self):
        self.frame_b_fight = tk.LabelFrame(self.frame_b_container, text=" [ ĐỘI B - BUILD (1v1) ] ",
                                           font=("Segoe UI", 9, "bold"), fg=self.c_fg, bg=self.c_surface,
                                           padx=8, pady=6, bd=1, relief="solid")

        # Hàng 1: Chế độ Build vs Dummy & Selector
        top_b = tk.Frame(self.frame_b_fight, bg=self.c_surface)
        top_b.pack(fill="x", pady=2)

        rb_b_build = tk.Radiobutton(top_b, text="Build:", variable=self.target_type_b, value="build",
                                    font=("Segoe UI", 8, "bold"), fg="#ffffff", bg=self.c_surface,
                                    selectcolor="#000000", activebackground=self.c_surface,
                                    command=self.on_toggle_b_type)
        rb_b_build.pack(side="left")

        self.frame_b_elems = tk.Frame(top_b, bg=self.c_surface)
        self.frame_b_elems.pack(side="left")

        self.cb_elem1_b = ttk.Combobox(self.frame_b_elems, values=ELEMENTS_LIST, width=9, state="readonly")
        self.cb_elem1_b.set("Glacia")
        self.cb_elem1_b.pack(side="left", padx=2)
        self.cb_elem1_b.bind("<<ComboboxSelected>>", lambda e: self.on_elem_change_b())

        btn_swap_b = tk.Button(self.frame_b_elems, text="⇄", font=("Segoe UI", 8, "bold"),
                               bg="#262626", fg="#ffffff", relief="solid", bd=1, padx=3,
                               cursor="hand2", command=self.swap_elements_b)
        btn_swap_b.pack(side="left", padx=2)

        self.cb_elem2_b = ttk.Combobox(self.frame_b_elems, values=ELEMENTS_LIST, width=9, state="readonly")
        self.cb_elem2_b.set("Glacia")
        self.cb_elem2_b.pack(side="left", padx=2)
        self.cb_elem2_b.bind("<<ComboboxSelected>>", lambda e: self.on_elem_change_b())

        btn_pure_b = tk.Button(self.frame_b_elems, text="★ Pure", font=("Segoe UI", 7, "bold"),
                               bg="#333333", fg="#ffffff", relief="solid", bd=1, padx=3,
                               cursor="hand2", command=self.make_pure_b)
        btn_pure_b.pack(side="left", padx=2)

        rb_b_dummy = tk.Radiobutton(top_b, text="Dummy:", variable=self.target_type_b, value="dummy",
                                    font=("Segoe UI", 8, "bold"), fg="#ffffff", bg=self.c_surface,
                                    selectcolor="#000000", activebackground=self.c_surface,
                                    command=self.on_toggle_b_type)
        rb_b_dummy.pack(side="left", padx=(5, 0))

        dummy_ids = ["dummy:" + k for k in self.cfg["scenarios"]["dummies"] if not k.startswith("_")]
        self.cb_dummy_b = ttk.Combobox(top_b, values=dummy_ids, width=12, state="disabled")
        self.cb_dummy_b.set(dummy_ids[0])
        self.cb_dummy_b.pack(side="left", padx=2)
        self.cb_dummy_b.bind("<<ComboboxSelected>>", lambda e: self.on_select_dummy_b())

        btn_rst_b = tk.Button(top_b, text="↺ Gốc", font=("Segoe UI", 7),
                              bg="#242424", fg="#aaaaaa", relief="solid", bd=1, padx=4,
                              cursor="hand2", command=self.reset_stats_b)
        btn_rst_b.pack(side="left", padx=2)

        # Hàng 2: Trạng thái Loại Build & Presets
        status_row_b = tk.Frame(self.frame_b_fight, bg=self.c_surface)
        status_row_b.pack(fill="x", pady=2)

        self.lbl_status_b = tk.Label(status_row_b, text="", font=("Segoe UI", 8, "bold"),
                                     bg="#222222", fg="#ffffff", padx=6, pady=1, relief="solid", bd=1)
        self.lbl_status_b.pack(side="left", padx=(0, 4))

        for p_name, p_val in [("Tank 1k", 1000), ("Tank 3k", 3000), ("Tank 10k", 10000)]:
            tk.Button(status_row_b, text=p_name, font=("Segoe UI", 7), bg="#262626", fg="#dddddd", relief="solid", bd=1, padx=4,
                      command=lambda v=p_val: self.apply_tank_preset_b(v)).pack(side="left", padx=2)

        # Hàng Preset & Relics cho Đội B
        self.preset_row_b = tk.Frame(self.frame_b_fight, bg="#1e1e1e", padx=6, pady=3, relief="solid", bd=1)
        self.preset_row_b.pack(fill="x", pady=(2, 3))

        tk.Label(self.preset_row_b, text="📦 Preset:", font=("Segoe UI", 8, "bold"),
                 bg="#1e1e1e", fg="#ffffff").pack(side="left", padx=(0, 4))
        p_names_init_b = ["(Tùy chỉnh)"] + [p.get("name", pid) for pid, p in self.build_presets.items()]
        self.cb_preset_b = ttk.Combobox(self.preset_row_b, values=p_names_init_b, width=13, state="readonly")
        self.cb_preset_b.set("(Tùy chỉnh)")
        self.cb_preset_b.pack(side="left", padx=2)
        self.cb_preset_b.bind("<<ComboboxSelected>>", lambda e: self.on_select_preset_b())

        self.btn_relics_b = tk.Button(self.preset_row_b, text="🛡 Relics: 0", font=("Segoe UI", 7, "bold"),
                                      bg="#2a2a2a", fg="#00e676", relief="solid", bd=1, padx=5,
                                      cursor="hand2", command=self.open_relics_dialog_b)
        self.btn_relics_b.pack(side="left", padx=3)

        btn_save_p_b = tk.Button(self.preset_row_b, text="💾 Lưu Preset...", font=("Segoe UI", 7),
                                 bg="#242424", fg="#dddddd", relief="solid", bd=1, padx=4,
                                 cursor="hand2", command=self.save_current_as_preset_b)
        btn_save_p_b.pack(side="right", padx=2)

        # KHUNG LOADOUT KỸ NĂNG CHO ĐỘI B (1v1)
        self.box_loadout_b = tk.LabelFrame(self.frame_b_fight, text=" [ LOADOUT KỸ NĂNG (5 SKILLS) ] ",
                                           font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface,
                                           padx=6, pady=4, bd=1, relief="solid")
        self.box_loadout_b.pack(fill="x", pady=2)

        r1_b = tk.Frame(self.box_loadout_b, bg=self.c_surface)
        r1_b.pack(fill="x", pady=1)

        self.lbl_l1_b = tk.Label(r1_b, text="Nhánh 1:", width=9, anchor="w",
                                 bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_l1_b.pack(side="left")

        tk.Label(r1_b, text="Basic:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_basic_b = ttk.Combobox(r1_b, width=12, state="readonly")
        self.cb_basic_b.pack(side="left", padx=(1, 3))
        self.cb_basic_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        tk.Label(r1_b, text="S1:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s1_b = ttk.Combobox(r1_b, width=11, state="readonly")
        self.cb_s1_b.pack(side="left", padx=(1, 3))
        self.cb_s1_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        tk.Label(r1_b, text="S2:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s2_b = ttk.Combobox(r1_b, width=11, state="readonly")
        self.cb_s2_b.pack(side="left", padx=(1, 2))
        self.cb_s2_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        r2_b = tk.Frame(self.box_loadout_b, bg=self.c_surface)
        r2_b.pack(fill="x", pady=1)

        self.lbl_l2_b = tk.Label(r2_b, text="Nhánh 2:", width=9, anchor="w",
                                 bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_l2_b.pack(side="left")

        tk.Label(r2_b, text="S3:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s3_b = ttk.Combobox(r2_b, width=11, state="readonly")
        self.cb_s3_b.pack(side="left", padx=(1, 3))
        self.cb_s3_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        tk.Label(r2_b, text="S4:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s4_b = ttk.Combobox(r2_b, width=11, state="readonly")
        self.cb_s4_b.pack(side="left", padx=(1, 3))
        self.cb_s4_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        tk.Label(r2_b, text="S5:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_s5_b = ttk.Combobox(r2_b, width=11, state="readonly")
        self.cb_s5_b.pack(side="left", padx=(1, 2))
        self.cb_s5_b.bind("<<ComboboxSelected>>", lambda e: self.on_skill_change_b())

        btn_rst_loadout_b = tk.Button(r2_b, text="↺", font=("Segoe UI", 7),
                                      bg="#242424", fg="#aaaaaa", relief="solid", bd=1, padx=3,
                                      cursor="hand2", command=self.reset_loadout_b)
        btn_rst_loadout_b.pack(side="left", padx=2)

        self.box_sliders_b = tk.Frame(self.frame_b_fight, bg=self.c_surface)
        self.box_sliders_b.pack(fill="both", expand=True, pady=2)
        self.populate_team_sliders("b", self.box_sliders_b, self.team_b_fight_vars)
        self.on_elem_change_b()

    # --- Đội B khi ở chế độ DPS (Tối đa 6 Dummy & TÙY CHỈNH CHỈ SỐ TỪNG DUMMY NHƯ BÊN A) ---
    def build_team_b_dps_view(self):
        self.frame_b_dps = tk.LabelFrame(self.frame_b_container,
                                         text=" [ TEAM B ] ",
                                         font=("Segoe UI", 9, "bold"), fg=self.c_fg, bg=self.c_surface,
                                         padx=8, pady=4, bd=1, relief="solid")

        # 1. Hàng chọn Dummy tab: [ Dummy #1 ] [ Dummy #2 ] ... [ + Thêm ]
        top_dps = tk.Frame(self.frame_b_dps, bg=self.c_surface)
        top_dps.pack(fill="x", pady=2)

        self.dps_tabs_frame = tk.Frame(top_dps, bg=self.c_surface)
        self.dps_tabs_frame.pack(side="left", fill="x", expand=True)

        self.btn_add_dummy = tk.Button(top_dps, text="+ Thêm Dummy", font=("Segoe UI", 8, "bold"),
                                       bg="#ffffff", fg="#000000", relief="flat", padx=8, pady=2,
                                       cursor="hand2", command=self.add_dps_dummy)
        self.btn_add_dummy.pack(side="right", padx=2)

        # 2. Hàng điều khiển Dummy hiện tại (Chọn phôi gốc, preset, copy all, delete)
        sub_dps = tk.Frame(self.frame_b_dps, bg="#202020", pady=3, padx=6, relief="solid", bd=1)
        sub_dps.pack(fill="x", pady=3)

        self.lbl_cur_dummy = tk.Label(sub_dps, text="Dummy #1:", font=("Segoe UI", 8, "bold"),
                                      fg="#ffffff", bg="#202020")
        self.lbl_cur_dummy.pack(side="left", padx=(0, 4))

        dummy_ids = ["dummy:" + k for k in self.cfg["scenarios"]["dummies"] if not k.startswith("_")]
        self.cb_dps_base = ttk.Combobox(sub_dps, values=dummy_ids, width=13, state="readonly")
        self.cb_dps_base.set("dummy:std")
        self.cb_dps_base.pack(side="left", padx=2)
        self.cb_dps_base.bind("<<ComboboxSelected>>", lambda e: self.on_change_dps_dummy_base())

        tk.Button(sub_dps, text="↺ Gốc", font=("Segoe UI", 7), bg="#2c2c2c", fg="#ffffff", relief="solid", bd=1,
                  command=self.on_change_dps_dummy_base).pack(side="left", padx=2)

        # Presets nhanh
        for p_name, p_def in [("Tank 1k", 1000), ("Tank 3k", 3000), ("Tank 10k", 10000)]:
            tk.Button(sub_dps, text=p_name, font=("Segoe UI", 7), bg="#262626", fg="#cccccc", relief="solid", bd=1,
                      command=lambda v=p_def: self.apply_dps_dummy_preset(v)).pack(side="left", padx=1)

        tk.Button(sub_dps, text="📦 Từ Preset...", font=("Segoe UI", 7, "bold"),
                  bg="#2a2a2a", fg="#ffffff", relief="solid", bd=1, padx=4,
                  command=self.apply_preset_to_current_dps_dummy).pack(side="left", padx=2)

        tk.Button(sub_dps, text="📋 Áp dụng cho ALL", font=("Segoe UI", 7, "bold"),
                  bg="#333333", fg="#ffffff", relief="solid", bd=1, padx=4,
                  command=self.copy_dps_stats_to_all).pack(side="left", padx=(6, 2))

        self.btn_del_dps_dummy = tk.Button(sub_dps, text="✕ Xóa Dummy", font=("Segoe UI", 7, "bold"),
                                           bg="#2a2a2a", fg="#ffffff", relief="solid", bd=1,
                                           command=self.remove_current_dps_dummy)
        self.btn_del_dps_dummy.pack(side="right", padx=2)

        # 3. Sliders tinh chỉnh chỉ số cho Dummy hiện tại (giống hệt bên A)
        self.box_dps_sliders = tk.Frame(self.frame_b_dps, bg=self.c_surface)
        self.box_dps_sliders.pack(fill="both", expand=True, pady=2)

        self.populate_team_sliders("dps", self.box_dps_sliders, self.dps_dummy_vars, on_change_fn=self.on_dps_slider_change)

        self.render_dps_dummy_tabs()
        self.load_dps_dummy_to_sliders(0)

    def on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "fight":
            if hasattr(self, "scenario_bar"):
                self.scenario_bar.pack(fill="x", side="top", padx=8, pady=(0, 6), before=self.combat_split)
            if hasattr(self, "frame_time_dps") and hasattr(self, "lbl_fight_mode_notice"):
                self.frame_time_dps.pack_forget()
                self.lbl_fight_mode_notice.pack(side="left", padx=(8, 8), before=self.lbl_runs_desc)
            self.frame_b_dps.pack_forget()
            self.frame_b_fight.pack(fill="both", expand=True)
        else:
            if hasattr(self, "scenario_bar"):
                self.scenario_bar.pack_forget()
            if hasattr(self, "frame_time_dps") and hasattr(self, "lbl_fight_mode_notice"):
                self.lbl_fight_mode_notice.pack_forget()
                self.frame_time_dps.pack(side="left", padx=(8, 4), before=self.lbl_runs_desc)
            self.frame_b_fight.pack_forget()
            self.frame_b_dps.pack(fill="both", expand=True)

    def render_dps_dummy_tabs(self):
        for w in self.dps_tabs_frame.winfo_children():
            w.destroy()

        for idx, item in enumerate(self.dps_dummies):
            is_active = (idx == self.current_dps_idx)
            bg_c = "#ffffff" if is_active else "#262626"
            fg_c = "#000000" if is_active else "#cccccc"

            st = item["stats"]
            hp_txt = f"{int(st.get('hp', 2000)) // 1000}k" if st.get('hp', 2000) >= 1000 else f"{int(st.get('hp', 2000))}"
            def_txt = f"{int(st.get('defense', 300))}"
            btn_txt = f"#{idx + 1} ({hp_txt} HP/{def_txt} Def)"

            btn = tk.Button(self.dps_tabs_frame, text=btn_txt, font=("Segoe UI", 7, "bold" if is_active else "normal"),
                            bg=bg_c, fg=fg_c, relief="solid", bd=1, padx=4, pady=1, cursor="hand2",
                            command=lambda i=idx: self.select_dps_dummy_tab(i))
            btn.pack(side="left", padx=2)

        if len(self.dps_dummies) >= 6:
            self.btn_add_dummy.config(state="disabled", bg="#333333", fg="#666666")
        else:
            self.btn_add_dummy.config(state="normal", bg="#ffffff", fg="#000000")

    def select_dps_dummy_tab(self, idx):
        self.current_dps_idx = idx
        self.render_dps_dummy_tabs()
        self.load_dps_dummy_to_sliders(idx)

    def load_dps_dummy_to_sliders(self, idx):
        if idx >= len(self.dps_dummies):
            idx = 0
            self.current_dps_idx = 0

        item = self.dps_dummies[idx]
        self.lbl_cur_dummy.config(text=f"Dummy #{idx + 1}:")
        self.cb_dps_base.set(item["base_id"])

        for k, info in self.dps_dummy_vars.items():
            val = item["stats"].get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    def on_dps_slider_change(self):
        # Lưu các giá trị slider vào stats của dummy hiện tại
        if self.current_dps_idx < len(self.dps_dummies):
            for k, info in self.dps_dummy_vars.items():
                self.dps_dummies[self.current_dps_idx]["stats"][k] = info["var"].get()
            self.render_dps_dummy_tabs()

    def on_change_dps_dummy_base(self):
        new_base = self.cb_dps_base.get()
        if self.current_dps_idx < len(self.dps_dummies):
            self.dps_dummies[self.current_dps_idx]["base_id"] = new_base
            defs = get_entity_default_stats(self.cfg, new_base)
            self.dps_dummies[self.current_dps_idx]["stats"] = dict(defs)
            self.load_dps_dummy_to_sliders(self.current_dps_idx)
            self.render_dps_dummy_tabs()

    def apply_dps_dummy_preset(self, def_val):
        hp_map = {1000: 6000, 3000: 20000, 10000: 50000}
        hp_val = hp_map.get(def_val, 10000)
        if self.current_dps_idx < len(self.dps_dummies):
            self.dps_dummies[self.current_dps_idx]["stats"]["defense"] = float(def_val)
            self.dps_dummies[self.current_dps_idx]["stats"]["hp"] = float(hp_val)
            self.load_dps_dummy_to_sliders(self.current_dps_idx)
            self.render_dps_dummy_tabs()

    def copy_dps_stats_to_all(self):
        if self.current_dps_idx < len(self.dps_dummies):
            cur_stats = dict(self.dps_dummies[self.current_dps_idx]["stats"])
            cur_base = self.dps_dummies[self.current_dps_idx]["base_id"]
            for d in self.dps_dummies:
                d["base_id"] = cur_base
                d["stats"] = dict(cur_stats)
            self.render_dps_dummy_tabs()
            messagebox.showinfo("Thông báo", f"Đã sao chép chỉ số của Dummy #{self.current_dps_idx + 1} sang tất cả {len(self.dps_dummies)} Dummy!")

    def add_dps_dummy(self):
        if len(self.dps_dummies) < 6:
            all_dummies = ["dummy:" + k for k in self.cfg["scenarios"]["dummies"] if not k.startswith("_")]
            new_did = all_dummies[len(self.dps_dummies) % len(all_dummies)]
            defs = get_entity_default_stats(self.cfg, new_did)
            self.dps_dummies.append({
                "base_id": new_did,
                "stats": dict(defs)
            })
            self.current_dps_idx = len(self.dps_dummies) - 1
            self.render_dps_dummy_tabs()
            self.load_dps_dummy_to_sliders(self.current_dps_idx)

    def remove_current_dps_dummy(self):
        if len(self.dps_dummies) > 1:
            self.dps_dummies.pop(self.current_dps_idx)
            self.current_dps_idx = max(0, self.current_dps_idx - 1)
            self.render_dps_dummy_tabs()
            self.load_dps_dummy_to_sliders(self.current_dps_idx)

    # --- Sliders Helper cho Team A & Team B ---
    def populate_team_sliders(self, team_tag, container, vars_dict, on_change_fn=None):
        for m in CUSTOM_STATS_META:
            k = m["key"]
            var = tk.DoubleVar(value=m["min"])
            vars_dict[k] = {"var": var, "meta": m}

            row = tk.Frame(container, bg=self.c_surface, pady=1)
            row.pack(fill="x")

            lbl = tk.Label(row, text=m["label"], width=17, anchor="w",
                           bg=self.c_surface, fg=self.c_fg, font=("Segoe UI", 8, "bold"))
            lbl.pack(side="left")

            scale = ttk.Scale(row, from_=m["min"], to=m["max"], variable=var, orient="horizontal")
            scale.pack(side="left", fill="x", expand=True, padx=4)

            ent = tk.Entry(row, width=7, bg="#111111", fg="#ffffff",
                           relief="solid", bd=1, justify="right", font=("Segoe UI", 8))
            ent.pack(side="left", padx=4)
            ent.insert(0, str(m["min"]))

            tk.Label(row, text=m["unit"], width=4, anchor="w",
                     bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 8)).pack(side="left")

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
                    if on_change_fn:
                        on_change_fn()

                def on_en(event=None):
                    try:
                        fval = float(e.get())
                        v.set(fval)
                        if on_change_fn:
                            on_change_fn()
                    except ValueError:
                        pass
                return on_sc, on_en

            sc_fn, en_fn = make_sync(var, ent, m)
            scale.configure(command=sc_fn)
            ent.bind("<Return>", en_fn)
            ent.bind("<FocusOut>", en_fn)

    def get_magic_skills(self, magic):
        basics = []
        actives = []
        for k, v in self.cfg["skills"].items():
            if isinstance(v, dict) and v.get("magic") == magic:
                if v.get("tier") == "Basic" or "basic" in k.lower():
                    basics.append(k)
                else:
                    actives.append(k)
        return basics, actives

    def reset_loadout_a(self):
        e1 = self.cb_elem1_a.get()
        e2 = self.cb_elem2_a.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_basic_a["values"] = b1
        self.cb_basic_a.set(b1[0] if b1 else "")

        if e1 == e2:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a1[2] if len(a1) > 2 else s1
            s4 = a1[3] if len(a1) > 3 else s1
        else:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a2[2] if len(a2) > 2 else (a2[0] if a2 else "")
            s4 = a2[3] if len(a2) > 3 else (a2[1] if len(a2) > 1 else s3)

        self.cb_s1_a.set(s1)
        self.cb_s2_a.set(s2)
        self.cb_s3_a.set(s3)
        self.cb_s4_a.set(s4)
        self.cb_s5_a.set("(Không dùng)")
        self.refresh_loadout_dropdowns_a()

    def refresh_loadout_dropdowns_a(self):
        e1 = self.cb_elem1_a.get()
        e2 = self.cb_elem2_a.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_basic_a["values"] = b1
        s1 = self.cb_s1_a.get()
        s2 = self.cb_s2_a.get()
        s3 = self.cb_s3_a.get()
        s4 = self.cb_s4_a.get()

        self.cb_s1_a["values"] = a1

        opt_s2 = [s for s in a1 if s != s1]
        self.cb_s2_a["values"] = opt_s2 if opt_s2 else a1
        if self.cb_s2_a.get() not in self.cb_s2_a["values"] and opt_s2:
            self.cb_s2_a.set(opt_s2[0])

        if e1 == e2:
            used_branch1 = {s1, self.cb_s2_a.get()}
            opt_s3 = [s for s in a1 if s not in used_branch1]
            self.cb_s3_a["values"] = opt_s3 if opt_s3 else a1
            if self.cb_s3_a.get() not in self.cb_s3_a["values"] and opt_s3:
                self.cb_s3_a.set(opt_s3[0])

            used_so_far = used_branch1 | {self.cb_s3_a.get()}
            opt_s4 = [s for s in a1 if s not in used_so_far]
            self.cb_s4_a["values"] = opt_s4 if opt_s4 else a1
            if self.cb_s4_a.get() not in self.cb_s4_a["values"] and opt_s4:
                self.cb_s4_a.set(opt_s4[0])

            used_all = used_so_far | {self.cb_s4_a.get()}
            rem_s5 = [s for s in a1 if s not in used_all]
            self.cb_s5_a["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_s5_a.get() not in self.cb_s5_a["values"]:
                self.cb_s5_a.set("(Không dùng)")
        else:
            self.cb_s3_a["values"] = a2
            opt_s4 = [s for s in a2 if s != s3]
            self.cb_s4_a["values"] = opt_s4 if opt_s4 else a2
            if self.cb_s4_a.get() not in self.cb_s4_a["values"] and opt_s4:
                self.cb_s4_a.set(opt_s4[0])

            used_b = {self.cb_s3_a.get(), self.cb_s4_a.get()}
            rem_s5 = [s for s in a2 if s not in used_b]
            self.cb_s5_a["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_s5_a.get() not in self.cb_s5_a["values"]:
                self.cb_s5_a.set("(Không dùng)")

    def on_skill_change_a(self):
        self.refresh_loadout_dropdowns_a()

    def reset_loadout_b(self):
        e1 = self.cb_elem1_b.get()
        e2 = self.cb_elem2_b.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_basic_b["values"] = b1
        self.cb_basic_b.set(b1[0] if b1 else "")

        if e1 == e2:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a1[2] if len(a1) > 2 else s1
            s4 = a1[3] if len(a1) > 3 else s1
        else:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a2[2] if len(a2) > 2 else (a2[0] if a2 else "")
            s4 = a2[3] if len(a2) > 3 else (a2[1] if len(a2) > 1 else s3)

        self.cb_s1_b.set(s1)
        self.cb_s2_b.set(s2)
        self.cb_s3_b.set(s3)
        self.cb_s4_b.set(s4)
        self.cb_s5_b.set("(Không dùng)")
        self.refresh_loadout_dropdowns_b()

    def refresh_loadout_dropdowns_b(self):
        e1 = self.cb_elem1_b.get()
        e2 = self.cb_elem2_b.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_basic_b["values"] = b1
        s1 = self.cb_s1_b.get()
        s2 = self.cb_s2_b.get()
        s3 = self.cb_s3_b.get()
        s4 = self.cb_s4_b.get()

        self.cb_s1_b["values"] = a1

        opt_s2 = [s for s in a1 if s != s1]
        self.cb_s2_b["values"] = opt_s2 if opt_s2 else a1
        if self.cb_s2_b.get() not in self.cb_s2_b["values"] and opt_s2:
            self.cb_s2_b.set(opt_s2[0])

        if e1 == e2:
            used_branch1 = {s1, self.cb_s2_b.get()}
            opt_s3 = [s for s in a1 if s not in used_branch1]
            self.cb_s3_b["values"] = opt_s3 if opt_s3 else a1
            if self.cb_s3_b.get() not in self.cb_s3_b["values"] and opt_s3:
                self.cb_s3_b.set(opt_s3[0])

            used_so_far = used_branch1 | {self.cb_s3_b.get()}
            opt_s4 = [s for s in a1 if s not in used_so_far]
            self.cb_s4_b["values"] = opt_s4 if opt_s4 else a1
            if self.cb_s4_b.get() not in self.cb_s4_b["values"] and opt_s4:
                self.cb_s4_b.set(opt_s4[0])

            used_all = used_so_far | {self.cb_s4_b.get()}
            rem_s5 = [s for s in a1 if s not in used_all]
            self.cb_s5_b["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_s5_b.get() not in self.cb_s5_b["values"]:
                self.cb_s5_b.set("(Không dùng)")
        else:
            self.cb_s3_b["values"] = a2
            opt_s4 = [s for s in a2 if s != s3]
            self.cb_s4_b["values"] = opt_s4 if opt_s4 else a2
            if self.cb_s4_b.get() not in self.cb_s4_b["values"] and opt_s4:
                self.cb_s4_b.set(opt_s4[0])

            used_b = {self.cb_s3_b.get(), self.cb_s4_b.get()}
            rem_s5 = [s for s in a2 if s not in used_b]
            self.cb_s5_b["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_s5_b.get() not in self.cb_s5_b["values"]:
                self.cb_s5_b.set("(Không dùng)")

    def on_skill_change_b(self):
        self.refresh_loadout_dropdowns_b()

    def on_elem_change_a(self):
        e1 = self.cb_elem1_a.get()
        e2 = self.cb_elem2_a.get()
        if e1 == e2:
            self.lbl_status_a.config(text=f"★ PURETYPE: Thuần {e1} (+15% dmg & xuyên kháng)",
                                     bg="#ffffff", fg="#000000")
        else:
            self.lbl_status_a.config(text=f"⚡ TỔ HỢP: {e1} (Nhánh 1) + {e2} (Nhánh 2)",
                                     bg="#242424", fg="#ffffff")
        if hasattr(self, "lbl_l1_a"):
            self.lbl_l1_a.config(text=f"Nhánh 1 ({e1}):")
            self.lbl_l2_a.config(text=f"Nhánh 2 ({e2}):")
            self.reset_loadout_a()

    def swap_elements_a(self):
        e1 = self.cb_elem1_a.get()
        e2 = self.cb_elem2_a.get()
        self.cb_elem1_a.set(e2)
        self.cb_elem2_a.set(e1)
        self.on_elem_change_a()

    def make_pure_a(self):
        e1 = self.cb_elem1_a.get()
        self.cb_elem2_a.set(e1)
        self.on_elem_change_a()

    def reset_stats_a(self):
        base_defs = {
            "hp": 2000, "atk": 200, "defense": 300, "mc": 0.0,
            "pct_def_ignore": 0.05, "flat_def_ignore": 50, "damage_mult": 1.0,
            "cdr": 0.0, "guard_q": 0.35, "res": 0.0
        }
        for k, info in self.team_a_vars.items():
            val = base_defs.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    def on_elem_change_b(self):
        if self.target_type_b.get() != "build":
            return
        e1 = self.cb_elem1_b.get()
        e2 = self.cb_elem2_b.get()
        if e1 == e2:
            self.lbl_status_b.config(text=f"★ PURETYPE: Thuần {e1} (+15% dmg & xuyên kháng)",
                                     bg="#ffffff", fg="#000000")
        else:
            self.lbl_status_b.config(text=f"⚡ TỔ HỢP: {e1} (Nhánh 1) + {e2} (Nhánh 2)",
                                     bg="#242424", fg="#ffffff")
        if hasattr(self, "lbl_l1_b"):
            self.lbl_l1_b.config(text=f"Nhánh 1 ({e1}):")
            self.lbl_l2_b.config(text=f"Nhánh 2 ({e2}):")
            self.reset_loadout_b()

    def swap_elements_b(self):
        e1 = self.cb_elem1_b.get()
        e2 = self.cb_elem2_b.get()
        self.cb_elem1_b.set(e2)
        self.cb_elem2_b.set(e1)
        self.on_elem_change_b()

    def make_pure_b(self):
        e1 = self.cb_elem1_b.get()
        self.cb_elem2_b.set(e1)
        self.on_elem_change_b()

    def on_toggle_b_type(self):
        t = self.target_type_b.get()
        if t == "build":
            self.cb_elem1_b.config(state="readonly")
            self.cb_elem2_b.config(state="readonly")
            self.cb_dummy_b.config(state="disabled")
            if hasattr(self, "preset_row_b"):
                self.preset_row_b.pack(fill="x", pady=(2, 3), before=self.box_loadout_b)
            if hasattr(self, "box_loadout_b"):
                self.box_loadout_b.pack(fill="x", pady=2, before=self.box_sliders_b)
            self.on_elem_change_b()
        else:
            self.cb_elem1_b.config(state="disabled")
            self.cb_elem2_b.config(state="disabled")
            self.cb_dummy_b.config(state="readonly")
            if hasattr(self, "preset_row_b"):
                self.preset_row_b.pack_forget()
            if hasattr(self, "box_loadout_b"):
                self.box_loadout_b.pack_forget()
            self.on_select_dummy_b()

    def on_select_dummy_b(self):
        did = self.cb_dummy_b.get()
        self.lbl_status_b.config(text=f"🎯 DUMMY: {did}",
                                 bg="#242424", fg="#ffffff")
        defs = get_entity_default_stats(self.cfg, did)
        for k, info in self.team_b_fight_vars.items():
            val = defs.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    def reset_stats_b(self):
        t = self.target_type_b.get()
        if t == "dummy":
            self.on_select_dummy_b()
        else:
            base_defs = {
                "hp": 2000, "atk": 200, "defense": 300, "mc": 0.0,
                "pct_def_ignore": 0.05, "flat_def_ignore": 50, "damage_mult": 1.0,
                "cdr": 0.0, "guard_q": 0.35, "res": 0.0
            }
            for k, info in self.team_b_fight_vars.items():
                val = base_defs.get(k, info["meta"]["min"])
                info["var"].set(val)
                info["entry"].delete(0, "end")
                info["entry"].insert(0, str(val))

    def apply_preset_a(self, preset_key):
        if preset_key == "dps":
            self.set_stat_val("a", "atk", 450)
            self.set_stat_val("a", "hp", 1800)
            self.set_stat_val("a", "damage_mult", 1.35)
            self.set_stat_val("a", "pct_def_ignore", 0.20)
        elif preset_key == "caster":
            self.set_stat_val("a", "atk", 240)
            self.set_stat_val("a", "mc", 0.35)
            self.set_stat_val("a", "cdr", 0.30)
        elif preset_key == "tank":
            self.set_stat_val("a", "hp", 8000)
            self.set_stat_val("a", "defense", 1200)
            self.set_stat_val("a", "guard_q", 0.60)
            self.set_stat_val("a", "res", 0.15)

    def apply_tank_preset_b(self, def_val):
        hp_map = {1000: 6000, 3000: 20000, 10000: 50000}
        self.set_stat_val("b", "defense", def_val)
        self.set_stat_val("b", "hp", hp_map.get(def_val, 10000))

    def set_stat_val(self, team, key, val):
        vars_dict = self.team_a_vars if team == "a" else self.team_b_fight_vars
        if key in vars_dict:
            vars_dict[key]["var"].set(val)
            vars_dict[key]["entry"].delete(0, "end")
            vars_dict[key]["entry"].insert(0, str(val))

    # --- CHẠY MÔ PHỎNG (HỖ TRỢ FIGHT VÀ DPS NHIỀU DUMMY TỰ CHỈNH) ---
    def run_simulation(self):
        mode = self.mode_var.get()
        if mode == "fight":
            time_limit = 1800.0  # Chế độ sinh tử 1v1: không giới hạn 60s, đánh đến khi một bên thua (tối đa 1800s an toàn)
        else:
            time_limit = float(self.sp_time.get() or 60)
        runs = int(self.sp_runs.get() or 50)

        custom_a = {k: v["var"].get() for k, v in self.team_a_vars.items()}

        self.txt_sim_result.delete("1.0", "end")
        if mode == "fight":
            self.txt_sim_result.insert("1.0", f"Đang mô phỏng 1v1 FIGHT (SINH TỬ) với {runs} lượt, đánh đến khi một bên ngã xuống (không giới hạn 60s)...\n")
        else:
            self.txt_sim_result.insert("1.0", f"Đang mô phỏng ({mode.upper()}) với {runs} lượt, thời gian {time_limit:.0f}s...\n")
        self.update_idletasks()

        try:
            cfg = copy.deepcopy(self.cfg)
            cfg["rules"] = self.current_rules

            # 1. Build Team A từ 2 nguyên tố và Loadout tùy chọn
            elem1_a = self.cb_elem1_a.get()
            elem2_a = self.cb_elem2_a.get()
            is_pure_a = (elem1_a == elem2_a)

            basic_a = self.cb_basic_a.get()
            skills_a = [self.cb_s1_a.get(), self.cb_s2_a.get()]
            skills_b = [self.cb_s3_a.get(), self.cb_s4_a.get()]
            extra_s_a = self.cb_s5_a.get()
            if extra_s_a and extra_s_a not in ("(Không dùng)", "(Hết skill)"):
                skills_b.append(extra_s_a)

            lbl_a = f"PureType {elem1_a} (Đội A)" if is_pure_a else f"{elem1_a} + {elem2_a} (Đội A)"
            desc_a = f"PureType {elem1_a}" if is_pure_a else f"{elem1_a} + {elem2_a}"

            b_a = {
                "label": lbl_a,
                "basic": basic_a,
                "branch_a": {"magic": elem1_a, "skills": skills_a},
                "branch_b": {"magic": elem2_a, "skills": skills_b},
                "relic": None,
                "relics": list(getattr(self, "selected_relics_a", []))
            }

            b_a.setdefault("stats", {})
            for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr"]:
                b_a["stats"][k] = float(custom_a[k])
            b_a["guard_q"] = float(custom_a["guard_q"])
            if custom_a["res"] > 0:
                b_a.setdefault("res", {})
                b_a["res"]["*"] = float(custom_a["res"])

            cfg["builds"]["custom_team_a"] = b_a
            actual_a = ["custom_team_a"]

            # 2. Build Team B tùy theo chế độ
            target_desc = ""
            desc_b = ""
            basic_b = ""
            skills_b1 = []
            skills_b2 = []

            if mode == "fight":
                target_type = self.target_type_b.get()
                custom_b = {k: v["var"].get() for k, v in self.team_b_fight_vars.items()}
                custom_id_b = "custom_team_b"

                if target_type == "build":
                    elem1_b = self.cb_elem1_b.get()
                    elem2_b = self.cb_elem2_b.get()
                    is_pure_b = (elem1_b == elem2_b)

                    basic_b = self.cb_basic_b.get()
                    skills_b1 = [self.cb_s1_b.get(), self.cb_s2_b.get()]
                    skills_b2 = [self.cb_s3_b.get(), self.cb_s4_b.get()]
                    extra_s_b = self.cb_s5_b.get()
                    if extra_s_b and extra_s_b not in ("(Không dùng)", "(Hết skill)"):
                        skills_b2.append(extra_s_b)

                    lbl_b = f"PureType {elem1_b} (Đội B)" if is_pure_b else f"{elem1_b} + {elem2_b} (Đội B)"
                    desc_b = f"PureType {elem1_b}" if is_pure_b else f"{elem1_b} + {elem2_b}"

                    b_b = {
                        "label": lbl_b,
                        "basic": basic_b,
                        "branch_a": {"magic": elem1_b, "skills": skills_b1},
                        "branch_b": {"magic": elem2_b, "skills": skills_b2},
                        "relic": None,
                        "relics": list(getattr(self, "selected_relics_b", []))
                    }

                    b_b.setdefault("stats", {})
                    for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr"]:
                        b_b["stats"][k] = float(custom_b[k])
                    b_b["guard_q"] = float(custom_b["guard_q"])
                    if custom_b["res"] > 0:
                        b_b.setdefault("res", {})
                        b_b["res"]["*"] = float(custom_b["res"])

                    cfg["builds"][custom_id_b] = b_b
                    actual_b = [custom_id_b]
                    target_desc = desc_b
                else:
                    team_b_id = self.cb_dummy_b.get()
                    did = team_b_id[6:] if team_b_id.startswith("dummy:") else team_b_id
                    d = copy.deepcopy(cfg["scenarios"]["dummies"].get(did, {}))
                    d["hp"] = float(custom_b["hp"])
                    d["defense"] = float(custom_b["defense"])
                    d["guard_q"] = float(custom_b["guard_q"])
                    if custom_b["res"] > 0:
                        d.setdefault("res", {})
                        d["res"]["*"] = float(custom_b["res"])
                    cfg["scenarios"]["dummies"][custom_id_b] = d
                    actual_b = ["dummy:" + custom_id_b]
                    target_desc = f"Dummy ({team_b_id})"
            else:
                # Chế độ DPS: danh sách nhiều dummy custom
                actual_b = []
                for idx, item in enumerate(self.dps_dummies):
                    cid = f"custom_dummy_{idx + 1}"
                    base_did = item["base_id"][6:] if item["base_id"].startswith("dummy:") else item["base_id"]
                    d = copy.deepcopy(cfg["scenarios"]["dummies"].get(base_did, {}))

                    st = item["stats"]
                    d["hp"] = float(st.get("hp", d.get("hp", 2000)))
                    d["defense"] = float(st.get("defense", d.get("defense", 300)))
                    d["guard_q"] = float(st.get("guard_q", 0.0))
                    for k in ("atk", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr"):
                        if k in st:
                            d[k] = float(st[k])
                    if float(st.get("res", 0.0)) > 0:
                        d.setdefault("res", {})
                        d["res"]["*"] = float(st["res"])

                    cfg["scenarios"]["dummies"][cid] = d
                    actual_b.append("dummy:" + cid)
                target_desc = f"{len(actual_b)} Dummy Custom (" + ", ".join(f"#{i+1}:{int(it['stats'].get('hp',2000))}HP/{int(it['stats'].get('defense',300))}Def" for i, it in enumerate(self.dps_dummies)) + ")"

            A = resolve_team(cfg, actual_a, "A")
            B = resolve_team(cfg, actual_b, "B")
            soft_check(cfg, A + B)

            if mode == "fight":
                scen_key = self.current_scenario_key.get()
                scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
                scen_data = scens_dict.get(scen_key)
                if not scen_data and scens_dict:
                    scen_data = list(scens_dict.values())[0]
                active_scenario = copy.deepcopy(scen_data) if scen_data else None
            else:
                active_scenario = None

            agg, logs = run_batch(cfg, A, B, mode=mode, T=time_limit, runs=runs, seed=42, scenario=active_scenario)
            n = max(1, agg.n)

            # Báo cáo kết quả
            preset_a_lbl = f" (Preset: {self.cb_preset_a.get()})" if hasattr(self, "cb_preset_a") and self.cb_preset_a.get() not in ("(Tùy chỉnh)", "") else ""
            out_text = "═" * 78 + "\n"
            out_text += f" KẾT QUẢ MÔ PHỎNG: {desc_a}{preset_a_lbl} vs {target_desc}\n"
            out_text += f" Loadout Đội A: [{basic_a} | {', '.join(skills_a)} | {', '.join(skills_b)}]\n"
            if self.selected_relics_a:
                out_text += f" Relics Đội A : [{', '.join(self.selected_relics_a)}]\n"
            if mode == "fight" and target_type == "build":
                preset_b_lbl = f" (Preset: {self.cb_preset_b.get()})" if hasattr(self, "cb_preset_b") and self.cb_preset_b.get() not in ("(Tùy chỉnh)", "") else ""
                out_text += f" Loadout Đội B{preset_b_lbl}: [{basic_b} | {', '.join(skills_b1)} | {', '.join(skills_b2)}]\n"
                if self.selected_relics_b:
                    out_text += f" Relics Đội B : [{', '.join(self.selected_relics_b)}]\n"
            if mode == "fight":
                out_text += f" Chế độ: 1v1 FIGHT (SINH TỬ - ĐÁNH ĐẾN KHI CÓ BÊN THUA)  |  Số trận: {runs}\n"
            else:
                out_text += f" Chế độ: DPS MODE  |  Số trận: {runs}  |  Thời gian: {time_limit:.0f}s\n"

            if mode == "fight" and active_scenario:
                scen_name = active_scenario.get("name", "Custom")
                scen_desc = active_scenario.get("desc", "")
                p_a = active_scenario.get("team_a", {})
                p_b = active_scenario.get("team_b", {})
                out_text += f" Kịch Bản 1v1: {scen_name}\n"
                if scen_desc:
                    out_text += f" Mô tả       : {scen_desc}\n"
                out_text += f" • Đội A [{p_a.get('rank_title', 'A')}]: Phản xạ {p_a.get('reaction_time', 0.2)*1000:.0f}ms | Né {p_a.get('dodge', {}).get('rate', 0.4)*100:.0f}% | Parry {p_a.get('parry', {}).get('rate', 0.2)*100:.0f}% | Tâm lý {p_a.get('psychology', {}).get('composure', 0.6)*100:.0f}%\n"
                out_text += f" • Đội B [{p_b.get('rank_title', 'B')}]: Phản xạ {p_b.get('reaction_time', 0.2)*1000:.0f}ms | Né {p_b.get('dodge', {}).get('rate', 0.4)*100:.0f}% | Parry {p_b.get('parry', {}).get('rate', 0.2)*100:.0f}% | Tâm lý {p_b.get('psychology', {}).get('composure', 0.6)*100:.0f}%\n"

            out_text += "─" * 78 + "\n"

            if mode == "fight":
                wa, wb, wd = agg.wins["A"], agg.wins["B"], agg.wins[None]
                if wd > 0:
                    out_text += f" Tỉ Lệ Thắng  : Đội A: {pct(wa / n, 1)} ({wa} trận)  |  Đội B: {pct(wb / n, 1)} ({wb} trận)  |  Hòa: {pct(wd / n, 1)} ({wd})\n"
                else:
                    out_text += f" Tỉ Lệ Thắng  : Đội A: {pct(wa / n, 1)} ({wa} trận thắng)  |  Đội B: {pct(wb / n, 1)} ({wb} trận thắng)\n"
                
                t_ends = agg.t_end if agg.t_end else [0.0]
                avg_t = sum(t_ends) / n
                min_t = min(t_ends)
                max_t = max(t_ends)
                out_text += f" Thời Gian Đấu: Trung bình {avg_t:.1f}s / trận  (Nhanh nhất: {min_t:.1f}s  |  Lâu nhất: {max_t:.1f}s)\n"
            else:
                out_text += f" Tổng Sát Thương Đội A Gây Ra (TB): {agg.dmg['A'] / n:.0f} dmg  |  DPS Trung Bình: {(agg.dmg['A'] / n) / time_limit:.0f}\n"

            out_text += "─" * 78 + "\n"
            name_map = {
                "custom_team_a": f"[A] {desc_a}",
                "custom_team_b": f"[B] {target_desc}",
            }
            dur = sum(agg.t_end) / n if mode == "fight" else time_limit

            if mode == "fight":
                out_text += f" {'THỰC THỂ / MỤC TIÊU':<20} | {'TỔNG DMG':<10} | {'DPS':<7} | {'DODGE':<6} | {'PARRY':<6} | {'BLOCK':<6} | {'TÂM LÝ (PANIC/CLUTCH)'}\n"
                out_text += "─" * 78 + "\n"
                for e_name, metrics in agg.m.items():
                    direct = metrics["direct"] / n
                    dot = metrics["dot"] / n
                    true = metrics["true"] / n
                    bonus = metrics.get("bonus", 0.0) / n
                    dmg = direct + dot + true + bonus
                    dps = dmg / max(0.1, dur)
                    blk = metrics.get("blocks", 0.0) / n
                    ddg = metrics.get("dodges", 0.0) / n
                    pry = metrics.get("parries", 0.0) / n
                    pan = metrics.get("panics", 0.0) / n
                    clt = metrics.get("clutches", 0.0) / n
                    clean_name = name_map.get(e_name, e_name)[:20]
                    psy_str = f"Pan:{pan:.1f} / Clt:{clt:.1f}"
                    out_text += f" {clean_name:<20} | {dmg:>10.0f} | {dps:>7.0f} | {ddg:>6.1f} | {pry:>6.1f} | {blk:>6.1f} | {psy_str:>16}\n"
            else:
                out_text += f" {'THỰC THỂ / MỤC TIÊU':<20} | {'TỔNG DAMAGE':<12} | {'DPS':<8} | {'TRỰC TIẾP':<10} | {'DoT':<8} | {'CHUẨN':<8} | {'BLOCK':<6}\n"
                out_text += "─" * 78 + "\n"
                for e_name, metrics in agg.m.items():
                    direct = metrics["direct"] / n
                    dot = metrics["dot"] / n
                    true = metrics["true"] / n
                    bonus = metrics.get("bonus", 0.0) / n
                    dmg = direct + dot + true + bonus
                    dps = dmg / max(0.1, dur)
                    blk = metrics.get("blocks", 0.0) / n
                    clean_name = name_map.get(e_name, e_name)[:20]
                    out_text += f" {clean_name:<20} | {dmg:>11.0f} | {dps:>8.0f} | {direct:>10.0f} | {dot:>8.0f} | {true:>8.0f} | {blk:>6.1f}\n"

            out_text += "═" * 78 + "\n"

            # Uptime các hiệu ứng
            probe = Sim(cfg, A, B, infinite=(mode == "dps"), T=time_limit, log=False, scenario=active_scenario).run()
            uptimes = uptime_rows(agg, probe)
            if uptimes:
                out_text += "\n [ TỈ LỆ THỜI GIAN DUY TRÌ HIỆU ỨNG (UPTIME) ]\n"
                out_text += f" {'Mục tiêu':<16} | {'Frozen':<8} | {'Freezing':<8} | {'Drained':<8} | {'Wet':<8} | {'Choáng':<8} | {'Slow TB'}\n"
                out_text += "─" * 78 + "\n"
                for u in uptimes:
                    out_text += f" {u[0]:<16} | {u[1]:<8} | {u[2]:<8} | {u[3]:<8} | {u[4]:<8} | {u[5]:<8} | {u[6]}\n"

            self.txt_sim_result.delete("1.0", "end")
            self.txt_sim_result.insert("1.0", out_text)
        except Exception as ex:
            self.txt_sim_result.delete("1.0", "end")
            self.txt_sim_result.insert("1.0", f"LỖI MÔ PHỎNG: {ex}")

    # -------------------------------------------------------------------------
    # TAB 2: QUẢN LÝ HIỆU ỨNG & LUẬT CHƠI (EFFECT RULES)
    # -------------------------------------------------------------------------
    def build_rules_tab(self, parent):
        canvas = tk.Canvas(parent, bg=self.c_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.c_bg)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar.pack(side="right", fill="y", pady=6)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        categories = {}
        for m in SLIDERS_META:
            cat = m["category"]
            if cat not in categories:
                cat_title = ELEMENT_CATEGORY_NAMES.get(cat, m["cat_name"])
                categories[cat] = {"name": cat_title, "items": []}
            categories[cat]["items"].append(m)

        for cat_id, cat_info in categories.items():
            cat_box = tk.LabelFrame(scrollable_frame, text=f" [ {cat_info['name'].upper()} ] ",
                                    font=("Segoe UI", 9, "bold"), fg=self.c_fg, bg=self.c_surface,
                                    padx=12, pady=6, bd=1, relief="solid")
            cat_box.pack(fill="x", expand=True, padx=6, pady=6)

            for item in cat_info["items"]:
                path = item["path"]
                init_val = self.get_val(self.current_rules, path)
                if init_val is None:
                    init_val = item["min"]

                var = tk.DoubleVar(value=init_val)
                self.slider_vars[path] = var

                row = tk.Frame(cat_box, bg=self.c_surface, pady=3)
                row.pack(fill="x")

                lbl_name = tk.Label(row, text=item["label"], width=40, anchor="w",
                                    font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface)
                lbl_name.pack(side="left")

                scale = ttk.Scale(row, from_=item["min"], to=item["max"], variable=var, orient="horizontal")
                scale.pack(side="left", fill="x", expand=True, padx=6)

                ent = tk.Entry(row, width=7, bg="#111111", fg="#ffffff",
                               relief="solid", bd=1, justify="right", font=("Segoe UI", 8))
                ent.pack(side="left", padx=4)
                ent.insert(0, str(init_val))

                lbl_unit = tk.Label(row, text=item["unit"], width=10, anchor="w",
                                    font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface)
                lbl_unit.pack(side="left")

                btn_rst = tk.Button(row, text="↺", font=("Segoe UI", 8),
                                    bg="#242424", fg="#a0a0a0", relief="solid", bd=1, padx=4,
                                    cursor="hand2", command=lambda p=path, e=ent, meta=item: self.reset_single_rule(p, e, meta))
                btn_rst.pack(side="left", padx=2)

                def make_rule_sync(p, meta, v, e):
                    def on_sc(val):
                        fval = round(float(val) / meta["step"]) * meta["step"]
                        if meta.get("format") == "int":
                            fval = int(round(fval))
                        else:
                            fval = round(fval, 3)
                        self.set_val(self.current_rules, p, fval)
                        e.delete(0, "end")
                        e.insert(0, str(fval))
                        self.update_diff_status()

                    def on_en(event=None):
                        try:
                            fval = float(e.get())
                            fval = max(meta["min"], min(meta["max"], fval))
                            v.set(fval)
                            on_sc(fval)
                        except ValueError:
                            pass
                    return on_sc, on_en

                sc_fn, en_fn = make_rule_sync(path, item, var, ent)
                scale.configure(command=sc_fn)
                ent.bind("<Return>", en_fn)
                ent.bind("<FocusOut>", en_fn)

    def reset_single_rule(self, path, entry, meta):
        base = self.get_val(self.baseline_rules, path)
        if base is not None:
            self.set_val(self.current_rules, path, base)
            self.slider_vars[path].set(base)
            entry.delete(0, "end")
            entry.insert(0, str(base))
            self.update_diff_status()

    # -------------------------------------------------------------------------
    # TAB 3: ADVANCED - CÔNG THỨC TÍNH DAMAGE
    # -------------------------------------------------------------------------
    def build_advanced_tab(self, parent):
        adv_canvas = tk.Canvas(parent, bg=self.c_bg, highlightthickness=0)
        adv_scroll = ttk.Scrollbar(parent, orient="vertical", command=adv_canvas.yview)
        adv_frame = tk.Frame(adv_canvas, bg=self.c_bg)

        adv_frame.bind("<Configure>", lambda e: adv_canvas.configure(scrollregion=adv_canvas.bbox("all")))
        adv_canvas.create_window((0, 0), window=adv_frame, anchor="nw")
        adv_canvas.configure(yscrollcommand=adv_scroll.set)

        adv_canvas.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        adv_scroll.pack(side="right", fill="y", pady=8)

        cur_df = self.current_rules.get("damage_formula", {})

        # KHUNG 1: CÔNG THỨC DAMAGE CHÍNH
        box_df = tk.LabelFrame(adv_frame, text=" [ 1. CÔNG THỨC TÍNH SÁT THƯƠNG (DAMAGE FORMULAS) ] ",
                               font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_surface,
                               padx=16, pady=12, bd=1, relief="solid")
        box_df.pack(fill="x", expand=True, padx=8, pady=6)

        # 1. Raw Damage Expression
        f1 = tk.Frame(box_df, bg=self.c_surface, pady=6)
        f1.pack(fill="x")
        tk.Label(f1, text="Sát Thương Thô (Raw Damage):", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_surface).pack(anchor="w")
        tk.Label(f1, text="Biến số: atk (chỉ số tấn công), base (sát thương skill), damage_mult (hệ số tăng sát thương)",
                 font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 4))

        self.ent_raw_expr = tk.Entry(f1, font=("Consolas", 10), bg="#111111", fg="#ffffff",
                                     relief="solid", bd=1, insertbackground="#ffffff")
        self.ent_raw_expr.pack(fill="x", pady=2)
        self.ent_raw_expr.insert(0, cur_df.get("raw_expr", DEFAULT_FORMULAS["raw_expr"]))

        p1 = tk.Frame(f1, bg=self.c_surface)
        p1.pack(fill="x", pady=2)
        tk.Label(p1, text="Mẫu gợi ý:", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")
        for p_txt, p_exp in [("Chuẩn IOM", "(atk + base) * damage_mult"),
                             ("Scaling ATK cao", "(atk * 1.5 + base) * damage_mult"),
                             ("Nhân Tỉ Lệ", "atk * (1 + base / 100) * damage_mult")]:
            tk.Button(p1, text=p_txt, font=("Segoe UI", 7), bg="#262626", fg="#cccccc", relief="solid", bd=1,
                      command=lambda exp=p_exp: self.set_entry_val(self.ent_raw_expr, exp)).pack(side="left", padx=2)

        # 2. Defense Reduction Expression
        f2 = tk.Frame(box_df, bg=self.c_surface, pady=8)
        f2.pack(fill="x")
        tk.Label(f2, text="Tỉ Lệ Giảm Trừ Theo Giáp (Defense Reduction Ratio red ∈ [0, 1]):", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_surface).pack(anchor="w")
        tk.Label(f2, text="Biến số: d (giáp mục tiêu sau khi trừ xuyên giáp), def_k (hằng số giáp). Sát thương qua giáp = raw * (1 - red)",
                 font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 4))

        k_row = tk.Frame(f2, bg=self.c_surface)
        k_row.pack(fill="x", pady=2)
        tk.Label(k_row, text="Hằng số giáp (def_k):", font=("Segoe UI", 8, "bold"), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.ent_def_k = tk.Entry(k_row, width=8, font=("Consolas", 9), bg="#111111", fg="#ffffff", relief="solid", bd=1)
        self.ent_def_k.pack(side="left", padx=6)
        self.ent_def_k.insert(0, str(cur_df.get("def_k", DEFAULT_FORMULAS["def_k"])))

        self.ent_def_expr = tk.Entry(f2, font=("Consolas", 10), bg="#111111", fg="#ffffff",
                                     relief="solid", bd=1, insertbackground="#ffffff")
        self.ent_def_expr.pack(fill="x", pady=2)
        self.ent_def_expr.insert(0, cur_df.get("def_expr", DEFAULT_FORMULAS["def_expr"]))

        p2 = tk.Frame(f2, bg=self.c_surface)
        p2.pack(fill="x", pady=2)
        tk.Label(p2, text="Mẫu gợi ý:", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")
        for p_txt, p_exp in [("Chuẩn Hyperbolic", "d / (def_k + d)"),
                             ("Giáp Tank K=300", "d / (300.0 + d)"),
                             ("Tuyến tính trần 85%", "min(0.85, d * 0.0008)"),
                             ("Mũ Giáp 0.99^d", "1.0 - (0.992 ** d)")]:
            tk.Button(p2, text=p_txt, font=("Segoe UI", 7), bg="#262626", fg="#cccccc", relief="solid", bd=1,
                      command=lambda exp=p_exp: self.set_entry_val(self.ent_def_expr, exp)).pack(side="left", padx=2)

        # 3. Magic Resistance Multiplier
        f3 = tk.Frame(box_df, bg=self.c_surface, pady=8)
        f3.pack(fill="x")
        tk.Label(f3, text="Hệ Số Kháng Phép (Magic Resistance Multiplier mult):", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_surface).pack(anchor="w")
        tk.Label(f3, text="Biến số: r (kháng phép sau trừ xuyên kháng), caps_res (cap kháng phép = 0.75). Sát thương cuối = raw * (1 - red) * mult",
                 font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 4))

        self.ent_res_expr = tk.Entry(f3, font=("Consolas", 10), bg="#111111", fg="#ffffff",
                                     relief="solid", bd=1, insertbackground="#ffffff")
        self.ent_res_expr.pack(fill="x", pady=2)
        self.ent_res_expr.insert(0, cur_df.get("res_expr", DEFAULT_FORMULAS["res_expr"]))

        p3 = tk.Frame(f3, bg=self.c_surface)
        p3.pack(fill="x", pady=2)
        tk.Label(p3, text="Mẫu gợi ý:", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")
        for p_txt, p_exp in [("Chuẩn IOM", "1 - min(r, caps_res) if r >= 0 else 1 - r / 2"),
                             ("Diminishing 1/(1+r)", "1.0 / (1.0 + max(0, r))"),
                             ("Tuyến tính", "max(0.1, 1.0 - r)")]:
            tk.Button(p3, text=p_txt, font=("Segoe UI", 7), bg="#262626", fg="#cccccc", relief="solid", bd=1,
                      command=lambda exp=p_exp: self.set_entry_val(self.ent_res_expr, exp)).pack(side="left", padx=2)

        # Nút lưu & khôi phục
        action_row = tk.Frame(box_df, bg=self.c_surface, pady=8)
        action_row.pack(fill="x")

        tk.Button(action_row, text="💾 Áp Dụng & Lưu Công Thức", font=("Segoe UI", 9, "bold"),
                  bg="#ffffff", fg="#000000", relief="flat", padx=14, pady=4, cursor="hand2",
                  command=self.save_damage_formulas).pack(side="left", padx=4)

        tk.Button(action_row, text="↺ Trả Về Mặc Định", font=("Segoe UI", 8),
                  bg="#2a2a2a", fg="#ffffff", relief="solid", bd=1, padx=10, pady=4, cursor="hand2",
                  command=self.reset_damage_formulas).pack(side="left", padx=4)

        # KHUNG 2: SANDBOX THỬ NGHIỆM CÔNG THỨC (LIVE TEST)
        box_test = tk.LabelFrame(adv_frame, text=" [ 2. THỬ NGHIỆM CÔNG THỨC (FORMULA SANDBOX) ] ",
                                 font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_surface,
                                 padx=16, pady=12, bd=1, relief="solid")
        box_test.pack(fill="x", expand=True, padx=8, pady=8)

        inputs_grid = tk.Frame(box_test, bg=self.c_surface)
        inputs_grid.pack(fill="x", pady=4)

        self.sb_atk = self.create_sb_input(inputs_grid, "ATK (Công):", "200")
        self.sb_scale = self.create_sb_input(inputs_grid, "% Scale ATK:", "1.0")
        self.sb_base = self.create_sb_input(inputs_grid, "Base Skill:", "150")
        self.sb_dmg_mult = self.create_sb_input(inputs_grid, "Dmg Mult:", "1.0")
        self.sb_def = self.create_sb_input(inputs_grid, "DEF (Thủ):", "300")
        self.sb_pct_ignore = self.create_sb_input(inputs_grid, "Xuyên Giáp %:", "0.05")
        self.sb_flat_ignore = self.create_sb_input(inputs_grid, "Xuyên Giáp Phẳng:", "50")
        self.sb_res = self.create_sb_input(inputs_grid, "RES (Kháng):", "0.20")

        btn_eval = tk.Button(box_test, text="⚡ Tính Thử Kết Quả Ngay", font=("Segoe UI", 9, "bold"),
                             bg="#333333", fg="#ffffff", relief="solid", bd=1, padx=12, pady=3,
                             cursor="hand2", command=self.eval_formula_sandbox)
        btn_eval.pack(anchor="w", pady=6)

        self.lbl_sb_res = tk.Label(box_test, text="Nhấn 'Tính Thử Kết Quả Ngay' để kiểm tra công thức.",
                                   font=("Consolas", 9), fg="#e0e0e0", bg="#111111", relief="solid", bd=1,
                                   padx=10, pady=8, justify="left")
        self.lbl_sb_res.pack(fill="x", pady=4)

    def create_sb_input(self, parent, label_text, default_val):
        f = tk.Frame(parent, bg=self.c_surface)
        f.pack(side="left", padx=4)
        tk.Label(f, text=label_text, font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack()
        ent = tk.Entry(f, width=7, font=("Consolas", 9), bg="#111111", fg="#ffffff", relief="solid", bd=1, justify="right")
        ent.pack()
        ent.insert(0, default_val)
        return ent

    def set_entry_val(self, entry, text):
        entry.delete(0, "end")
        entry.insert(0, text)

    def save_damage_formulas(self):
        raw_expr = self.ent_raw_expr.get().strip()
        def_expr = self.ent_def_expr.get().strip()
        res_expr = self.ent_res_expr.get().strip()
        try:
            def_k = float(self.ent_def_k.get().strip())
        except ValueError:
            def_k = 100.0

        try:
            compile(raw_expr, "<raw_expr>", "eval")
            compile(def_expr, "<def_expr>", "eval")
            compile(res_expr, "<res_expr>", "eval")
        except Exception as e:
            messagebox.showerror("Lỗi Cú Pháp", f"Biểu thức công thức không hợp lệ:\n{e}")
            return

        df_obj = {
            "raw_expr": raw_expr,
            "def_k": def_k,
            "def_expr": def_expr,
            "res_expr": res_expr
        }
        self.current_rules["damage_formula"] = df_obj
        self.save_config()
        messagebox.showinfo("Thành công", "Đã lưu công thức tính damage thành công!\nCác trận mô phỏng kế tiếp sẽ áp dụng công thức mới này.")

    def reset_damage_formulas(self):
        if not messagebox.askyesno("Xác nhận", "Khôi phục toàn bộ công thức tính damage về mặc định của IOM?"):
            return
        self.set_entry_val(self.ent_raw_expr, DEFAULT_FORMULAS["raw_expr"])
        self.set_entry_val(self.ent_def_k, str(DEFAULT_FORMULAS["def_k"]))
        self.set_entry_val(self.ent_def_expr, DEFAULT_FORMULAS["def_expr"])
        self.set_entry_val(self.ent_res_expr, DEFAULT_FORMULAS["res_expr"])
        self.save_damage_formulas()

    def eval_formula_sandbox(self):
        try:
            atk = float(self.sb_atk.get())
            scale_raw = self.sb_scale.get().strip()
            atk_scale = float(scale_raw[:-1]) / 100.0 if scale_raw.endswith("%") else float(scale_raw)
            base = float(self.sb_base.get())
            dmg_mult = float(self.sb_dmg_mult.get())
            dfn = float(self.sb_def.get())
            pct_ig = float(self.sb_pct_ignore.get())
            flat_ig = float(self.sb_flat_ignore.get())
            r = float(self.sb_res.get())

            scaled_atk = atk * atk_scale
            raw_code = compile(self.ent_raw_expr.get().strip(), "<raw>", "eval")
            raw = eval(raw_code, {"__builtins__": None, "max": max, "min": min},
                       {"atk": scaled_atk, "base": base, "damage_mult": dmg_mult, "raw_atk": atk, "atk_scale": atk_scale})

            d = max(0.0, dfn * (1.0 - pct_ig) - flat_ig)
            def_k = float(self.ent_def_k.get().strip())
            def_code = compile(self.ent_def_expr.get().strip(), "<def>", "eval")
            red = eval(def_code, {"__builtins__": None, "max": max, "min": min},
                       {"d": d, "def_k": def_k})
            red = max(0.0, min(1.0, red))

            res_code = compile(self.ent_res_expr.get().strip(), "<res>", "eval")
            mult = eval(res_code, {"__builtins__": None, "max": max, "min": min},
                        {"r": r, "caps_res": 0.75})

            final_dmg = raw * (1.0 - red) * mult

            res_txt = f"► KẾT QUẢ TÍNH TOÁN:\n"
            res_txt += f" • Sát thương thô (Raw)        : ({atk} * {atk_scale:.2f} + {base}) * {dmg_mult} = {raw:.1f}\n"
            res_txt += f" • Giáp sau xuyên giáp (d)     : max(0, {dfn} * (1 - {pct_ig}) - {flat_ig}) = {d:.1f}\n"
            res_txt += f" • Tỉ lệ giảm do giáp (red)    : {red * 100:.2f}%\n"
            res_txt += f" • Hệ số kháng phép (mult)     : {mult:.3f}\n"
            res_txt += f" ═══════════════════════════════════════════════════════════════════════\n"
            res_txt += f" ★ SÁT THƯƠNG CUỐI (FINAL DMG)  : {final_dmg:.2f} DAMAGE"

            self.lbl_sb_res.config(text=res_txt)
        except Exception as e:
            self.lbl_sb_res.config(text=f"Lỗi tính toán biểu thức:\n{e}")

    # -------------------------------------------------------------------------
    # TAB 4: CUSTOM & EDIT SKILLS (QUẢN LÝ, TẠO MỚI & CHỈNH SỬA KỸ NĂNG)
    # -------------------------------------------------------------------------
    def build_skills_tab(self, parent):
        self.editing_skill_id = None

        main_box = tk.Frame(parent, bg=self.c_bg)
        main_box.pack(fill="both", expand=True, padx=8, pady=8)

        # CỘT TRÁI: BỘ LỌC, TÌM KIẾM & DANH SÁCH TREEVIEW (470px)
        left_frame = tk.Frame(main_box, bg=self.c_surface, width=470, bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", padx=(0, 6), pady=0)
        left_frame.pack_propagate(False)

        # Header cột trái
        top_filter_bar = tk.Frame(left_frame, bg=self.c_sub, padx=10, pady=8)
        top_filter_bar.pack(fill="x")

        tk.Label(top_filter_bar, text="DANH SÁCH KỸ NĂNG", font=("Segoe UI", 10, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w", pady=(0, 6))

        # Tìm kiếm theo tên / ID
        search_row = tk.Frame(top_filter_bar, bg=self.c_sub)
        search_row.pack(fill="x", pady=2)
        tk.Label(search_row, text="Tìm kiếm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_sub, width=8, anchor="w").pack(side="left")
        self.ent_skill_search = tk.Entry(search_row, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_skill_search.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.ent_skill_search.bind("<KeyRelease>", lambda e: self.filter_skills_tree())

        # Hàng lọc Magic & Tier
        filter_row = tk.Frame(top_filter_bar, bg=self.c_sub)
        filter_row.pack(fill="x", pady=4)

        tk.Label(filter_row, text="Hệ:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_sub, width=4, anchor="w").pack(side="left")
        self.filter_magic_var = tk.StringVar(value="Tất cả")
        cb_f_magic = ttk.Combobox(filter_row, textvariable=self.filter_magic_var,
                                  values=["Tất cả"] + ELEMENTS_LIST, width=12, state="readonly")
        cb_f_magic.pack(side="left", padx=(2, 8))
        cb_f_magic.bind("<<ComboboxSelected>>", lambda e: self.filter_skills_tree())

        tk.Label(filter_row, text="Bậc:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_sub, width=4, anchor="w").pack(side="left")
        self.filter_tier_var = tk.StringVar(value="Tất cả")
        cb_f_tier = ttk.Combobox(filter_row, textvariable=self.filter_tier_var,
                                 values=["Tất cả", "Basic", "Mid", "High", "Ultimate"], width=10, state="readonly")
        cb_f_tier.pack(side="left", padx=(2, 0))
        cb_f_tier.bind("<<ComboboxSelected>>", lambda e: self.filter_skills_tree())

        # Treeview danh sách skill
        tree_container = tk.Frame(left_frame, bg=self.c_bg)
        tree_container.pack(fill="both", expand=True, padx=6, pady=6)

        columns = ("id", "name", "magic", "tier", "base", "scale", "cd")
        self.skills_tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="browse")
        self.skills_tree.heading("id", text="ID", anchor="w")
        self.skills_tree.heading("name", text="Tên Skill", anchor="w")
        self.skills_tree.heading("magic", text="Hệ", anchor="center")
        self.skills_tree.heading("tier", text="Bậc", anchor="center")
        self.skills_tree.heading("base", text="Base", anchor="e")
        self.skills_tree.heading("scale", text="% ATK", anchor="e")
        self.skills_tree.heading("cd", text="CD (s)", anchor="e")

        self.skills_tree.column("id", width=85, minwidth=65)
        self.skills_tree.column("name", width=120, minwidth=85)
        self.skills_tree.column("magic", width=60, minwidth=50, anchor="center")
        self.skills_tree.column("tier", width=50, minwidth=40, anchor="center")
        self.skills_tree.column("base", width=45, minwidth=35, anchor="e")
        self.skills_tree.column("scale", width=55, minwidth=40, anchor="e")
        self.skills_tree.column("cd", width=45, minwidth=35, anchor="e")

        tree_sb = ttk.Scrollbar(tree_container, orient="vertical", command=self.skills_tree.yview)
        self.skills_tree.configure(yscrollcommand=tree_sb.set)

        self.skills_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")

        self.skills_tree.bind("<<TreeviewSelect>>", self.on_skill_tree_select)

        # Thanh nút thao tác bên dưới Treeview
        btn_action_bar = tk.Frame(left_frame, bg=self.c_sub, padx=8, pady=8)
        btn_action_bar.pack(fill="x", side="bottom")

        # Khung xem nhanh mô tả kỹ năng đang chọn
        desc_preview_box = tk.Frame(left_frame, bg=self.c_sub, padx=8, pady=4)
        desc_preview_box.pack(fill="x", side="bottom", padx=6, pady=(0, 4))

        tk.Label(desc_preview_box, text="Mô tả kỹ năng:", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_sub).pack(anchor="w")
        self.lbl_sk_quick_desc = tk.Label(desc_preview_box, text="(Chọn một kỹ năng để xem mô tả)", font=("Segoe UI", 8),
                                          fg="#cccccc", bg=self.c_sub, wraplength=440, justify="left")
        self.lbl_sk_quick_desc.pack(anchor="w", pady=(1, 2))

        btn_new = tk.Button(btn_action_bar, text="+ Tạo Mới", bg="#2a2a2a", fg="#ffffff",
                            font=("Segoe UI", 9, "bold"), relief="solid", bd=1, padx=8, pady=4,
                            cursor="hand2", activebackground="#3d3d3d", command=self.new_skill_form)
        btn_new.pack(side="left", padx=2)

        btn_clone = tk.Button(btn_action_bar, text="📋 Nhân Bản", bg="#2a2a2a", fg="#ffffff",
                              font=("Segoe UI", 8), relief="solid", bd=1, padx=6, pady=4,
                              cursor="hand2", activebackground="#3d3d3d", command=self.clone_skill_action)
        btn_clone.pack(side="left", padx=2)

        btn_del = tk.Button(btn_action_bar, text="🗑 Xóa", bg="#2a2a2a", fg="#ff6666",
                            font=("Segoe UI", 8), relief="solid", bd=1, padx=6, pady=4,
                            cursor="hand2", activebackground="#442222", command=self.delete_skill_action)
        btn_del.pack(side="left", padx=2)

        self.lbl_skill_count = tk.Label(btn_action_bar, text="", font=("Segoe UI", 8),
                                        fg=self.c_muted, bg=self.c_sub)
        self.lbl_skill_count.pack(side="right", padx=4)

        # CỘT PHẢI: FORM CHỈNH SỬA & TẠO SKILL (SCROLLABLE CANVAS)
        right_frame = tk.Frame(main_box, bg=self.c_surface, bd=1, relief="solid")
        right_frame.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=0)

        # Top bar editor
        ed_top = tk.Frame(right_frame, bg=self.c_sub, padx=12, pady=8)
        ed_top.pack(fill="x")
        self.lbl_editor_status = tk.Label(ed_top, text="[ THÔNG TIN KỸ NĂNG ]",
                                          font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_sub)
        self.lbl_editor_status.pack(side="left")

        # Scrollable form canvas
        ed_canvas = tk.Canvas(right_frame, bg=self.c_surface, highlightthickness=0)
        ed_sb = ttk.Scrollbar(right_frame, orient="vertical", command=ed_canvas.yview)
        ed_form = tk.Frame(ed_canvas, bg=self.c_surface, padx=14, pady=10)

        ed_form.bind("<Configure>", lambda e: ed_canvas.configure(scrollregion=ed_canvas.bbox("all")))
        ed_win = ed_canvas.create_window((0, 0), window=ed_form, anchor="nw")
        ed_canvas.configure(yscrollcommand=ed_sb.set)

        def _on_ed_canvas_configure(e):
            ed_canvas.itemconfig(ed_win, width=e.width)
        ed_canvas.bind("<Configure>", _on_ed_canvas_configure)

        def _on_ed_mousewheel(event):
            ed_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        ed_canvas.bind("<Enter>", lambda e: ed_canvas.bind_all("<MouseWheel>", _on_ed_mousewheel))
        ed_canvas.bind("<Leave>", lambda e: ed_canvas.unbind_all("<MouseWheel>"))

        ed_canvas.pack(side="left", fill="both", expand=True)
        ed_sb.pack(side="right", fill="y")

        # --- CÁC TRƯỜNG THÔNG TIN CỦA SKILL ---
        # 1. Định danh (ID & Tên)
        id_frame = tk.Frame(ed_form, bg=self.c_surface)
        id_frame.pack(fill="x", pady=(0, 8))

        # ID
        f_id = tk.Frame(id_frame, bg=self.c_surface)
        f_id.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f_id, text="Skill ID (Mã định danh duy nhất):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 2))
        self.ent_sk_id = tk.Entry(f_id, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                  relief="solid", bd=1, font=("Consolas", 10))
        self.ent_sk_id.pack(fill="x")

        # Name
        f_name = tk.Frame(id_frame, bg=self.c_surface)
        f_name.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(f_name, text="Tên hiển thị (Skill Name):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 2))
        self.ent_sk_name = tk.Entry(f_name, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                    relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_name.pack(fill="x")

        # 2. Phân loại (Magic & Tier)
        type_frame = tk.Frame(ed_form, bg=self.c_surface)
        type_frame.pack(fill="x", pady=(0, 8))

        f_magic = tk.Frame(type_frame, bg=self.c_surface)
        f_magic.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f_magic, text="Hệ nguyên tố (Magic):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 2))
        self.cb_sk_magic = ttk.Combobox(f_magic, values=ELEMENTS_LIST, state="readonly", font=("Segoe UI", 9))
        self.cb_sk_magic.pack(fill="x")

        f_tier = tk.Frame(type_frame, bg=self.c_surface)
        f_tier.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(f_tier, text="Bậc kỹ năng (Tier):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 2))
        self.cb_sk_tier = ttk.Combobox(f_tier, values=["Basic", "Mid", "High", "Ultimate"],
                                       state="readonly", font=("Segoe UI", 9))
        self.cb_sk_tier.pack(fill="x")

        # 2.5. Mô tả kỹ năng (Skill Description)
        desc_frame = tk.Frame(ed_form, bg=self.c_surface)
        desc_frame.pack(fill="x", pady=(0, 8))

        tk.Label(desc_frame, text="Mô tả kỹ năng (Skill Description):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 2))
        self.txt_sk_desc = tk.Text(desc_frame, height=3, wrap="word", bg="#121212", fg="#ffffff",
                                   insertbackground="#ffffff", relief="solid", bd=1,
                                   font=("Segoe UI", 9))
        self.txt_sk_desc.pack(fill="x")

        # 3. Thông số số học (Grid 2 cột)
        stat_box = tk.LabelFrame(ed_form, text=" CHỈ SỐ CƠ BẢN (NUMERIC STATS) ",
                                 font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface,
                                 padx=10, pady=8, bd=1, relief="solid")
        stat_box.pack(fill="x", pady=(0, 8))

        # Row 1: base & atk_scale & true_base
        r1 = tk.Frame(stat_box, bg=self.c_surface)
        r1.pack(fill="x", pady=2)
        f_base = tk.Frame(r1, bg=self.c_surface)
        f_base.pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Label(f_base, text="Sát thương gốc (base):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_base = tk.Entry(f_base, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                    relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_base.pack(fill="x")

        f_scale = tk.Frame(r1, bg=self.c_surface)
        f_scale.pack(side="left", fill="x", expand=True, padx=(3, 3))
        tk.Label(f_scale, text="Scale % ATK (vd: 1.0 = 100%):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_atk_scale = tk.Entry(f_scale, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_atk_scale.pack(fill="x")

        f_true = tk.Frame(r1, bg=self.c_surface)
        f_true.pack(side="left", fill="x", expand=True, padx=(3, 0))
        tk.Label(f_true, text="Sát thương chuẩn (true_base):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_true_base = tk.Entry(f_true, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_true_base.pack(fill="x")

        # Row 2: cd & cast_time
        r2 = tk.Frame(stat_box, bg=self.c_surface)
        r2.pack(fill="x", pady=2)
        f_cd = tk.Frame(r2, bg=self.c_surface)
        f_cd.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(f_cd, text="Hồi chiêu (cd - giây):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_cd = tk.Entry(f_cd, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                  relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_cd.pack(fill="x")

        f_cast = tk.Frame(r2, bg=self.c_surface)
        f_cast.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(f_cast, text="Thời gian ra đòn (cast_time - giây, 0 = GCD):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_cast_time = tk.Entry(f_cast, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_cast_time.pack(fill="x")

        # Row 3: hits & hit_interval
        r3 = tk.Frame(stat_box, bg=self.c_surface)
        r3.pack(fill="x", pady=2)
        f_hits = tk.Frame(r3, bg=self.c_surface)
        f_hits.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(f_hits, text="Số đòn đánh (hits: 1=đơn, >1=đa đòn, 0=buff/heal):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_hits = tk.Entry(f_hits, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                    relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_hits.pack(fill="x")

        f_hint = tk.Frame(r3, bg=self.c_surface)
        f_hint.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(f_hint, text="Khoảng cách giữa các hit (hit_interval - s):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_hit_interval = tk.Entry(f_hint, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                            relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_hit_interval.pack(fill="x")

        # Row 4: charges & hit_chance & lifetime
        r4 = tk.Frame(stat_box, bg=self.c_surface)
        r4.pack(fill="x", pady=2)
        f_chg = tk.Frame(r4, bg=self.c_surface)
        f_chg.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(f_chg, text="Tích trữ tối đa (charges):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_charges = tk.Entry(f_chg, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                       relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_charges.pack(fill="x")

        f_hch = tk.Frame(r4, bg=self.c_surface)
        f_hch.pack(side="left", fill="x", expand=True, padx=(4, 4))
        tk.Label(f_hch, text="Tỉ lệ trúng (hit_chance, trống = chuẩn):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_hit_chance = tk.Entry(f_hch, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                          relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_hit_chance.pack(fill="x")

        f_life = tk.Frame(r4, bg=self.c_surface)
        f_life.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(f_life, text="Tồn tại (lifetime - s, trống = null):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_sk_lifetime = tk.Entry(f_life, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                        relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_sk_lifetime.pack(fill="x")

        # 4. Hiệu ứng đặc biệt (Effects & Quick Presets)
        eff_box = tk.LabelFrame(ed_form, text=" HIỆU ỨNG ĐẶC BIỆT (EFFECTS) ",
                                font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface,
                                padx=10, pady=8, bd=1, relief="solid")
        eff_box.pack(fill="x", pady=(0, 10))

        tk.Label(eff_box, text="Thêm nhanh mẫu hiệu ứng (Quick Presets):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(0, 4))

        # Preset buttons bar 1
        p_row1 = tk.Frame(eff_box, bg=self.c_surface)
        p_row1.pack(fill="x", pady=2)

        tk.Button(p_row1, text="+ Slow (Làm chậm)", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "slow", "value": 0.3, "duration": 3.0, "name": "slow"})).pack(side="left", padx=2)

        tk.Button(p_row1, text="+ Choáng (Stun)", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "stun", "duration": 1.5})).pack(side="left", padx=2)

        tk.Button(p_row1, text="+ DoT (Sát thương/s)", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "dot", "dps_base": 40.0, "atk_coef": 0.1, "duration": 5.0, "tick": 0.5, "magic": self.cb_sk_magic.get() or "Neutral"})).pack(side="left", padx=2)

        tk.Button(p_row1, text="+ Buff ATK", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "buff", "to": "self", "stat": "atk", "mode": "pct", "value": 0.2, "duration": 6.0, "name": "buff_atk"})).pack(side="left", padx=2)

        # Preset buttons bar 2
        p_row2 = tk.Frame(eff_box, bg=self.c_surface)
        p_row2.pack(fill="x", pady=2)

        tk.Button(p_row2, text="+ Debuff DEF", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "debuff", "to": "enemy", "stat": "def", "mode": "pct", "value": -0.2, "duration": 5.0, "name": "weaken"})).pack(side="left", padx=2)

        tk.Button(p_row2, text="+ Hồi Máu (Heal)", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "heal", "to": "self", "pct_max": 0.15, "amount": 0.0})).pack(side="left", padx=2)

        tk.Button(p_row2, text="+ Khiên (Shield)", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "shield", "to": "self", "pct_max": 0.2, "duration": 6.0})).pack(side="left", padx=2)

        tk.Button(p_row2, text="+ True Damage", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=lambda: self.add_effect_preset({"type": "true_damage", "amount": 100.0})).pack(side="left", padx=2)

        tk.Button(p_row2, text="✕ Xóa hết", bg="#332222", fg="#ff8888", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=2, cursor="hand2",
                  command=self.clear_effects).pack(side="left", padx=6)

        # JSON Text Area
        tk.Label(eff_box, text="Dữ liệu JSON Hiệu ứng (Có thể trực tiếp chỉnh sửa cấu trúc danh sách bên dưới):",
                 font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w", pady=(6, 2))
        self.txt_sk_effects = tk.Text(eff_box, height=6, bg="#121212", fg="#ffffff",
                                      insertbackground="#ffffff", relief="solid", bd=1,
                                      font=("Consolas", 9), wrap="none")
        self.txt_sk_effects.pack(fill="x", expand=True)

        # 5. Thanh nút Lưu & Đặt lại
        action_bar = tk.Frame(ed_form, bg=self.c_surface)
        action_bar.pack(fill="x", pady=6)

        btn_save = tk.Button(action_bar, text="💾 LƯU / CẬP NHẬT KỸ NĂNG", bg="#ffffff", fg="#000000",
                             font=("Segoe UI", 10, "bold"), relief="solid", bd=1, padx=16, pady=6,
                             cursor="hand2", activebackground="#dddddd", command=self.save_skill_action)
        btn_save.pack(side="left", padx=(0, 8))

        btn_reset = tk.Button(action_bar, text="🔄 Đặt Lại Form", bg="#2a2a2a", fg="#ffffff",
                              font=("Segoe UI", 9), relief="solid", bd=1, padx=12, pady=6,
                              cursor="hand2", activebackground="#3d3d3d", command=self.reset_skill_form)
        btn_reset.pack(side="left")

        self.lbl_sk_msg = tk.Label(ed_form, text="", font=("Segoe UI", 9, "bold"),
                                   fg="#00e676", bg=self.c_surface)
        self.lbl_sk_msg.pack(anchor="w", pady=(6, 0))

        # Khởi tạo nạp dữ liệu Treeview
        self.filter_skills_tree()

    def filter_skills_tree(self):
        query = self.ent_skill_search.get().strip().lower()
        magic_f = self.filter_magic_var.get()
        tier_f = self.filter_tier_var.get()

        for item in self.skills_tree.get_children():
            self.skills_tree.delete(item)

        skills = self.cfg.get("skills", {})
        displayed_count = 0
        total_count = 0

        for sk_id, sk in sorted(skills.items(), key=lambda x: str(x[0])):
            if not isinstance(sk, dict):
                continue
            total_count += 1

            sk_name = str(sk.get("name", sk_id))
            sk_magic = str(sk.get("magic", ""))
            sk_tier = str(sk.get("tier", ""))
            sk_base = str(sk.get("base", 0))
            sk_cd = str(sk.get("cd", 0))

            if magic_f != "Tất cả" and sk_magic != magic_f:
                continue
            if tier_f != "Tất cả" and sk_tier != tier_f:
                continue

            sk_desc = str(sk.get("desc", sk.get("description", ""))).lower()
            if query:
                if query not in sk_id.lower() and query not in sk_name.lower() and query not in sk_desc:
                    continue

            sk_scale_val = sk.get("atk_scale", sk.get("atk_pct", sk.get("scale_atk", 1.0)))
            try:
                sk_scale = f"{round(float(sk_scale_val) * 100)}%"
            except Exception:
                sk_scale = "100%"

            self.skills_tree.insert("", "end", iid=sk_id, values=(sk_id, sk_name, sk_magic, sk_tier, sk_base, sk_scale, sk_cd))
            displayed_count += 1

        self.lbl_skill_count.config(text=f"Hiển thị: {displayed_count}/{total_count}")

    def on_skill_tree_select(self, event=None):
        sel = self.skills_tree.selection()
        if not sel:
            return
        sk_id = sel[0]
        sk = self.cfg.get("skills", {}).get(sk_id)
        if not isinstance(sk, dict):
            return

        desc = sk.get("desc", sk.get("description", ""))
        scale_val = sk.get("atk_scale", sk.get("atk_pct", sk.get("scale_atk", 1.0)))
        try:
            scale_pct = f"{round(float(scale_val) * 100)}%"
        except Exception:
            scale_pct = "100%"
        preview_text = f"• [Hệ: {sk.get('magic', '')} | Tier: {sk.get('tier', '')} | Dame: {sk.get('base', 0)} + {scale_pct} ATK | CD: {sk.get('cd', 0)}s]\n" + (desc if desc else "(Chưa có mô tả)")

        self.editing_skill_id = sk_id
        self.lbl_editor_status.config(text=f"[ CHỈNH SỬA KỸ NĂNG: {sk_id} ]")
        if hasattr(self, "lbl_sk_quick_desc"):
            self.lbl_sk_quick_desc.config(text=preview_text)

        self.ent_sk_id.delete(0, "end")
        self.ent_sk_id.insert(0, sk_id)

        self.ent_sk_name.delete(0, "end")
        self.ent_sk_name.insert(0, sk.get("name", sk_id))

        self.cb_sk_magic.set(sk.get("magic", "Amgar"))
        self.cb_sk_tier.set(sk.get("tier", "Mid"))

        self.ent_sk_base.delete(0, "end")
        self.ent_sk_base.insert(0, str(sk.get("base", 0)))

        self.ent_sk_atk_scale.delete(0, "end")
        self.ent_sk_atk_scale.insert(0, str(scale_val))

        self.ent_sk_true_base.delete(0, "end")
        self.ent_sk_true_base.insert(0, str(sk.get("true_base", 0)))

        self.ent_sk_cd.delete(0, "end")
        self.ent_sk_cd.insert(0, str(sk.get("cd", 1.5)))

        self.ent_sk_cast_time.delete(0, "end")
        self.ent_sk_cast_time.insert(0, str(sk.get("cast_time", 0.0)))

        self.ent_sk_hits.delete(0, "end")
        self.ent_sk_hits.insert(0, str(sk.get("hits", 1)))

        self.ent_sk_hit_interval.delete(0, "end")
        self.ent_sk_hit_interval.insert(0, str(sk.get("hit_interval", 0.2)))

        self.ent_sk_charges.delete(0, "end")
        self.ent_sk_charges.insert(0, str(sk.get("charges", 1)))

        self.ent_sk_hit_chance.delete(0, "end")
        if sk.get("hit_chance") is not None:
            self.ent_sk_hit_chance.insert(0, str(sk.get("hit_chance")))

        self.ent_sk_lifetime.delete(0, "end")
        if sk.get("lifetime") is not None:
            self.ent_sk_lifetime.insert(0, str(sk.get("lifetime")))

        desc = sk.get("desc", sk.get("description", ""))
        self.txt_sk_desc.delete("1.0", "end")
        self.txt_sk_desc.insert("1.0", desc)
        if hasattr(self, "lbl_sk_quick_desc"):
            self.lbl_sk_quick_desc.config(text=desc if desc else "(Chưa có mô tả)")

        self.txt_sk_effects.delete("1.0", "end")
        effs = sk.get("effects", [])
        self.txt_sk_effects.insert("1.0", json.dumps(effs, ensure_ascii=False, indent=2))
        self.lbl_sk_msg.config(text="")

    def new_skill_form(self):
        self.editing_skill_id = None
        self.skills_tree.selection_remove(self.skills_tree.selection())
        self.lbl_editor_status.config(text="[ TẠO KỸ NĂNG MỚI ]")

        # Sinh mã ID tạm không trùng
        num = 1
        while f"custom_skill_{num}" in self.cfg.get("skills", {}):
            num += 1
        new_id = f"custom_skill_{num}"

        self.ent_sk_id.delete(0, "end")
        self.ent_sk_id.insert(0, new_id)

        self.ent_sk_name.delete(0, "end")
        self.ent_sk_name.insert(0, f"Kỹ Năng Mới {num}")

        cur_magic = self.filter_magic_var.get()
        self.cb_sk_magic.set(cur_magic if cur_magic != "Tất cả" else "Amgar")
        self.cb_sk_tier.set("Mid")

        self.ent_sk_base.delete(0, "end")
        self.ent_sk_base.insert(0, "80")

        self.ent_sk_atk_scale.delete(0, "end")
        self.ent_sk_atk_scale.insert(0, "1.0")

        self.ent_sk_true_base.delete(0, "end")
        self.ent_sk_true_base.insert(0, "0")

        self.ent_sk_cd.delete(0, "end")
        self.ent_sk_cd.insert(0, "3.0")

        self.ent_sk_cast_time.delete(0, "end")
        self.ent_sk_cast_time.insert(0, "0.0")

        self.ent_sk_hits.delete(0, "end")
        self.ent_sk_hits.insert(0, "1")

        self.ent_sk_hit_interval.delete(0, "end")
        self.ent_sk_hit_interval.insert(0, "0.2")

        self.ent_sk_charges.delete(0, "end")
        self.ent_sk_charges.insert(0, "1")

        self.ent_sk_hit_chance.delete(0, "end")
        self.ent_sk_lifetime.delete(0, "end")

        self.txt_sk_desc.delete("1.0", "end")
        if hasattr(self, "lbl_sk_quick_desc"):
            self.lbl_sk_quick_desc.config(text="(Chưa có mô tả)")

        self.txt_sk_effects.delete("1.0", "end")
        self.txt_sk_effects.insert("1.0", "[]")

        self.lbl_sk_msg.config(text="Đang tạo kỹ năng mới. Hãy chỉnh các thông số rồi bấm 'LƯU'.", fg=self.c_fg)

    def clone_skill_action(self):
        sel = self.skills_tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một kỹ năng trong danh sách để nhân bản!")
            return
        orig_id = sel[0]
        sk = self.cfg.get("skills", {}).get(orig_id)
        if not isinstance(sk, dict):
            return

        self.editing_skill_id = None
        self.skills_tree.selection_remove(sel)

        clone_id = f"{orig_id}_custom"
        c_num = 1
        while clone_id in self.cfg.get("skills", {}):
            clone_id = f"{orig_id}_custom{c_num}"
            c_num += 1

        self.lbl_editor_status.config(text=f"[ NHÂN BẢN TỪ: {orig_id} ]")

        self.ent_sk_id.delete(0, "end")
        self.ent_sk_id.insert(0, clone_id)

        self.ent_sk_name.delete(0, "end")
        self.ent_sk_name.insert(0, f"{sk.get('name', orig_id)} (Bản sao)")

        self.cb_sk_magic.set(sk.get("magic", "Amgar"))
        self.cb_sk_tier.set(sk.get("tier", "Mid"))

        self.ent_sk_base.delete(0, "end")
        self.ent_sk_base.insert(0, str(sk.get("base", 0)))

        self.ent_sk_atk_scale.delete(0, "end")
        self.ent_sk_atk_scale.insert(0, str(sk.get("atk_scale", sk.get("atk_pct", sk.get("scale_atk", 1.0)))))

        self.ent_sk_true_base.delete(0, "end")
        self.ent_sk_true_base.insert(0, str(sk.get("true_base", 0)))

        self.ent_sk_cd.delete(0, "end")
        self.ent_sk_cd.insert(0, str(sk.get("cd", 1.5)))

        self.ent_sk_cast_time.delete(0, "end")
        self.ent_sk_cast_time.insert(0, str(sk.get("cast_time", 0.0)))

        self.ent_sk_hits.delete(0, "end")
        self.ent_sk_hits.insert(0, str(sk.get("hits", 1)))

        self.ent_sk_hit_interval.delete(0, "end")
        self.ent_sk_hit_interval.insert(0, str(sk.get("hit_interval", 0.2)))

        self.ent_sk_charges.delete(0, "end")
        self.ent_sk_charges.insert(0, str(sk.get("charges", 1)))

        self.ent_sk_hit_chance.delete(0, "end")
        if sk.get("hit_chance") is not None:
            self.ent_sk_hit_chance.insert(0, str(sk.get("hit_chance")))

        self.ent_sk_lifetime.delete(0, "end")
        if sk.get("lifetime") is not None:
            self.ent_sk_lifetime.insert(0, str(sk.get("lifetime")))

        desc = sk.get("desc", sk.get("description", ""))
        self.txt_sk_desc.delete("1.0", "end")
        self.txt_sk_desc.insert("1.0", desc)
        if hasattr(self, "lbl_sk_quick_desc"):
            self.lbl_sk_quick_desc.config(text=desc if desc else "(Chưa có mô tả)")

        self.txt_sk_effects.delete("1.0", "end")
        effs = copy.deepcopy(sk.get("effects", []))
        self.txt_sk_effects.insert("1.0", json.dumps(effs, ensure_ascii=False, indent=2))

        self.lbl_sk_msg.config(text=f"Đã sao chép cấu trúc từ [{orig_id}]. Bấm 'LƯU' để hoàn tất.", fg=self.c_fg)

    def delete_skill_action(self):
        sel = self.skills_tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một kỹ năng cần xóa trong danh sách!")
            return
        sk_id = sel[0]
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa kỹ năng '{sk_id}' không?\nHành động này sẽ cập nhật config/skills.json."):
            return

        if sk_id in self.cfg.get("skills", {}):
            del self.cfg["skills"][sk_id]
            self.save_skills_to_disk()

        self.filter_skills_tree()
        self.reset_loadout_a()
        self.reset_loadout_b()
        self.new_skill_form()
        self.lbl_sk_msg.config(text=f"✓ Đã xóa kỹ năng [{sk_id}].", fg="#ff6666")

    def reset_skill_form(self):
        if self.editing_skill_id:
            self.on_skill_tree_select()
        else:
            self.new_skill_form()

    def add_effect_preset(self, preset):
        raw = self.txt_sk_effects.get("1.0", "end").strip()
        try:
            cur = json.loads(raw) if raw else []
            if not isinstance(cur, list):
                cur = []
        except Exception:
            cur = []
        cur.append(preset)
        self.txt_sk_effects.delete("1.0", "end")
        self.txt_sk_effects.insert("1.0", json.dumps(cur, ensure_ascii=False, indent=2))

    def clear_effects(self):
        self.txt_sk_effects.delete("1.0", "end")
        self.txt_sk_effects.insert("1.0", "[]")

    def save_skill_action(self):
        sk_id = self.ent_sk_id.get().strip()
        if not sk_id:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập Skill ID!")
            return

        name = self.ent_sk_name.get().strip() or sk_id
        magic = self.cb_sk_magic.get()
        if not magic:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng chọn Hệ nguyên tố (Magic)!")
            return

        tier = self.cb_sk_tier.get() or "Mid"

        try:
            base_val = float(self.ent_sk_base.get() or 0)
            base = int(base_val) if base_val == int(base_val) else base_val
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Sát thương cơ bản (base) phải là số!")
            return

        scale_raw = self.ent_sk_atk_scale.get().strip()
        atk_scale = 1.0
        if scale_raw:
            if scale_raw.endswith("%"):
                try:
                    atk_scale = float(scale_raw[:-1].strip()) / 100.0
                except ValueError:
                    messagebox.showerror("Lỗi dữ liệu", "Hệ số scale theo % ATK không hợp lệ (vd: 1.0 hoặc 100%)!")
                    return
            else:
                try:
                    atk_scale = float(scale_raw)
                except ValueError:
                    messagebox.showerror("Lỗi dữ liệu", "Hệ số scale theo % ATK phải là số (vd: 1.0 hoặc 1.2)!")
                    return

        try:
            true_val = float(self.ent_sk_true_base.get() or 0)
            true_base = int(true_val) if true_val == int(true_val) else true_val
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Sát thương chuẩn (true_base) phải là số!")
            return

        try:
            cd = float(self.ent_sk_cd.get() or 1.5)
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Hồi chiêu (cd) phải là số giây!")
            return

        try:
            cast_time = float(self.ent_sk_cast_time.get() or 0.0)
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Thời gian niệm (cast_time) phải là số giây!")
            return

        try:
            hits = int(float(self.ent_sk_hits.get() or 1))
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Số đòn đánh (hits) phải là số nguyên!")
            return

        try:
            hit_interval = float(self.ent_sk_hit_interval.get() or 0.2)
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Khoảng cách hit (hit_interval) phải là số giây!")
            return

        try:
            charges = int(float(self.ent_sk_charges.get() or 1))
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Số tích trữ (charges) phải là số nguyên!")
            return

        hit_chance_str = self.ent_sk_hit_chance.get().strip()
        hit_chance = None
        if hit_chance_str:
            try:
                hit_chance = float(hit_chance_str)
            except ValueError:
                messagebox.showerror("Lỗi dữ liệu", "Tỉ lệ trúng (hit_chance) phải là số float (vd 0.95)!")
                return

        lifetime_str = self.ent_sk_lifetime.get().strip()
        lifetime = None
        if lifetime_str:
            try:
                lifetime = float(lifetime_str)
            except ValueError:
                messagebox.showerror("Lỗi dữ liệu", "Thời gian tồn tại (lifetime) phải là số giây!")
                return

        desc = self.txt_sk_desc.get("1.0", "end").strip()

        eff_raw = self.txt_sk_effects.get("1.0", "end").strip()
        effects = []
        if eff_raw:
            try:
                effects = json.loads(eff_raw)
                if not isinstance(effects, list):
                    raise ValueError("Hiệu ứng phải là danh sách [] dạng JSON!")
            except Exception as e:
                messagebox.showerror("Lỗi JSON Hiệu ứng", f"Cú pháp JSON của effects không hợp lệ:\n{e}")
                return

        # Tạo đối tượng skill
        sk_dict = {
            "name": name,
            "magic": magic,
            "tier": tier,
            "base": base,
            "atk_scale": atk_scale,
            "cd": cd,
        }
        if desc:
            sk_dict["desc"] = desc
        if true_base > 0:
            sk_dict["true_base"] = true_base
        if cast_time > 0:
            sk_dict["cast_time"] = cast_time
        if hits != 1:
            sk_dict["hits"] = hits
        if hit_interval != 0.2 and hits > 1:
            sk_dict["hit_interval"] = hit_interval
        if charges > 1:
            sk_dict["charges"] = charges
        if hit_chance is not None:
            sk_dict["hit_chance"] = hit_chance
        if lifetime is not None:
            sk_dict["lifetime"] = lifetime
        if effects:
            sk_dict["effects"] = effects

        # Xử lý đổi tên ID nếu đang sửa
        if self.editing_skill_id and self.editing_skill_id != sk_id:
            if sk_id in self.cfg.get("skills", {}):
                if not messagebox.askyesno("Trùng ID", f"Skill ID '{sk_id}' đã tồn tại! Bạn có muốn ghi đè không?"):
                    return
            if self.editing_skill_id in self.cfg.get("skills", {}):
                del self.cfg["skills"][self.editing_skill_id]

        self.cfg.setdefault("skills", {})[sk_id] = sk_dict
        self.save_skills_to_disk()

        self.editing_skill_id = sk_id
        self.lbl_editor_status.config(text=f"[ CHỈNH SỬA KỸ NĂNG: {sk_id} ]")
        if hasattr(self, "lbl_sk_quick_desc"):
            scale_pct = f"{round(atk_scale * 100)}%"
            preview_text = f"• [Hệ: {magic} | Tier: {tier} | Dame: {base} + {scale_pct} ATK | CD: {cd}s]\n" + (desc if desc else "(Chưa có mô tả)")
            self.lbl_sk_quick_desc.config(text=preview_text)

        # Cập nhật lại UI
        self.filter_skills_tree()
        if self.skills_tree.exists(sk_id):
            self.skills_tree.selection_set(sk_id)
            self.skills_tree.see(sk_id)

        # Cập nhật các dropdown loadout ở Tab 1
        self.reset_loadout_a()
        self.reset_loadout_b()

        self.lbl_sk_msg.config(text=f"✓ Đã lưu kỹ năng [{sk_id}] vào hệ thống & config/skills.json!", fg="#00e676")

    def save_skills_to_disk(self):
        try:
            skills_path = os.path.join(HERE, "config", "skills.json")
            with open(skills_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg["skills"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", f"Không thể ghi config/skills.json:\n{e}")

    # -------------------------------------------------------------------------
    # TAB 5: KỊCH BẢN 1v1 (SCENARIOS & HỒ SƠ NGƯỜI CHƠI)
    # -------------------------------------------------------------------------
    def build_scenario_tab(self, parent):
        self.scen_sliders_meta = [
            {"key": "reaction_time", "label": "Phản xạ nhận diện (Reaction)", "min": 0.05, "max": 0.60, "step": 0.01, "unit": "s", "format": "float"},
            {"key": "dodge_rate", "label": "Tỉ lệ Né đòn (Dodge Rate)", "min": 0, "max": 90, "step": 1, "unit": "%", "format": "int"},
            {"key": "dodge_cd", "label": "Hồi chiêu Lướt né (Dodge CD)", "min": 0.8, "max": 3.0, "step": 0.1, "unit": "s", "format": "float"},
            {"key": "dodge_cost", "label": "Thể lực Né (Dodge Cost)", "min": 10, "max": 45, "step": 1, "unit": "sta", "format": "int"},
            {"key": "parry_rate", "label": "Tỉ lệ Đỡ gạt (Parry Rate)", "min": 0, "max": 80, "step": 1, "unit": "%", "format": "int"},
            {"key": "counter_stun", "label": "Choáng Parry (Counter Stun)", "min": 0.2, "max": 1.5, "step": 0.1, "unit": "s", "format": "float"},
            {"key": "guard_rate", "label": "Tỉ lệ Block thường (Guard)", "min": 0, "max": 80, "step": 1, "unit": "%", "format": "int"},
            {"key": "spacing", "label": "Giữ cự ly / Kiting (Spacing)", "min": 0.0, "max": 1.0, "step": 0.05, "unit": "", "format": "float"},
            {"key": "stamina_discipline", "label": "Kỷ luật thể lực (Discipline)", "min": 0.0, "max": 1.0, "step": 0.05, "unit": "", "format": "float"},
            {"key": "panic_hp_threshold", "label": "Ngưỡng máu áp lực (Panic HP)", "min": 10, "max": 50, "step": 1, "unit": "%", "format": "int"},
            {"key": "composure", "label": "Bản lĩnh tâm lý (Composure)", "min": 0.0, "max": 1.0, "step": 0.05, "unit": "", "format": "float"},
        ]

        main_box = tk.Frame(parent, bg=self.c_bg)
        main_box.pack(fill="both", expand=True, padx=8, pady=8)

        # CỘT TRÁI: DANH SÁCH KỊCH BẢN (320px)
        left_frame = tk.Frame(main_box, bg=self.c_surface, width=320, bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", padx=(0, 6), pady=0)
        left_frame.pack_propagate(False)

        top_l = tk.Frame(left_frame, bg=self.c_sub, padx=10, pady=8)
        top_l.pack(fill="x")
        tk.Label(top_l, text="DANH SÁCH KỊCH BẢN 1v1", font=("Segoe UI", 10, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w")

        # Listbox kịch bản
        lb_frame = tk.Frame(left_frame, bg=self.c_bg)
        lb_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.lb_scenarios = tk.Listbox(lb_frame, bg="#141414", fg="#ffffff", selectbackground="#383838",
                                       selectforeground="#ffffff", relief="solid", bd=1, font=("Segoe UI", 9))
        lb_sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.lb_scenarios.yview)
        self.lb_scenarios.configure(yscrollcommand=lb_sb.set)
        self.lb_scenarios.pack(side="left", fill="both", expand=True)
        lb_sb.pack(side="right", fill="y")
        self.lb_scenarios.bind("<<ListboxSelect>>", self.on_scenario_list_select)

        # Hộp mô tả ngắn
        desc_box = tk.Frame(left_frame, bg=self.c_surface, padx=8, pady=4)
        desc_box.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(desc_box, text="Mô tả tóm tắt kịch bản:", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.lbl_scen_brief = tk.Label(desc_box, text="", font=("Segoe UI", 8),
                                       fg="#cccccc", bg=self.c_surface, wraplength=290, justify="left")
        self.lbl_scen_brief.pack(anchor="w", pady=(2, 0))

        # Nút thao tác kịch bản
        btn_bar = tk.Frame(left_frame, bg=self.c_sub, padx=8, pady=8)
        btn_bar.pack(fill="x", side="bottom")

        tk.Button(btn_bar, text="+ Mới", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=6, pady=4, cursor="hand2", command=self.new_scenario_form).pack(side="left", padx=2)

        tk.Button(btn_bar, text="📋 Bản sao", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=4, cursor="hand2", command=self.clone_scenario_action).pack(side="left", padx=2)

        tk.Button(btn_bar, text="🗑 Xóa", bg="#2a2a2a", fg="#ff6666", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=4, cursor="hand2", command=self.delete_scenario_action).pack(side="left", padx=2)

        # CỘT PHẢI: FORM CHỈNH SỬA CHI TIẾT KỊCH BẢN & 2 NGƯỜI CHƠI
        right_frame = tk.Frame(main_box, bg=self.c_surface, bd=1, relief="solid")
        right_frame.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=0)

        # Top bar
        ed_top = tk.Frame(right_frame, bg=self.c_sub, padx=12, pady=8)
        ed_top.pack(fill="x")
        self.lbl_scen_editor_title = tk.Label(ed_top, text="[ THIẾT LẬP KỊCH BẢN & HỒ SƠ NGƯỜI CHƠI ]",
                                              font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_sub)
        self.lbl_scen_editor_title.pack(side="left")

        # Scrollable canvas for the editor
        sc_canvas = tk.Canvas(right_frame, bg=self.c_surface, highlightthickness=0)
        sc_sb = ttk.Scrollbar(right_frame, orient="vertical", command=sc_canvas.yview)
        sc_form = tk.Frame(sc_canvas, bg=self.c_surface, padx=12, pady=10)

        sc_form.bind("<Configure>", lambda e: sc_canvas.configure(scrollregion=sc_canvas.bbox("all")))
        sc_win = sc_canvas.create_window((0, 0), window=sc_form, anchor="nw")
        sc_canvas.configure(yscrollcommand=sc_sb.set)

        def _on_sc_canvas_configure(e):
            sc_canvas.itemconfig(sc_win, width=e.width)
        sc_canvas.bind("<Configure>", _on_sc_canvas_configure)

        def _on_sc_mousewheel(event):
            sc_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        sc_canvas.bind("<Enter>", lambda e: sc_canvas.bind_all("<MouseWheel>", _on_sc_mousewheel))
        sc_canvas.bind("<Leave>", lambda e: sc_canvas.unbind_all("<MouseWheel>"))

        sc_canvas.pack(side="left", fill="both", expand=True)
        sc_sb.pack(side="right", fill="y")

        # Thông tin kịch bản (Key, Name, Desc)
        meta_box = tk.LabelFrame(sc_form, text=" THÔNG TIN KỊCH BẢN ", font=("Segoe UI", 8, "bold"),
                                 fg=self.c_fg, bg=self.c_surface, padx=10, pady=8, bd=1, relief="solid")
        meta_box.pack(fill="x", pady=(0, 8))

        m_r1 = tk.Frame(meta_box, bg=self.c_surface)
        m_r1.pack(fill="x", pady=2)

        f_k = tk.Frame(m_r1, bg=self.c_surface)
        f_k.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f_k, text="Mã Kịch Bản (Key ID):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_scen_key = tk.Entry(f_k, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                     relief="solid", bd=1, font=("Consolas", 9))
        self.ent_scen_key.pack(fill="x")

        f_n = tk.Frame(m_r1, bg=self.c_surface)
        f_n.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(f_n, text="Tên Kịch Bản Hiển Thị:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_scen_name = tk.Entry(f_n, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                      relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_scen_name.pack(fill="x")

        m_r2 = tk.Frame(meta_box, bg=self.c_surface)
        m_r2.pack(fill="x", pady=(4, 2))
        tk.Label(m_r2, text="Mô tả bối cảnh / cơ chế thi đấu:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_scen_desc = tk.Entry(m_r2, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                      relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_scen_desc.pack(fill="x")

        # Khung 2 bên: NGƯỜI CHƠI ĐỘI A và NGƯỜI CHƠI ĐỘI B
        players_box = tk.Frame(sc_form, bg=self.c_surface)
        players_box.pack(fill="x", pady=(0, 8))

        f_pa = tk.LabelFrame(players_box, text=" [ NGƯỜI CHƠI ĐỘI A ] ", font=("Segoe UI", 9, "bold"),
                             fg=self.c_fg, bg=self.c_surface, padx=8, pady=8, bd=1, relief="solid")
        f_pa.pack(side="left", fill="both", expand=True, padx=(0, 4))

        f_pb = tk.LabelFrame(players_box, text=" [ NGƯỜI CHƠI ĐỘI B ] ", font=("Segoe UI", 9, "bold"),
                             fg=self.c_fg, bg=self.c_surface, padx=8, pady=8, bd=1, relief="solid")
        f_pb.pack(side="left", fill="both", expand=True, padx=(4, 0))

        self.build_player_controls(f_pa, "team_a")
        self.build_player_controls(f_pb, "team_b")

        # Thanh nút thao tác cuối form
        act_box = tk.Frame(sc_form, bg=self.c_surface)
        act_box.pack(fill="x", pady=6)

        btn_save = tk.Button(act_box, text="💾 LƯU KỊCH BẢN VÀO HỆ THỐNG", bg="#ffffff", fg="#000000",
                             font=("Segoe UI", 9, "bold"), relief="solid", bd=1, padx=16, pady=5,
                             cursor="hand2", activebackground="#dddddd", command=self.save_scenario_action)
        btn_save.pack(side="left", padx=(0, 8))

        btn_apply = tk.Button(act_box, text="⚔ ÁP DỤNG & VÀO ĐẤU 1v1", bg="#2a2a2a", fg="#ffffff",
                              font=("Segoe UI", 9, "bold"), relief="solid", bd=1, padx=14, pady=5,
                              cursor="hand2", activebackground="#3d3d3d", command=self.apply_and_switch_to_fight)
        btn_apply.pack(side="left")

        self.lbl_scen_msg = tk.Label(sc_form, text="", font=("Segoe UI", 9, "bold"),
                                     fg="#00e676", bg=self.c_surface)
        self.lbl_scen_msg.pack(anchor="w", pady=(4, 0))

        self.refresh_scenarios_listbox()

    def build_player_controls(self, parent_frame, team_key):
        vars_map = {}
        self.scen_player_vars[team_key] = vars_map

        # Hàng chọn Rank Preset
        pr_row = tk.Frame(parent_frame, bg=self.c_surface)
        pr_row.pack(fill="x", pady=(0, 6))

        tk.Label(pr_row, text="Mẫu Trình Độ (Rank):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_muted, bg=self.c_surface).pack(side="left")

        rank_keys = list(self.cfg.get("scenarios", {}).get("player_ranks", {}).keys())
        rank_titles = [self.cfg["scenarios"]["player_ranks"][k].get("rank_title", k) for k in rank_keys]
        cb_rank = ttk.Combobox(pr_row, values=rank_titles, state="readonly", width=22, font=("Segoe UI", 8))
        cb_rank.pack(side="right")
        vars_map["cb_rank"] = cb_rank

        def on_rank_change(e):
            idx = cb_rank.current()
            if 0 <= idx < len(rank_keys):
                rk = rank_keys[idx]
                r_data = self.cfg["scenarios"]["player_ranks"][rk]
                self.load_player_profile_into_controls(team_key, r_data)

        cb_rank.bind("<<ComboboxSelected>>", on_rank_change)

        # Danh xưng hiển thị
        title_row = tk.Frame(parent_frame, bg=self.c_surface)
        title_row.pack(fill="x", pady=(0, 6))
        tk.Label(title_row, text="Danh xưng:", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")
        ent_title = tk.Entry(title_row, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                             relief="solid", bd=1, font=("Segoe UI", 8))
        ent_title.pack(side="right", fill="x", expand=True, padx=(4, 0))
        vars_map["ent_title"] = ent_title

        # Các thanh trượt
        for m in self.scen_sliders_meta:
            k = m["key"]
            row = tk.Frame(parent_frame, bg=self.c_surface)
            row.pack(fill="x", pady=2)

            lbl = tk.Label(row, text=m["label"], width=26, anchor="w",
                           bg=self.c_surface, fg=self.c_fg, font=("Segoe UI", 8))
            lbl.pack(side="left")

            var = tk.DoubleVar()
            scale = ttk.Scale(row, from_=m["min"], to=m["max"], variable=var, orient="horizontal")
            scale.pack(side="left", fill="x", expand=True, padx=4)

            ent = tk.Entry(row, width=5, bg="#111111", fg="#ffffff",
                           relief="solid", bd=1, justify="right", font=("Segoe UI", 8))
            ent.pack(side="left", padx=2)

            tk.Label(row, text=m["unit"], width=3, anchor="w",
                     bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 8)).pack(side="left")

            vars_map[k] = {"var": var, "entry": ent, "scale": scale, "meta": m}

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

    def load_player_profile_into_controls(self, team_key, p_data):
        vars_map = self.scen_player_vars[team_key]
        vars_map["ent_title"].delete(0, "end")
        vars_map["ent_title"].insert(0, p_data.get("rank_title", team_key))

        flat = {
            "reaction_time": p_data.get("reaction_time", 0.22),
            "dodge_rate": int(p_data.get("dodge", {}).get("rate", 0.40) * 100),
            "dodge_cd": p_data.get("dodge", {}).get("cd", 1.5),
            "dodge_cost": int(p_data.get("dodge", {}).get("stamina_cost", 25)),
            "parry_rate": int(p_data.get("parry", {}).get("rate", 0.20) * 100),
            "counter_stun": p_data.get("parry", {}).get("counter_stun", 0.6),
            "guard_rate": int(p_data.get("guard", {}).get("rate", 0.35) * 100),
            "spacing": p_data.get("movement", {}).get("spacing", 0.50),
            "stamina_discipline": p_data.get("movement", {}).get("stamina_discipline", 0.50),
            "panic_hp_threshold": int(p_data.get("psychology", {}).get("panic_hp_threshold", 0.30) * 100),
            "composure": p_data.get("psychology", {}).get("composure", 0.60),
        }

        for m in self.scen_sliders_meta:
            k = m["key"]
            val = flat.get(k, m["min"])
            vars_map[k]["var"].set(val)
            vars_map[k]["entry"].delete(0, "end")
            vars_map[k]["entry"].insert(0, str(int(val) if m["format"] == "int" else round(val, 2)))

    def read_player_profile_from_controls(self, team_key):
        vars_map = self.scen_player_vars[team_key]
        title = vars_map["ent_title"].get().strip() or team_key

        def get_v(k, default=0.0):
            try:
                return float(vars_map[k]["entry"].get())
            except Exception:
                return default

        return {
            "rank_title": title,
            "reaction_time": get_v("reaction_time", 0.22),
            "dodge": {
                "rate": get_v("dodge_rate", 40.0) / 100.0,
                "cd": get_v("dodge_cd", 1.5),
                "stamina_cost": get_v("dodge_cost", 25.0),
                "iframes": 0.30
            },
            "parry": {
                "rate": get_v("parry_rate", 20.0) / 100.0,
                "counter_stun": get_v("counter_stun", 0.6),
                "stamina_cost": 10.0
            },
            "guard": {
                "rate": get_v("guard_rate", 35.0) / 100.0,
                "stamina_cost": 30.0
            },
            "movement": {
                "spacing": get_v("spacing", 0.50),
                "stamina_discipline": get_v("stamina_discipline", 0.50)
            },
            "psychology": {
                "panic_hp_threshold": get_v("panic_hp_threshold", 30.0) / 100.0,
                "composure": get_v("composure", 0.60)
            }
        }

    def refresh_scenarios_listbox(self):
        self.lb_scenarios.delete(0, "end")
        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        self.scen_list_keys = list(scens_dict.keys())
        for k in self.scen_list_keys:
            name = scens_dict[k].get("name", k)
            self.lb_scenarios.insert("end", f"{name}")

        cur_k = self.current_scenario_key.get()
        if cur_k in self.scen_list_keys:
            idx = self.scen_list_keys.index(cur_k)
            self.lb_scenarios.selection_set(idx)
            self.on_scenario_list_select()
        elif self.scen_list_keys:
            self.lb_scenarios.selection_set(0)
            self.on_scenario_list_select()

    def on_scenario_list_select(self, event=None):
        sel = self.lb_scenarios.curselection()
        if not sel:
            return
        idx = sel[0]
        scen_k = self.scen_list_keys[idx]
        scen_data = self.cfg.get("scenarios", {}).get("scenarios", {}).get(scen_k, {})

        self.editing_scenario_key = scen_k
        self.lbl_scen_editor_title.config(text=f"[ CHỈNH SỬA KỊCH BẢN: {scen_k} ]")

        self.ent_scen_key.delete(0, "end")
        self.ent_scen_key.insert(0, scen_k)

        self.ent_scen_name.delete(0, "end")
        self.ent_scen_name.insert(0, scen_data.get("name", scen_k))

        self.ent_scen_desc.delete(0, "end")
        self.ent_scen_desc.insert(0, scen_data.get("desc", ""))

        self.lbl_scen_brief.config(text=scen_data.get("desc", ""))

        self.load_player_profile_into_controls("team_a", scen_data.get("team_a", {}))
        self.load_player_profile_into_controls("team_b", scen_data.get("team_b", {}))

    def new_scenario_form(self):
        self.editing_scenario_key = None
        self.lb_scenarios.selection_clear(0, "end")
        self.lbl_scen_editor_title.config(text="[ TẠO KỊCH BẢN MỚI ]")

        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        num = 1
        while f"custom_scen_{num}" in scens_dict:
            num += 1
        new_k = f"custom_scen_{num}"

        self.ent_scen_key.delete(0, "end")
        self.ent_scen_key.insert(0, new_k)

        self.ent_scen_name.delete(0, "end")
        self.ent_scen_name.insert(0, f"Kịch Bản Tùy Chỉnh #{num}")

        self.ent_scen_desc.delete(0, "end")
        self.ent_scen_desc.insert(0, "Kịch bản tùy chỉnh do người dùng thiết lập.")
        self.lbl_scen_brief.config(text="Kịch bản tùy chỉnh mới.")

        ranks = self.cfg.get("scenarios", {}).get("player_ranks", {})
        def_r = ranks.get("platinum", {})
        self.load_player_profile_into_controls("team_a", def_r)
        self.load_player_profile_into_controls("team_b", def_r)

        self.lbl_scen_msg.config(text="Đang tạo kịch bản mới. Hãy tùy chỉnh thông số rồi nhấn 'LƯU'.", fg=self.c_fg)

    def clone_scenario_action(self):
        sel = self.lb_scenarios.curselection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một kịch bản để nhân bản!")
            return
        idx = sel[0]
        orig_k = self.scen_list_keys[idx]
        scen_data = self.cfg.get("scenarios", {}).get("scenarios", {}).get(orig_k, {})

        clone_k = f"{orig_k}_custom"
        c_num = 1
        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        while clone_k in scens_dict:
            clone_k = f"{orig_k}_custom{c_num}"
            c_num += 1

        self.editing_scenario_key = None
        self.lb_scenarios.selection_clear(0, "end")
        self.lbl_scen_editor_title.config(text=f"[ NHÂN BẢN TỪ: {orig_k} ]")

        self.ent_scen_key.delete(0, "end")
        self.ent_scen_key.insert(0, clone_k)

        self.ent_scen_name.delete(0, "end")
        self.ent_scen_name.insert(0, f"{scen_data.get('name', orig_k)} (Bản sao)")

        self.ent_scen_desc.delete(0, "end")
        self.ent_scen_desc.insert(0, scen_data.get("desc", ""))

        self.load_player_profile_into_controls("team_a", scen_data.get("team_a", {}))
        self.load_player_profile_into_controls("team_b", scen_data.get("team_b", {}))

        self.lbl_scen_msg.config(text=f"Đã sao chép cấu trúc từ [{orig_k}]. Nhấn 'LƯU' để hoàn tất.", fg=self.c_fg)

    def delete_scenario_action(self):
        sel = self.lb_scenarios.curselection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một kịch bản cần xóa!")
            return
        idx = sel[0]
        scen_k = self.scen_list_keys[idx]
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa kịch bản '{scen_k}' không?"):
            return

        scens_dict = self.cfg.get("scenarios", {}).get("scenarios", {})
        if scen_k in scens_dict:
            del scens_dict[scen_k]
            self.save_scenarios_to_disk()

        self.refresh_scenarios_listbox()
        self.refresh_combat_tab_scenarios()
        self.lbl_scen_msg.config(text=f"✓ Đã xóa kịch bản [{scen_k}].", fg="#ff6666")

    def save_scenario_action(self):
        k = self.ent_scen_key.get().strip()
        if not k:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập Mã Kịch Bản (Key ID)!")
            return

        name = self.ent_scen_name.get().strip() or k
        desc = self.ent_scen_desc.get().strip()

        pa = self.read_player_profile_from_controls("team_a")
        pb = self.read_player_profile_from_controls("team_b")

        scen_obj = {
            "name": name,
            "desc": desc,
            "team_a": pa,
            "team_b": pb
        }

        scens_dict = self.cfg.setdefault("scenarios", {}).setdefault("scenarios", {})

        if self.editing_scenario_key and self.editing_scenario_key != k:
            if k in scens_dict:
                if not messagebox.askyesno("Trùng mã", f"Kịch bản '{k}' đã tồn tại! Ghi đè?"):
                    return
            if self.editing_scenario_key in scens_dict:
                del scens_dict[self.editing_scenario_key]

        scens_dict[k] = scen_obj
        self.save_scenarios_to_disk()

        self.editing_scenario_key = k
        self.current_scenario_key.set(k)

        self.refresh_scenarios_listbox()
        self.refresh_combat_tab_scenarios()

        self.lbl_scen_msg.config(text=f"✓ Đã lưu kịch bản [{k}] vào config/scenarios.json!", fg="#00e676")

    def apply_and_switch_to_fight(self):
        self.save_scenario_action()
        self.notebook.select(0)

    def save_scenarios_to_disk(self):
        try:
            p = os.path.join(HERE, "config", "scenarios.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.cfg["scenarios"], f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", f"Không thể ghi config/scenarios.json:\n{e}")

    # =========================================================================
    # HỆ THỐNG BUILD PRESET & RELICS (TÙY BIẾN, LƯU TRỮ VÀ ÁP DỤNG PRESET)
    # =========================================================================
    def load_build_presets(self):
        try:
            if hasattr(self, "build_presets_path") and os.path.exists(self.build_presets_path):
                with open(self.build_presets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            print(f"Lỗi đọc build_presets.json: {e}")
        return {}

    def save_build_presets_to_disk(self):
        try:
            with open(self.build_presets_path, "w", encoding="utf-8") as f:
                json.dump(self.build_presets, f, ensure_ascii=False, indent=2)
            self.refresh_preset_comboboxes()
            if hasattr(self, "refresh_presets_tree"):
                self.refresh_presets_tree()
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", f"Không thể ghi config/build_presets.json:\n{e}")

    def refresh_preset_comboboxes(self):
        p_names = ["(Tùy chỉnh)"] + [p.get("name", pid) for pid, p in self.build_presets.items()]
        if hasattr(self, "cb_preset_a"):
            cur_a = self.cb_preset_a.get()
            self.cb_preset_a["values"] = p_names
            if cur_a in p_names:
                self.cb_preset_a.set(cur_a)
            else:
                self.cb_preset_a.set("(Tùy chỉnh)")
        if hasattr(self, "cb_preset_b"):
            cur_b = self.cb_preset_b.get()
            self.cb_preset_b["values"] = p_names
            if cur_b in p_names:
                self.cb_preset_b.set(cur_b)
            else:
                self.cb_preset_b.set("(Tùy chỉnh)")

    def get_all_relics_info(self):
        relics = []
        for k, v in self.cfg.get("relics", {}).items():
            if k.startswith("_"):
                continue
            name = v.get("name", k)
            desc_parts = []
            for m in v.get("mods", []):
                st = m.get("stat")
                mode = m.get("mode", "add")
                val = m.get("value", 0)
                if mode == "pct":
                    desc_parts.append(f"{st} +{val*100:.0f}%")
                else:
                    desc_parts.append(f"{st} +{val}")
            if v.get("grants"):
                desc_parts.append("Nội tại: " + ", ".join(v.get("grants")))
            if v.get("triggers"):
                desc_parts.append("Trigger chiến đấu")
            detail = " | ".join(desc_parts) if desc_parts else ""
            relics.append({
                "id": k,
                "name": name,
                "detail": detail,
                "is_passive": k.startswith("passive_")
            })
        return relics

    def open_relic_selector(self, current_selection, on_confirm_callback, title="CHỌN RELICS / NỘI TẠI"):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("540x640")
        win.minsize(480, 500)
        win.configure(bg=self.c_bg)
        win.transient(self)
        win.grab_set()

        top_bar = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        top_bar.pack(fill="x")
        tk.Label(top_bar, text=title, font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_sub).pack(side="left")

        lbl_count = tk.Label(top_bar, text="", font=("Segoe UI", 8, "bold"), fg="#00e676", bg=self.c_sub)
        lbl_count.pack(side="right")

        quick_bar = tk.Frame(win, bg=self.c_surface, padx=8, pady=5)
        quick_bar.pack(fill="x")

        canv_frame = tk.Frame(win, bg=self.c_bg)
        canv_frame.pack(fill="both", expand=True, padx=8, pady=6)

        canvas = tk.Canvas(canv_frame, bg=self.c_surface, highlightthickness=0)
        sb = ttk.Scrollbar(canv_frame, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=self.c_surface, padx=8, pady=6)

        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        c_win = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        def _on_cv_conf(e):
            canvas.itemconfig(c_win, width=e.width)
        canvas.bind("<Configure>", _on_cv_conf)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        relics_info = self.get_all_relics_info()
        check_vars = {}

        def update_count():
            cnt = sum(1 for v in check_vars.values() if v.get())
            lbl_count.config(text=f"Đã chọn: {cnt} Relics")

        def select_all():
            for v in check_vars.values():
                v.set(True)
            update_count()

        def clear_all():
            for v in check_vars.values():
                v.set(False)
            update_count()

        def select_mods():
            for r in relics_info:
                check_vars[r["id"]].set(not r["is_passive"])
            update_count()

        def select_passives():
            for r in relics_info:
                check_vars[r["id"]].set(r["is_passive"])
            update_count()

        tk.Button(quick_bar, text="Chọn Tất Cả", font=("Segoe UI", 8), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=6, command=select_all).pack(side="left", padx=2)
        tk.Button(quick_bar, text="Bỏ Chọn Hết", font=("Segoe UI", 8), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=6, command=clear_all).pack(side="left", padx=2)
        tk.Button(quick_bar, text="Chỉ Stat Mods", font=("Segoe UI", 8), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=6, command=select_mods).pack(side="left", padx=2)
        tk.Button(quick_bar, text="Chỉ Passives", font=("Segoe UI", 8), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=6, command=select_passives).pack(side="left", padx=2)

        cur_set = set(current_selection or [])

        for r in relics_info:
            rid = r["id"]
            var = tk.BooleanVar(value=(rid in cur_set))
            check_vars[rid] = var

            item_card = tk.Frame(scroll_content, bg="#202020", pady=4, padx=6, relief="solid", bd=1)
            item_card.pack(fill="x", pady=2)

            cb = tk.Checkbutton(item_card, text=r["name"], variable=var, font=("Segoe UI", 9, "bold"),
                                fg="#ffffff", bg="#202020", selectcolor="#000000",
                                activebackground="#202020", activeforeground="#ffffff",
                                command=update_count)
            cb.pack(anchor="w")

            sub_txt = f"[{rid}]" + (f"  -  {r['detail']}" if r['detail'] else "")
            tk.Label(item_card, text=sub_txt, font=("Consolas", 8), fg="#999999", bg="#202020",
                     wraplength=480, justify="left").pack(anchor="w", padx=22)

        update_count()

        bottom_bar = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        bottom_bar.pack(fill="x", side="bottom")

        def on_confirm():
            chosen = [rid for rid, v in check_vars.items() if v.get()]
            on_confirm_callback(chosen)
            win.destroy()

        btn_ok = tk.Button(bottom_bar, text="✓  ĐỒNG Ý VÀ ÁP DỤNG", font=("Segoe UI", 9, "bold"),
                           bg="#ffffff", fg="#000000", relief="flat", padx=16, pady=4,
                           cursor="hand2", command=on_confirm)
        btn_ok.pack(side="right", padx=4)

        btn_cancel = tk.Button(bottom_bar, text="Hủy", font=("Segoe UI", 9),
                               bg="#282828", fg="#ffffff", relief="solid", bd=1, padx=12, pady=4,
                               cursor="hand2", command=win.destroy)
        btn_cancel.pack(side="right", padx=4)

    def open_relics_dialog_a(self):
        def cb(chosen):
            self.selected_relics_a = chosen
            self.btn_relics_a.config(text=f"🛡 Relics: {len(chosen)}")
        self.open_relic_selector(self.selected_relics_a, cb, title="CHỌN RELICS CHO ĐỘI A")

    def open_relics_dialog_b(self):
        def cb(chosen):
            self.selected_relics_b = chosen
            self.btn_relics_b.config(text=f"🛡 Relics: {len(chosen)}")
        self.open_relic_selector(self.selected_relics_b, cb, title="CHỌN RELICS CHO ĐỘI B")

    def prompt_save_preset(self, default_id, default_name, on_save_callback):
        win = tk.Toplevel(self)
        win.title("LƯU THÀNH BUILD PRESET")
        win.geometry("420x240")
        win.configure(bg=self.c_bg)
        win.transient(self)
        win.grab_set()

        top = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="💾 LƯU CẤU HÌNH THÀNH PRESET MỚI", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w")

        body = tk.Frame(win, bg=self.c_surface, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Mã Preset (Key ID, chữ thường, không dấu):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        ent_id = tk.Entry(body, bg="#111111", fg="#ffffff", insertbackground="#ffffff",
                          relief="solid", bd=1, font=("Consolas", 9))
        ent_id.pack(fill="x", pady=(2, 8))
        ent_id.insert(0, default_id)

        tk.Label(body, text="Tên Preset Hiển Thị:", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        ent_name = tk.Entry(body, bg="#111111", fg="#ffffff", insertbackground="#ffffff",
                            relief="solid", bd=1, font=("Segoe UI", 9))
        ent_name.pack(fill="x", pady=(2, 8))
        ent_name.insert(0, default_name)

        tk.Label(body, text="Mô tả tóm tắt (tùy chọn):", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        ent_desc = tk.Entry(body, bg="#111111", fg="#ffffff", insertbackground="#ffffff",
                            relief="solid", bd=1, font=("Segoe UI", 9))
        ent_desc.pack(fill="x", pady=(2, 8))

        bottom = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        bottom.pack(fill="x", side="bottom")

        def on_ok():
            p_id = ent_id.get().strip()
            p_name = ent_name.get().strip() or p_id
            p_desc = ent_desc.get().strip()
            if not p_id:
                messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập Mã Preset!", parent=win)
                return
            if p_id in self.build_presets:
                if not messagebox.askyesno("Ghi đè?", f"Preset '{p_id}' đã tồn tại! Bạn có muốn ghi đè không?", parent=win):
                    return
            win.destroy()
            on_save_callback(p_id, p_name, p_desc)

        tk.Button(bottom, text="💾 Lưu Preset", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#000000",
                  relief="flat", padx=12, pady=3, cursor="hand2", command=on_ok).pack(side="right", padx=4)
        tk.Button(bottom, text="Hủy", font=("Segoe UI", 9), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=10, pady=3, cursor="hand2", command=win.destroy).pack(side="right", padx=4)

    def save_current_as_preset_a(self):
        e1 = self.cb_elem1_a.get()
        e2 = self.cb_elem2_a.get()
        def_id = f"{e1.lower()}_{e2.lower()}_preset"
        def_name = f"Build {e1} + {e2}" if e1 != e2 else f"PureType {e1}"

        def do_save(pid, pname, pdesc):
            skills_b = [self.cb_s3_a.get(), self.cb_s4_a.get()]
            s5 = self.cb_s5_a.get()
            if s5 and s5 not in ("(Không dùng)", "(Hết skill)"):
                skills_b.append(s5)

            stats_dict = {k: v["var"].get() for k, v in self.team_a_vars.items()}
            self.build_presets[pid] = {
                "name": pname,
                "desc": pdesc,
                "branch_a": {"magic": e1, "skills": [self.cb_s1_a.get(), self.cb_s2_a.get()]},
                "branch_b": {"magic": e2, "skills": skills_b},
                "basic": self.cb_basic_a.get(),
                "stats": stats_dict,
                "relics": list(self.selected_relics_a)
            }
            self.save_build_presets_to_disk()
            self.cb_preset_a.set(pname)
            messagebox.showinfo("Đã lưu", f"Đã lưu preset '{pname}' [{pid}] thành công!")

        self.prompt_save_preset(def_id, def_name, do_save)

    def save_current_as_preset_b(self):
        e1 = self.cb_elem1_b.get()
        e2 = self.cb_elem2_b.get()
        def_id = f"{e1.lower()}_{e2.lower()}_b"
        def_name = f"Build {e1} + {e2} (B)" if e1 != e2 else f"PureType {e1} (B)"

        def do_save(pid, pname, pdesc):
            skills_b2 = [self.cb_s3_b.get(), self.cb_s4_b.get()]
            s5 = self.cb_s5_b.get()
            if s5 and s5 not in ("(Không dùng)", "(Hết skill)"):
                skills_b2.append(s5)

            stats_dict = {k: v["var"].get() for k, v in self.team_b_fight_vars.items()}
            self.build_presets[pid] = {
                "name": pname,
                "desc": pdesc,
                "branch_a": {"magic": e1, "skills": [self.cb_s1_b.get(), self.cb_s2_b.get()]},
                "branch_b": {"magic": e2, "skills": skills_b2},
                "basic": self.cb_basic_b.get(),
                "stats": stats_dict,
                "relics": list(self.selected_relics_b)
            }
            self.save_build_presets_to_disk()
            self.cb_preset_b.set(pname)
            messagebox.showinfo("Đã lưu", f"Đã lưu preset '{pname}' [{pid}] thành công!")

        self.prompt_save_preset(def_id, def_name, do_save)

    def on_select_preset_a(self):
        val = self.cb_preset_a.get()
        if val == "(Tùy chỉnh)" or not val:
            return
        p_obj = None
        for pid, p in self.build_presets.items():
            if p.get("name") == val or pid == val:
                p_obj = p
                break
        if not p_obj:
            return
        self.apply_preset_to_team("a", p_obj)

    def on_select_preset_b(self):
        val = self.cb_preset_b.get()
        if val == "(Tùy chỉnh)" or not val:
            return
        p_obj = None
        for pid, p in self.build_presets.items():
            if p.get("name") == val or pid == val:
                p_obj = p
                break
        if not p_obj:
            return
        self.apply_preset_to_team("b", p_obj)

    def apply_preset_to_team(self, team_tag, p_obj):
        e1 = p_obj.get("branch_a", {}).get("magic", "Amgar")
        e2 = p_obj.get("branch_b", {}).get("magic", "Gale")
        basic = p_obj.get("basic", "")
        skills_a = p_obj.get("branch_a", {}).get("skills", [])
        skills_b = p_obj.get("branch_b", {}).get("skills", [])
        stats = p_obj.get("stats", {})
        relics = p_obj.get("relics", [])

        if team_tag == "a":
            self.cb_elem1_a.set(e1)
            self.cb_elem2_a.set(e2)
            self.on_elem_change_a()

            if basic:
                self.cb_basic_a.set(basic)
            if len(skills_a) > 0:
                self.cb_s1_a.set(skills_a[0])
            if len(skills_a) > 1:
                self.cb_s2_a.set(skills_a[1])
            if len(skills_b) > 0:
                self.cb_s3_a.set(skills_b[0])
            if len(skills_b) > 1:
                self.cb_s4_a.set(skills_b[1])
            if len(skills_b) > 2:
                self.cb_s5_a.set(skills_b[2])
            else:
                self.cb_s5_a.set("(Không dùng)")
            self.refresh_loadout_dropdowns_a()

            for k, info in self.team_a_vars.items():
                if k in stats:
                    val = stats[k]
                    info["var"].set(val)
                    info["entry"].delete(0, "end")
                    info["entry"].insert(0, str(val))

            self.selected_relics_a = list(relics)
            self.btn_relics_a.config(text=f"🛡 Relics: {len(self.selected_relics_a)}")
            self.cb_preset_a.set(p_obj.get("name", ""))

        elif team_tag == "b":
            self.target_type_b.set("build")
            self.on_toggle_b_type()
            self.cb_elem1_b.set(e1)
            self.cb_elem2_b.set(e2)
            self.on_elem_change_b()

            if basic:
                self.cb_basic_b.set(basic)
            if len(skills_a) > 0:
                self.cb_s1_b.set(skills_a[0])
            if len(skills_a) > 1:
                self.cb_s2_b.set(skills_a[1])
            if len(skills_b) > 0:
                self.cb_s3_b.set(skills_b[0])
            if len(skills_b) > 1:
                self.cb_s4_b.set(skills_b[1])
            if len(skills_b) > 2:
                self.cb_s5_b.set(skills_b[2])
            else:
                self.cb_s5_b.set("(Không dùng)")
            self.refresh_loadout_dropdowns_b()

            for k, info in self.team_b_fight_vars.items():
                if k in stats:
                    val = stats[k]
                    info["var"].set(val)
                    info["entry"].delete(0, "end")
                    info["entry"].insert(0, str(val))

            self.selected_relics_b = list(relics)
            self.btn_relics_b.config(text=f"🛡 Relics: {len(self.selected_relics_b)}")
            self.cb_preset_b.set(p_obj.get("name", ""))

    def apply_preset_to_current_dps_dummy(self):
        if not self.build_presets:
            messagebox.showinfo("Thông báo", "Chưa có Preset nào được lưu! Bạn có thể tạo preset ở Tab PRESET BUILDS.")
            return

        win = tk.Toplevel(self)
        win.title("ÁP DỤNG STATS TỪ PRESET VÀO DUMMY")
        win.geometry("380x200")
        win.configure(bg=self.c_bg)
        win.transient(self)
        win.grab_set()

        top = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="CHỌN PRESET ĐỂ SAO CHÉP CHỈ SỐ", font=("Segoe UI", 9, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w")

        body = tk.Frame(win, bg=self.c_surface, padx=16, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Chọn Preset cần lấy chỉ số:", font=("Segoe UI", 8),
                 fg=self.c_muted, bg=self.c_surface).pack(anchor="w")

        p_names = [p.get("name", pid) for pid, p in self.build_presets.items()]
        cb_p = ttk.Combobox(body, values=p_names, state="readonly", width=30)
        cb_p.set(p_names[0])
        cb_p.pack(fill="x", pady=6)

        bottom = tk.Frame(win, bg=self.c_sub, padx=12, pady=8)
        bottom.pack(fill="x", side="bottom")

        def on_apply():
            chosen_name = cb_p.get()
            target_p = None
            for pid, p in self.build_presets.items():
                if p.get("name") == chosen_name or pid == chosen_name:
                    target_p = p
                    break
            if target_p and "stats" in target_p:
                st = target_p["stats"]
                cur_dummy = self.dps_dummies[self.current_dps_idx]
                for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr", "guard_q", "res"]:
                    if k in st:
                        cur_dummy["stats"][k] = float(st[k])
                self.load_dps_dummy_to_sliders(self.current_dps_idx)
                self.render_dps_dummy_tabs()
                win.destroy()
                messagebox.showinfo("Thành công", f"Đã sao chép toàn bộ chỉ số từ Preset '{chosen_name}' vào Dummy #{self.current_dps_idx + 1}!")

        tk.Button(bottom, text="✓ Áp dụng", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#000000",
                  relief="flat", padx=12, pady=3, cursor="hand2", command=on_apply).pack(side="right", padx=4)
        tk.Button(bottom, text="Hủy", font=("Segoe UI", 9), bg="#282828", fg="#ffffff",
                  relief="solid", bd=1, padx=10, pady=3, cursor="hand2", command=win.destroy).pack(side="right", padx=4)

    # -------------------------------------------------------------------------
    # TAB 6: PRESET BUILDS (QUẢN LÝ, TẠO MỚI, TÙY BIẾN & LƯU TRỮ PRESET)
    # -------------------------------------------------------------------------
    def build_preset_tab(self, parent):
        main_box = tk.Frame(parent, bg=self.c_bg)
        main_box.pack(fill="both", expand=True, padx=8, pady=8)

        # CỘT TRÁI: DANH SÁCH PRESET (330px)
        left_frame = tk.Frame(main_box, bg=self.c_surface, width=330, bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", padx=(0, 6), pady=0)
        left_frame.pack_propagate(False)

        top_l = tk.Frame(left_frame, bg=self.c_sub, padx=10, pady=8)
        top_l.pack(fill="x")
        tk.Label(top_l, text="DANH SÁCH PRESET BUILD", font=("Segoe UI", 10, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w")

        # Tìm kiếm Preset
        search_box = tk.Frame(left_frame, bg=self.c_surface, padx=8, pady=4)
        search_box.pack(fill="x")
        tk.Label(search_box, text="🔍 Tìm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.ent_search_preset = tk.Entry(search_box, bg="#111111", fg="#ffffff", insertbackground="#ffffff",
                                          relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_search_preset.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.ent_search_preset.bind("<KeyRelease>", lambda e: self.refresh_presets_tree())

        # Treeview danh sách Preset
        tree_frame = tk.Frame(left_frame, bg=self.c_bg)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=4)

        tree_cols = ("name", "elem", "relics")
        self.tree_presets = ttk.Treeview(tree_frame, columns=tree_cols, show="headings", selectmode="browse")
        self.tree_presets.heading("name", text="Tên Preset")
        self.tree_presets.heading("elem", text="Nguyên Tố")
        self.tree_presets.heading("relics", text="Relics")

        self.tree_presets.column("name", width=130, anchor="w")
        self.tree_presets.column("elem", width=105, anchor="center")
        self.tree_presets.column("relics", width=50, anchor="center")

        tree_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_presets.yview)
        self.tree_presets.configure(yscrollcommand=tree_sb.set)

        self.tree_presets.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")
        self.tree_presets.bind("<<TreeviewSelect>>", self.on_preset_tree_select)

        # Hộp tóm tắt preset đang chọn
        card_box = tk.Frame(left_frame, bg="#181818", padx=8, pady=6, relief="solid", bd=1)
        card_box.pack(fill="x", padx=6, pady=(0, 6))

        tk.Label(card_box, text="TÓM TẮT PRESET:", font=("Segoe UI", 8, "bold"), fg=self.c_muted, bg="#181818").pack(anchor="w")
        self.lbl_preset_card = tk.Label(card_box, text="(Chọn hoặc tạo mới preset để xem)", font=("Segoe UI", 8),
                                        fg="#cccccc", bg="#181818", wraplength=300, justify="left")
        self.lbl_preset_card.pack(anchor="w", pady=(2, 0))

        # Thanh nút thao tác preset
        btn_bar = tk.Frame(left_frame, bg=self.c_sub, padx=6, pady=6)
        btn_bar.pack(fill="x", side="bottom")

        r_btn1 = tk.Frame(btn_bar, bg=self.c_sub)
        r_btn1.pack(fill="x", pady=1)

        tk.Button(r_btn1, text="+ Tạo Mới", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=6, pady=3, cursor="hand2", command=self.new_preset_form).pack(side="left", padx=2)
        tk.Button(r_btn1, text="📋 Nhân Bản", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=3, cursor="hand2", command=self.clone_preset_action).pack(side="left", padx=2)
        tk.Button(r_btn1, text="🗑 Xóa", bg="#2a2a2a", fg="#ff6666", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=6, pady=3, cursor="hand2", command=self.delete_preset_action).pack(side="left", padx=2)

        r_btn2 = tk.Frame(btn_bar, bg=self.c_sub)
        r_btn2.pack(fill="x", pady=(4, 1))

        tk.Button(r_btn2, text="➔ Đội A", bg="#242424", fg="#00e676", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=4, pady=2, cursor="hand2", command=self.apply_pform_and_switch_a).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(r_btn2, text="➔ Đội B", bg="#242424", fg="#00e676", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=4, pady=2, cursor="hand2", command=self.apply_pform_and_switch_b).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(r_btn2, text="➔ Dummy DPS", bg="#242424", fg="#00e676", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=4, pady=2, cursor="hand2", command=self.apply_pform_and_switch_dps).pack(side="left", padx=1, fill="x", expand=True)

        # CỘT PHẢI: FORM TÙY CHỈNH PRESET (SCROLLABLE CANVAS)
        right_frame = tk.Frame(main_box, bg=self.c_surface, bd=1, relief="solid")
        right_frame.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=0)

        ed_top = tk.Frame(right_frame, bg=self.c_sub, padx=12, pady=8)
        ed_top.pack(fill="x")
        self.lbl_pform_editor_title = tk.Label(ed_top, text="[ THIẾT LẬP PRESET BUILD ]",
                                               font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_sub)
        self.lbl_pform_editor_title.pack(side="left")

        p_canvas = tk.Canvas(right_frame, bg=self.c_surface, highlightthickness=0)
        p_sb = ttk.Scrollbar(right_frame, orient="vertical", command=p_canvas.yview)
        p_form = tk.Frame(p_canvas, bg=self.c_surface, padx=12, pady=8)

        p_form.bind("<Configure>", lambda e: p_canvas.configure(scrollregion=p_canvas.bbox("all")))
        p_win = p_canvas.create_window((0, 0), window=p_form, anchor="nw")
        p_canvas.configure(yscrollcommand=p_sb.set)

        def _on_p_canvas_configure(e):
            p_canvas.itemconfig(p_win, width=e.width)
        p_canvas.bind("<Configure>", _on_p_canvas_configure)

        def _on_p_mousewheel(event):
            p_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        p_canvas.bind("<Enter>", lambda e: p_canvas.bind_all("<MouseWheel>", _on_p_mousewheel))
        p_canvas.bind("<Leave>", lambda e: p_canvas.unbind_all("<MouseWheel>"))

        p_canvas.pack(side="left", fill="both", expand=True)
        p_sb.pack(side="right", fill="y")

        # 1. Thông tin chung Preset (Key ID, Name, Desc)
        meta_box = tk.LabelFrame(p_form, text=" 1. THÔNG TIN PRESET ", font=("Segoe UI", 8, "bold"),
                                 fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        meta_box.pack(fill="x", pady=(0, 6))

        m_r1 = tk.Frame(meta_box, bg=self.c_surface)
        m_r1.pack(fill="x", pady=2)

        f_k = tk.Frame(m_r1, bg=self.c_surface)
        f_k.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f_k, text="Mã Preset (Key ID):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_pform_key = tk.Entry(f_k, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                      relief="solid", bd=1, font=("Consolas", 9))
        self.ent_pform_key.pack(fill="x")

        f_n = tk.Frame(m_r1, bg=self.c_surface)
        f_n.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(f_n, text="Tên Preset Hiển Thị:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_pform_name = tk.Entry(f_n, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                       relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_pform_name.pack(fill="x")

        m_r2 = tk.Frame(meta_box, bg=self.c_surface)
        m_r2.pack(fill="x", pady=(4, 2))
        tk.Label(m_r2, text="Mô tả tóm tắt phong cách build:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_pform_desc = tk.Entry(m_r2, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                       relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_pform_desc.pack(fill="x")

        # 2. Tổ hợp 2 Nguyên Tố
        elem_box = tk.LabelFrame(p_form, text=" 2. TỔ HỢP NGUYÊN TỐ (BUILD) ", font=("Segoe UI", 8, "bold"),
                                 fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        elem_box.pack(fill="x", pady=(0, 6))

        el_r = tk.Frame(elem_box, bg=self.c_surface)
        el_r.pack(fill="x", pady=2)

        tk.Label(el_r, text="Nhánh 1:", bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.cb_pform_elem1 = ttk.Combobox(el_r, values=ELEMENTS_LIST, width=10, state="readonly")
        self.cb_pform_elem1.set("Amgar")
        self.cb_pform_elem1.pack(side="left", padx=2)
        self.cb_pform_elem1.bind("<<ComboboxSelected>>", lambda e: self.on_pform_elem_change())

        tk.Button(el_r, text="⇄", font=("Segoe UI", 8, "bold"), bg="#262626", fg="#ffffff",
                  relief="solid", bd=1, padx=4, cursor="hand2", command=self.swap_pform_elements).pack(side="left", padx=2)

        tk.Label(el_r, text="Nhánh 2:", bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(4, 0))
        self.cb_pform_elem2 = ttk.Combobox(el_r, values=ELEMENTS_LIST, width=10, state="readonly")
        self.cb_pform_elem2.set("Gale")
        self.cb_pform_elem2.pack(side="left", padx=2)
        self.cb_pform_elem2.bind("<<ComboboxSelected>>", lambda e: self.on_pform_elem_change())

        tk.Button(el_r, text="★ Pure", font=("Segoe UI", 7, "bold"), bg="#333333", fg="#ffffff",
                  relief="solid", bd=1, padx=4, cursor="hand2", command=self.make_pform_pure).pack(side="left", padx=2)

        self.lbl_pform_elem_status = tk.Label(el_r, text="", font=("Segoe UI", 8, "bold"),
                                              bg="#222222", fg="#ffffff", padx=6, pady=1, relief="solid", bd=1)
        self.lbl_pform_elem_status.pack(side="left", padx=(6, 0))

        # 3. Loadout Kỹ Năng (5 Skills)
        loadout_box = tk.LabelFrame(p_form, text=" 3. LOADOUT KỸ NĂNG (5 SKILLS) ", font=("Segoe UI", 8, "bold"),
                                    fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        loadout_box.pack(fill="x", pady=(0, 6))

        lr1 = tk.Frame(loadout_box, bg=self.c_surface)
        lr1.pack(fill="x", pady=1)

        self.lbl_pform_l1 = tk.Label(lr1, text="Nhánh 1:", width=9, anchor="w",
                                     bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_pform_l1.pack(side="left")

        tk.Label(lr1, text="Basic:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_basic = ttk.Combobox(lr1, width=12, state="readonly")
        self.cb_pform_basic.pack(side="left", padx=(1, 4))
        self.cb_pform_basic.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        tk.Label(lr1, text="S1:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_s1 = ttk.Combobox(lr1, width=11, state="readonly")
        self.cb_pform_s1.pack(side="left", padx=(1, 4))
        self.cb_pform_s1.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        tk.Label(lr1, text="S2:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_s2 = ttk.Combobox(lr1, width=11, state="readonly")
        self.cb_pform_s2.pack(side="left", padx=(1, 4))
        self.cb_pform_s2.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        lr2 = tk.Frame(loadout_box, bg=self.c_surface)
        lr2.pack(fill="x", pady=1)

        self.lbl_pform_l2 = tk.Label(lr2, text="Nhánh 2:", width=9, anchor="w",
                                     bg=self.c_surface, fg=self.c_muted, font=("Segoe UI", 7, "bold"))
        self.lbl_pform_l2.pack(side="left")

        tk.Label(lr2, text="S3:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_s3 = ttk.Combobox(lr2, width=11, state="readonly")
        self.cb_pform_s3.pack(side="left", padx=(1, 4))
        self.cb_pform_s3.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        tk.Label(lr2, text="S4:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_s4 = ttk.Combobox(lr2, width=11, state="readonly")
        self.cb_pform_s4.pack(side="left", padx=(1, 4))
        self.cb_pform_s4.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        tk.Label(lr2, text="S5:", bg=self.c_surface, fg=self.c_dim, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.cb_pform_s5 = ttk.Combobox(lr2, width=11, state="readonly")
        self.cb_pform_s5.pack(side="left", padx=(1, 4))
        self.cb_pform_s5.bind("<<ComboboxSelected>>", lambda e: self.on_pform_skill_change())

        tk.Button(lr2, text="↺", font=("Segoe UI", 7), bg="#242424", fg="#aaaaaa",
                  relief="solid", bd=1, padx=3, cursor="hand2", command=self.reset_pform_loadout).pack(side="left", padx=2)

        # 4. Lựa chọn Relics (Cổ vật & Nội tại tự chọn)
        relic_box = tk.LabelFrame(p_form, text=" 4. RELICS & NỘI TẠI TỰ CHỌN ", font=("Segoe UI", 8, "bold"),
                                  fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        relic_box.pack(fill="x", pady=(0, 6))

        r_top = tk.Frame(relic_box, bg=self.c_surface)
        r_top.pack(fill="x", pady=(0, 4))

        self.btn_pform_pick_relics = tk.Button(r_top, text="🛡 Chọn Relics (0 đã chọn)...", font=("Segoe UI", 8, "bold"),
                                               bg="#262626", fg="#00e676", relief="solid", bd=1, padx=8, pady=3,
                                               cursor="hand2", command=self.open_pform_relic_selector)
        self.btn_pform_pick_relics.pack(side="left")

        tk.Button(r_top, text="✕ Bỏ chọn hết", font=("Segoe UI", 7), bg="#202020", fg="#aaaaaa",
                  relief="solid", bd=1, padx=6, command=self.clear_pform_relics).pack(side="left", padx=6)

        self.frame_pform_chips = tk.Frame(relic_box, bg=self.c_surface)
        self.frame_pform_chips.pack(fill="x", pady=2)
        self.render_pform_relic_chips()

        # 5. Tùy chỉnh Chỉ Số (Custom Stats)
        stats_box = tk.LabelFrame(p_form, text=" 5. CHỈ SỐ NHÂN VẬT (STATS) ", font=("Segoe UI", 8, "bold"),
                                  fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        stats_box.pack(fill="x", pady=(0, 6))

        st_presets_row = tk.Frame(stats_box, bg=self.c_surface)
        st_presets_row.pack(fill="x", pady=(0, 4))
        tk.Label(st_presets_row, text="Chỉ số mẫu:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(0, 4))

        for p_name, p_k in [("↺ Gốc", "base"), ("Dồn Dame", "dps"), ("Pháp Sư", "caster"), ("Đỡ Đòn", "tank")]:
            tk.Button(st_presets_row, text=p_name, font=("Segoe UI", 7), bg="#262626", fg="#dddddd",
                      relief="solid", bd=1, padx=5, command=lambda k=p_k: self.apply_pform_stat_preset(k)).pack(side="left", padx=2)

        self.box_pform_sliders = tk.Frame(stats_box, bg=self.c_surface)
        self.box_pform_sliders.pack(fill="both", expand=True, pady=2)
        self.populate_team_sliders("preset_form", self.box_pform_sliders, self.preset_form_vars)

        # 6. Thanh Lưu & Phản Hồi
        save_box = tk.Frame(p_form, bg=self.c_surface, pady=8)
        save_box.pack(fill="x", pady=(4, 8))

        btn_save_p = tk.Button(save_box, text="💾 LƯU PRESET BUILD", font=("Segoe UI", 9, "bold"),
                               bg="#ffffff", fg="#000000", relief="flat", padx=18, pady=5,
                               cursor="hand2", activebackground="#dddddd", command=self.save_preset_action)
        btn_save_p.pack(side="left")

        btn_save_use = tk.Button(save_box, text="➔ Lưu & Sử dụng Đội A ngay", font=("Segoe UI", 8, "bold"),
                                 bg="#262626", fg="#00e676", relief="solid", bd=1, padx=12, pady=5,
                                 cursor="hand2", command=self.save_and_apply_to_team_a)
        btn_save_use.pack(side="left", padx=8)

        self.lbl_pform_msg = tk.Label(save_box, text="", font=("Segoe UI", 8, "bold"),
                                      bg=self.c_surface, fg="#00e676")
        self.lbl_pform_msg.pack(side="left", padx=8)

        self.on_pform_elem_change()
        self.refresh_presets_tree()

    # --- Các phương thức xử lý Tab 6 (Preset Builds) ---
    def refresh_presets_tree(self):
        for item in self.tree_presets.get_children():
            self.tree_presets.delete(item)

        filter_txt = (self.ent_search_preset.get() if hasattr(self, "ent_search_preset") else "").lower().strip()

        for pid, p in sorted(self.build_presets.items()):
            name = p.get("name", pid)
            e1 = p.get("branch_a", {}).get("magic", "-")
            e2 = p.get("branch_b", {}).get("magic", "-")
            elem_str = f"Pure {e1}" if e1 == e2 else f"{e1}+{e2}"
            relics_cnt = str(len(p.get("relics", [])))

            if filter_txt and (filter_txt not in pid.lower() and filter_txt not in name.lower() and filter_txt not in elem_str.lower()):
                continue

            self.tree_presets.insert("", "end", iid=pid, values=(name, elem_str, relics_cnt))

    def on_preset_tree_select(self, event=None):
        sel = self.tree_presets.selection()
        if not sel:
            return
        pid = sel[0]
        p = self.build_presets.get(pid)
        if not p:
            return

        self.editing_preset_key = pid
        self.ent_pform_key.delete(0, "end")
        self.ent_pform_key.insert(0, pid)

        self.ent_pform_name.delete(0, "end")
        self.ent_pform_name.insert(0, p.get("name", pid))

        self.ent_pform_desc.delete(0, "end")
        self.ent_pform_desc.insert(0, p.get("desc", ""))

        e1 = p.get("branch_a", {}).get("magic", "Amgar")
        e2 = p.get("branch_b", {}).get("magic", "Gale")
        self.cb_pform_elem1.set(e1)
        self.cb_pform_elem2.set(e2)
        self.on_pform_elem_change()

        basic = p.get("basic", "")
        if basic:
            self.cb_pform_basic.set(basic)
        s_a = p.get("branch_a", {}).get("skills", [])
        s_b = p.get("branch_b", {}).get("skills", [])
        if len(s_a) > 0:
            self.cb_pform_s1.set(s_a[0])
        if len(s_a) > 1:
            self.cb_pform_s2.set(s_a[1])
        if len(s_b) > 0:
            self.cb_pform_s3.set(s_b[0])
        if len(s_b) > 1:
            self.cb_pform_s4.set(s_b[1])
        if len(s_b) > 2:
            self.cb_pform_s5.set(s_b[2])
        else:
            self.cb_pform_s5.set("(Không dùng)")
        self.refresh_pform_loadout_dropdowns()

        self.preset_form_relics = set(p.get("relics", []))
        self.render_pform_relic_chips()

        st = p.get("stats", {})
        for k, info in self.preset_form_vars.items():
            val = st.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

        # Cập nhật thẻ tóm tắt
        sks = [basic] + s_a + s_b
        sks_str = ", ".join(s for s in sks if s and s != "(Không dùng)")
        relics_str = ", ".join(self.preset_form_relics) if self.preset_form_relics else "(Không)"
        card_text = f"• Mã: {pid}\n• Tên: {p.get('name', pid)}\n• Nhánh: {e1} + {e2}\n• Kỹ năng: {sks_str}\n• Relics ({len(self.preset_form_relics)}): {relics_str}\n• Chỉ số: {st.get('hp', 2000):.0f}HP | {st.get('atk', 200):.0f}ATK | {st.get('defense', 300):.0f}DEF | MC {st.get('mc', 0)*100:.0f}%"
        self.lbl_preset_card.config(text=card_text)
        self.lbl_pform_msg.config(text=f"Đang xem [{pid}]", fg="#cccccc")

    def new_preset_form(self):
        self.editing_preset_key = None
        idx = 1
        while f"preset_{idx}" in self.build_presets:
            idx += 1
        new_id = f"preset_{idx}"
        new_name = f"Build Preset {idx}"

        self.ent_pform_key.delete(0, "end")
        self.ent_pform_key.insert(0, new_id)

        self.ent_pform_name.delete(0, "end")
        self.ent_pform_name.insert(0, new_name)

        self.ent_pform_desc.delete(0, "end")

        self.cb_pform_elem1.set("Amgar")
        self.cb_pform_elem2.set("Gale")
        self.on_pform_elem_change()

        self.preset_form_relics = set()
        self.render_pform_relic_chips()

        self.apply_pform_stat_preset("base")
        self.lbl_preset_card.config(text=f"Đang soạn thảo Preset mới [{new_id}]. Nhấn 'LƯU PRESET' khi hoàn tất.")
        self.lbl_pform_msg.config(text="Đang soạn Preset mới", fg="#cccccc")

    def clone_preset_action(self):
        sel = self.tree_presets.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 Preset để nhân bản!")
            return
        pid = sel[0]
        orig = self.build_presets.get(pid)
        if not orig:
            return

        new_pid = f"{pid}_copy"
        idx = 2
        while new_pid in self.build_presets:
            new_pid = f"{pid}_copy_{idx}"
            idx += 1

        cloned = copy.deepcopy(orig)
        cloned["name"] = f"{orig.get('name', pid)} (Bản sao)"
        self.build_presets[new_pid] = cloned
        self.save_build_presets_to_disk()
        self.refresh_presets_tree()
        self.tree_presets.selection_set(new_pid)
        self.on_preset_tree_select()
        self.lbl_pform_msg.config(text=f"✓ Đã nhân bản thành [{new_pid}]!", fg="#00e676")

    def delete_preset_action(self):
        sel = self.tree_presets.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 Preset để xóa!")
            return
        pid = sel[0]
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa Preset '{pid}' không?"):
            return
        if pid in self.build_presets:
            del self.build_presets[pid]
            self.save_build_presets_to_disk()
            self.refresh_presets_tree()
            self.new_preset_form()
            self.lbl_pform_msg.config(text=f"✓ Đã xóa preset [{pid}].", fg="#ff6666")

    def save_preset_action(self):
        pid = self.ent_pform_key.get().strip()
        if not pid:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập Mã Preset (Key ID)!")
            return
        pname = self.ent_pform_name.get().strip() or pid
        pdesc = self.ent_pform_desc.get().strip()

        e1 = self.cb_pform_elem1.get()
        e2 = self.cb_pform_elem2.get()
        basic = self.cb_pform_basic.get()

        s_a = [self.cb_pform_s1.get(), self.cb_pform_s2.get()]
        s_b = [self.cb_pform_s3.get(), self.cb_pform_s4.get()]
        extra_s = self.cb_pform_s5.get()
        if extra_s and extra_s not in ("(Không dùng)", "(Hết skill)"):
            s_b.append(extra_s)

        stats_dict = {k: v["var"].get() for k, v in self.preset_form_vars.items()}

        preset_obj = {
            "name": pname,
            "desc": pdesc,
            "branch_a": {"magic": e1, "skills": s_a},
            "branch_b": {"magic": e2, "skills": s_b},
            "basic": basic,
            "stats": stats_dict,
            "relics": sorted(list(self.preset_form_relics))
        }

        if self.editing_preset_key and self.editing_preset_key != pid:
            if pid in self.build_presets:
                if not messagebox.askyesno("Ghi đè?", f"Preset '{pid}' đã tồn tại! Bạn có muốn ghi đè?"):
                    return
            if self.editing_preset_key in self.build_presets:
                del self.build_presets[self.editing_preset_key]

        self.build_presets[pid] = preset_obj
        self.editing_preset_key = pid
        self.save_build_presets_to_disk()
        self.refresh_presets_tree()
        self.tree_presets.selection_set(pid)
        self.on_preset_tree_select()

        self.lbl_pform_msg.config(text=f"✓ Đã lưu preset [{pid}] vào config/build_presets.json!", fg="#00e676")
        return preset_obj

    def save_and_apply_to_team_a(self):
        p_obj = self.save_preset_action()
        if p_obj:
            self.apply_preset_to_team("a", p_obj)
            self.notebook.select(0)

    def apply_pform_and_switch_a(self):
        pid = self.ent_pform_key.get().strip()
        p = self.build_presets.get(pid)
        if not p:
            self.save_preset_action()
            p = self.build_presets.get(pid)
        if p:
            self.apply_preset_to_team("a", p)
            self.notebook.select(0)

    def apply_pform_and_switch_b(self):
        pid = self.ent_pform_key.get().strip()
        p = self.build_presets.get(pid)
        if not p:
            self.save_preset_action()
            p = self.build_presets.get(pid)
        if p:
            self.apply_preset_to_team("b", p)
            self.mode_var.set("fight")
            self.on_mode_change()
            self.notebook.select(0)

    def apply_pform_and_switch_dps(self):
        pid = self.ent_pform_key.get().strip()
        p = self.build_presets.get(pid)
        if not p:
            self.save_preset_action()
            p = self.build_presets.get(pid)
        if p and "stats" in p:
            st = p["stats"]
            cur_dummy = self.dps_dummies[self.current_dps_idx]
            for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr", "guard_q", "res"]:
                if k in st:
                    cur_dummy["stats"][k] = float(st[k])
            self.load_dps_dummy_to_sliders(self.current_dps_idx)
            self.render_dps_dummy_tabs()
            self.mode_var.set("dps")
            self.on_mode_change()
            self.notebook.select(0)

    def on_pform_elem_change(self):
        e1 = self.cb_pform_elem1.get()
        e2 = self.cb_pform_elem2.get()
        if e1 == e2:
            self.lbl_pform_elem_status.config(text=f"★ PURETYPE: Thuần {e1}", bg="#ffffff", fg="#000000")
        else:
            self.lbl_pform_elem_status.config(text=f"⚡ TỔ HỢP: {e1} + {e2}", bg="#242424", fg="#ffffff")
        if hasattr(self, "lbl_pform_l1"):
            self.lbl_pform_l1.config(text=f"Nhánh 1 ({e1}):")
            self.lbl_pform_l2.config(text=f"Nhánh 2 ({e2}):")
            self.reset_pform_loadout()

    def swap_pform_elements(self):
        e1 = self.cb_pform_elem1.get()
        e2 = self.cb_pform_elem2.get()
        self.cb_pform_elem1.set(e2)
        self.cb_pform_elem2.set(e1)
        self.on_pform_elem_change()

    def make_pform_pure(self):
        e1 = self.cb_pform_elem1.get()
        self.cb_pform_elem2.set(e1)
        self.on_pform_elem_change()

    def reset_pform_loadout(self):
        e1 = self.cb_pform_elem1.get()
        e2 = self.cb_pform_elem2.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_pform_basic["values"] = b1
        self.cb_pform_basic.set(b1[0] if b1 else "")

        if e1 == e2:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a1[2] if len(a1) > 2 else s1
            s4 = a1[3] if len(a1) > 3 else s1
        else:
            s1 = a1[0] if len(a1) > 0 else ""
            s2 = a1[1] if len(a1) > 1 else s1
            s3 = a2[2] if len(a2) > 2 else (a2[0] if a2 else "")
            s4 = a2[3] if len(a2) > 3 else (a2[1] if len(a2) > 1 else s3)

        self.cb_pform_s1.set(s1)
        self.cb_pform_s2.set(s2)
        self.cb_pform_s3.set(s3)
        self.cb_pform_s4.set(s4)
        self.cb_pform_s5.set("(Không dùng)")
        self.refresh_pform_loadout_dropdowns()

    def refresh_pform_loadout_dropdowns(self):
        e1 = self.cb_pform_elem1.get()
        e2 = self.cb_pform_elem2.get()
        b1, a1 = self.get_magic_skills(e1)
        b2, a2 = self.get_magic_skills(e2)

        self.cb_pform_basic["values"] = b1
        s1 = self.cb_pform_s1.get()
        s2 = self.cb_pform_s2.get()
        s3 = self.cb_pform_s3.get()
        s4 = self.cb_pform_s4.get()

        self.cb_pform_s1["values"] = a1

        opt_s2 = [s for s in a1 if s != s1]
        self.cb_pform_s2["values"] = opt_s2 if opt_s2 else a1
        if self.cb_pform_s2.get() not in self.cb_pform_s2["values"] and opt_s2:
            self.cb_pform_s2.set(opt_s2[0])

        if e1 == e2:
            used_branch1 = {s1, self.cb_pform_s2.get()}
            opt_s3 = [s for s in a1 if s not in used_branch1]
            self.cb_pform_s3["values"] = opt_s3 if opt_s3 else a1
            if self.cb_pform_s3.get() not in self.cb_pform_s3["values"] and opt_s3:
                self.cb_pform_s3.set(opt_s3[0])

            used_so_far = used_branch1 | {self.cb_pform_s3.get()}
            opt_s4 = [s for s in a1 if s not in used_so_far]
            self.cb_pform_s4["values"] = opt_s4 if opt_s4 else a1
            if self.cb_pform_s4.get() not in self.cb_pform_s4["values"] and opt_s4:
                self.cb_pform_s4.set(opt_s4[0])

            used_all = used_so_far | {self.cb_pform_s4.get()}
            rem_s5 = [s for s in a1 if s not in used_all]
            self.cb_pform_s5["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_pform_s5.get() not in self.cb_pform_s5["values"]:
                self.cb_pform_s5.set("(Không dùng)")
        else:
            self.cb_pform_s3["values"] = a2
            opt_s4 = [s for s in a2 if s != s3]
            self.cb_pform_s4["values"] = opt_s4 if opt_s4 else a2
            if self.cb_pform_s4.get() not in self.cb_pform_s4["values"] and opt_s4:
                self.cb_pform_s4.set(opt_s4[0])

            used_b = {self.cb_pform_s3.get(), self.cb_pform_s4.get()}
            rem_s5 = [s for s in a2 if s not in used_b]
            self.cb_pform_s5["values"] = ["(Không dùng)"] + rem_s5
            if self.cb_pform_s5.get() not in self.cb_pform_s5["values"]:
                self.cb_pform_s5.set("(Không dùng)")

    def on_pform_skill_change(self):
        self.refresh_pform_loadout_dropdowns()

    def open_pform_relic_selector(self):
        def cb(chosen):
            self.preset_form_relics = set(chosen)
            self.render_pform_relic_chips()
        self.open_relic_selector(list(self.preset_form_relics), cb, title="CHỌN RELICS CHO PRESET BUILD")

    def render_pform_relic_chips(self):
        if not hasattr(self, "frame_pform_chips"):
            return
        for w in self.frame_pform_chips.winfo_children():
            w.destroy()

        cnt = len(self.preset_form_relics)
        if hasattr(self, "btn_pform_pick_relics"):
            self.btn_pform_pick_relics.config(text=f"🛡 Chọn Relics ({cnt} đã chọn)...")

        if not self.preset_form_relics:
            tk.Label(self.frame_pform_chips, text="(Chưa chọn relic nào. Nhấn nút phía trên để chọn)",
                     font=("Segoe UI", 8, "italic"), fg="#777777", bg=self.c_surface).pack(anchor="w", padx=2, pady=2)
            return

        flow = tk.Frame(self.frame_pform_chips, bg=self.c_surface)
        flow.pack(fill="x", pady=2)

        for rid in sorted(self.preset_form_relics):
            r_info = self.cfg.get("relics", {}).get(rid, {})
            name = r_info.get("name", rid)
            chip = tk.Frame(flow, bg="#262626", relief="solid", bd=1, padx=4, pady=2)
            chip.pack(side="left", padx=2, pady=2)

            tk.Label(chip, text=name, font=("Segoe UI", 8), fg="#ffffff", bg="#262626").pack(side="left")
            btn_del = tk.Button(chip, text="✕", font=("Segoe UI", 7, "bold"), fg="#ff6666", bg="#262626",
                                relief="flat", padx=2, cursor="hand2", command=lambda r=rid: self.remove_pform_relic(r))
            btn_del.pack(side="left", padx=(2, 0))

    def remove_pform_relic(self, rid):
        if rid in self.preset_form_relics:
            self.preset_form_relics.remove(rid)
            self.render_pform_relic_chips()

    def clear_pform_relics(self):
        self.preset_form_relics.clear()
        self.render_pform_relic_chips()

    def apply_pform_stat_preset(self, preset_key):
        base_defs = {
            "hp": 2000, "atk": 200, "defense": 300, "mc": 0.0,
            "pct_def_ignore": 0.05, "flat_def_ignore": 50, "damage_mult": 1.0,
            "cdr": 0.0, "guard_q": 0.35, "res": 0.0
        }
        if preset_key == "base":
            target = base_defs
        elif preset_key == "dps":
            target = dict(base_defs, hp=1800, atk=450, damage_mult=1.35, pct_def_ignore=0.20)
        elif preset_key == "caster":
            target = dict(base_defs, atk=240, mc=0.35, cdr=0.30)
        elif preset_key == "tank":
            target = dict(base_defs, hp=8000, defense=1200, guard_q=0.60, res=0.15)
        else:
            target = base_defs

        for k, info in self.preset_form_vars.items():
            val = target.get(k, info["meta"]["min"])
            info["var"].set(val)
            info["entry"].delete(0, "end")
            info["entry"].insert(0, str(val))

    # =========================================================================
    # TAB 7: CUSTOM RELICS & NỘI TẠI (QUẢN LÝ, TẠO MỚI & SỬA RELICS THEO TRIGGER)
    # =========================================================================
    def save_relics_to_disk(self):
        try:
            p = os.path.join(HERE, "config", "relics.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.cfg["relics"], f, ensure_ascii=False, indent=2)
            if hasattr(self, "refresh_relics_tree"):
                self.refresh_relics_tree()
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", f"Không thể ghi config/relics.json:\n{e}")

    def build_relics_tab(self, parent):
        main_box = tk.Frame(parent, bg=self.c_bg)
        main_box.pack(fill="both", expand=True, padx=8, pady=8)

        # CỘT TRÁI: DANH SÁCH RELICS (330px)
        left_frame = tk.Frame(main_box, bg=self.c_surface, width=330, bd=1, relief="solid")
        left_frame.pack(side="left", fill="both", padx=(0, 6), pady=0)
        left_frame.pack_propagate(False)

        top_l = tk.Frame(left_frame, bg=self.c_sub, padx=10, pady=8)
        top_l.pack(fill="x")
        tk.Label(top_l, text="DANH SÁCH RELICS & NỘI TẠI", font=("Segoe UI", 10, "bold"),
                 fg=self.c_fg, bg=self.c_sub).pack(anchor="w")

        # Tìm kiếm & Phân loại
        search_box = tk.Frame(left_frame, bg=self.c_surface, padx=8, pady=4)
        search_box.pack(fill="x")
        tk.Label(search_box, text="🔍 Tìm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.ent_search_relic = tk.Entry(search_box, bg="#111111", fg="#ffffff", insertbackground="#ffffff",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_search_relic.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.ent_search_relic.bind("<KeyRelease>", lambda e: self.refresh_relics_tree())

        cat_box = tk.Frame(left_frame, bg=self.c_surface, padx=8, pady=2)
        cat_box.pack(fill="x")
        self.cb_relic_cat = ttk.Combobox(cat_box, values=["Tất cả", "Nội tại kích hoạt (Triggers)", "Chỉ số tĩnh (Mods)", "Nội tại nguyên tố"], state="readonly", font=("Segoe UI", 8))
        self.cb_relic_cat.set("Tất cả")
        self.cb_relic_cat.pack(fill="x", pady=2)
        self.cb_relic_cat.bind("<<ComboboxSelected>>", lambda e: self.refresh_relics_tree())

        # Treeview danh sách Relic
        tree_frame = tk.Frame(left_frame, bg=self.c_bg)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=4)

        tree_cols = ("name", "kind")
        self.tree_relics = ttk.Treeview(tree_frame, columns=tree_cols, show="headings", selectmode="browse")
        self.tree_relics.heading("name", text="Tên Relic / Nội Tại")
        self.tree_relics.heading("kind", text="Loại")
        self.tree_relics.column("name", width=190, anchor="w")
        self.tree_relics.column("kind", width=100, anchor="center")

        tree_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_relics.yview)
        self.tree_relics.configure(yscrollcommand=tree_sb.set)

        self.tree_relics.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")
        self.tree_relics.bind("<<TreeviewSelect>>", self.on_relic_tree_select)

        # Card tóm tắt Relic đang chọn
        card_box = tk.Frame(left_frame, bg="#181818", padx=8, pady=6, relief="solid", bd=1)
        card_box.pack(fill="x", padx=6, pady=(0, 6))

        tk.Label(card_box, text="TÓM TẮT RELIC:", font=("Segoe UI", 8, "bold"), fg=self.c_muted, bg="#181818").pack(anchor="w")
        self.lbl_relic_card = tk.Label(card_box, text="(Chọn một relic để xem tóm tắt)", font=("Segoe UI", 8),
                                       fg="#cccccc", bg="#181818", wraplength=300, justify="left")
        self.lbl_relic_card.pack(anchor="w", pady=(2, 0))

        # Nút thao tác nhanh
        btn_bar = tk.Frame(left_frame, bg=self.c_sub, padx=6, pady=6)
        btn_bar.pack(fill="x", side="bottom")

        tk.Button(btn_bar, text="+ Tạo Mới", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                  relief="solid", bd=1, padx=8, pady=4, cursor="hand2", command=self.new_relic_form).pack(side="left", padx=2)
        tk.Button(btn_bar, text="📋 Nhân Bản", bg="#2a2a2a", fg="#ffffff", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=8, pady=4, cursor="hand2", command=self.clone_relic_action).pack(side="left", padx=2)
        tk.Button(btn_bar, text="🗑 Xóa", bg="#2a2a2a", fg="#ff6666", font=("Segoe UI", 8),
                  relief="solid", bd=1, padx=8, pady=4, cursor="hand2", command=self.delete_relic_action).pack(side="left", padx=2)

        # CỘT PHẢI: FORM THIẾT LẬP RELIC (SCROLLABLE CANVAS)
        right_frame = tk.Frame(main_box, bg=self.c_surface, bd=1, relief="solid")
        right_frame.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=0)

        r_top = tk.Frame(right_frame, bg=self.c_sub, padx=12, pady=8)
        r_top.pack(fill="x")
        self.lbl_relic_editor_title = tk.Label(r_top, text="[ THIẾT LẬP RELIC & NỘI TẠI TỰ DO ]",
                                               font=("Segoe UI", 10, "bold"), fg=self.c_fg, bg=self.c_sub)
        self.lbl_relic_editor_title.pack(side="left")

        r_canvas = tk.Canvas(right_frame, bg=self.c_surface, highlightthickness=0)
        r_sb = ttk.Scrollbar(right_frame, orient="vertical", command=r_canvas.yview)
        r_form = tk.Frame(r_canvas, bg=self.c_surface, padx=12, pady=8)

        r_form.bind("<Configure>", lambda e: r_canvas.configure(scrollregion=r_canvas.bbox("all")))
        r_win = r_canvas.create_window((0, 0), window=r_form, anchor="nw")
        r_canvas.configure(yscrollcommand=r_sb.set)

        def _on_r_canvas_configure(e):
            r_canvas.itemconfig(r_win, width=e.width)
        r_canvas.bind("<Configure>", _on_r_canvas_configure)

        def _on_r_mousewheel(event):
            r_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        r_canvas.bind("<Enter>", lambda e: r_canvas.bind_all("<MouseWheel>", _on_r_mousewheel))
        r_canvas.bind("<Leave>", lambda e: r_canvas.unbind_all("<MouseWheel>"))

        r_canvas.pack(side="left", fill="both", expand=True)
        r_sb.pack(side="right", fill="y")

        # 1. Thông tin chung Relic
        meta_box = tk.LabelFrame(r_form, text=" 1. THÔNG TIN RELIC / NỘI TẠI ", font=("Segoe UI", 8, "bold"),
                                 fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        meta_box.pack(fill="x", pady=(0, 6))

        m_r1 = tk.Frame(meta_box, bg=self.c_surface)
        m_r1.pack(fill="x", pady=2)

        f_k = tk.Frame(m_r1, bg=self.c_surface)
        f_k.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f_k, text="Mã Relic (Key ID, chữ thường không dấu):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_relic_key = tk.Entry(f_k, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                      relief="solid", bd=1, font=("Consolas", 9))
        self.ent_relic_key.pack(fill="x")

        f_n = tk.Frame(m_r1, bg=self.c_surface)
        f_n.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Label(f_n, text="Tên Relic Hiển Thị:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_relic_name = tk.Entry(f_n, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                       relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_relic_name.pack(fill="x")

        m_r2 = tk.Frame(meta_box, bg=self.c_surface)
        m_r2.pack(fill="x", pady=(4, 2))
        tk.Label(m_r2, text="Mô tả cơ chế / hiệu ứng của Relic:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(anchor="w")
        self.ent_relic_desc = tk.Entry(m_r2, bg="#121212", fg="#ffffff", insertbackground="#ffffff",
                                       relief="solid", bd=1, font=("Segoe UI", 9))
        self.ent_relic_desc.pack(fill="x")

        # 2. Cấu hình Kích Hoạt (Event Trigger)
        trig_box = tk.LabelFrame(r_form, text=" 2. CƠ CHẾ KÍCH HOẠT (EVENT TRIGGER) ", font=("Segoe UI", 8, "bold"),
                                 fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        trig_box.pack(fill="x", pady=(0, 6))

        self.var_r_has_trigger = tk.BooleanVar(value=True)
        cb_has_trig = tk.Checkbutton(trig_box, text="Kích hoạt theo hành động chiến đấu (Event Trigger)",
                                     variable=self.var_r_has_trigger, font=("Segoe UI", 8, "bold"),
                                     fg="#ffffff", bg=self.c_surface, selectcolor="#000000",
                                     activebackground=self.c_surface, activeforeground="#ffffff",
                                     command=self.toggle_r_trigger_view)
        cb_has_trig.pack(anchor="w")

        self.frame_trig_settings = tk.Frame(trig_box, bg=self.c_surface)
        self.frame_trig_settings.pack(fill="x", pady=4)

        t_r1 = tk.Frame(self.frame_trig_settings, bg=self.c_surface)
        t_r1.pack(fill="x", pady=2)

        tk.Label(t_r1, text="Hành Động Kích Hoạt (Event):", font=("Segoe UI", 8, "bold"),
                 fg=self.c_fg, bg=self.c_surface).pack(side="left", padx=(0, 6))

        self.TRIGGER_EVENT_MAP = {
            # 1. Cơ Động & Phòng Ngự Thể Lực
            "on_dodge": "on_dodge (Lướt né đòn thành công)",
            "on_perfect_dodge": "on_perfect_dodge (Lướt né hoàn hảo)",
            "on_parry": "on_parry (Đỡ gạt Parry thành công)",
            "on_block": "on_block (Chặn Block đòn thành công)",
            "on_guard_break": "on_guard_break (Thế thủ bị đánh vỡ)",
            "on_exhausted": "on_exhausted (Kiệt sức - Thể lực về 0)",
            "on_stamina_full": "on_stamina_full (Thể lực hồi đầy 100%)",
            "on_stamina_low": "on_stamina_low (Thể lực xuống dưới 25%)",
            "on_heavy_stamina_spent": "on_heavy_stamina_spent (Tiêu hao nhiều thể lực)",

            # 2. Tấn Công & Tung Chiêu
            "on_hit": "on_hit (Đòn đánh / kỹ năng trúng đích)",
            "on_cast_any": "on_cast_any (Tung bất kỳ kỹ năng nào)",
            "on_cast_basic": "on_cast_basic (Tung chiêu Basic)",
            "on_cast_magic_1": "on_cast_magic_1 (Tung chiêu Nhánh 1)",
            "on_cast_magic_2": "on_cast_magic_2 (Tung chiêu Nhánh 2)",
            "on_cast_cd_skill": "on_cast_cd_skill (Tung chiêu có hồi chiêu)",
            "on_deal_true_dmg": "on_deal_true_dmg (Gây sát thương chuẩn)",
            "on_combo_hits": "on_combo_hits (Đánh trúng chuỗi liên hoàn)",
            "on_finisher_hit": "on_finisher_hit (Đòn kết liễu chuỗi combo)",
            "on_counter_attack": "on_counter_attack (Phản đòn sau khi bị đánh)",
            "on_skill_depleted": "on_skill_depleted (Kỹ năng cạn kiệt lần dùng)",

            # 3. Nhận Sát Thương & Máu
            "on_take_hit": "on_take_hit (Bị kẻ địch đánh trúng)",
            "on_take_heavy_hit": "on_take_heavy_hit (Nhận đòn đánh nặng >=15% HP)",
            "on_take_dot_tick": "on_take_dot_tick (Nhận sát thương DoT)",
            "on_shield_broken": "on_shield_broken (Lớp khiên bị đánh vỡ)",
            "on_shield_expired": "on_shield_expired (Khiên hết thời gian tồn tại)",
            "on_hp_below": "on_hp_below (Máu tụt dưới ngưỡng % HP)",
            "on_hp_above": "on_hp_above (Máu duy trì trên ngưỡng % HP)",
            "on_fatal_damage": "on_fatal_damage (Nhận đòn chí tử)",
            "on_healed": "on_healed (Khi được hồi máu)",
            "on_overheal": "on_overheal (Hồi máu vượt trần Max HP)",

            # 4. Trạng Thái Mục Tiêu
            "on_target_hp_below": "on_target_hp_below (Đánh địch dưới % HP)",
            "on_target_hp_full": "on_target_hp_full (Đánh địch còn 100% HP)",
            "on_target_underdog": "on_target_underdog (Đánh địch có HP cao hơn ta)",
            "on_target_exhausted": "on_target_exhausted (Đánh địch kiệt sức)",
            "on_target_shielded": "on_target_shielded (Đánh địch đang có khiên)",
            "on_target_shieldless": "on_target_shieldless (Đánh địch không có khiên)",
            "on_target_multi_debuff": "on_target_multi_debuff (Đánh địch dính >=2 debuff)",

            # 5. Hiệu Ứng Trạng Thái & Nguyên Tố
            "on_apply_cc": "on_apply_cc (Gây khống chế thành công)",
            "on_hit_frozen": "on_hit_frozen (Đánh trúng mục tiêu Băng)",
            "on_hit_wet": "on_hit_wet (Đánh trúng mục tiêu Wet)",
            "on_trigger_reaction": "on_trigger_reaction (Kích hoạt phản ứng)",
            "on_cleanse": "on_cleanse (Tự giải trừ debuff)",
            "on_receive_debuff": "on_receive_debuff (Bị trúng hiệu ứng xấu)",

            # 6. Thời Gian & Nhịp Độ Trận Đấu
            "periodic": "periodic (Định kỳ mỗi X giây)",
            "on_combat_start": "on_combat_start (Mở màn trận đấu)",
            "on_combat_time_elapsed": "on_combat_time_elapsed (Trận đấu kéo dài qua X giây)"
        }
        self.TRIGGER_EVENT_REVERSE = {v: k for k, v in self.TRIGGER_EVENT_MAP.items()}

        self.cb_r_event = ttk.Combobox(t_r1, values=list(self.TRIGGER_EVENT_MAP.values()), width=42, state="readonly")
        self.cb_r_event.set(self.TRIGGER_EVENT_MAP["on_dodge"])
        self.cb_r_event.pack(side="left", padx=2)

        t_r2 = tk.Frame(self.frame_trig_settings, bg=self.c_surface)
        t_r2.pack(fill="x", pady=4)

        tk.Label(t_r2, text="Hồi chiêu nội tại (ICD):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_icd = ttk.Spinbox(t_r2, from_=0.0, to=60.0, increment=0.5, width=5)
        self.sp_r_icd.set("1.5")
        self.sp_r_icd.pack(side="left", padx=3)
        tk.Label(t_r2, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left", padx=(0, 8))

        tk.Label(t_r2, text="Tỉ lệ kích hoạt:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_chance = ttk.Spinbox(t_r2, from_=5, to=100, increment=5, width=4)
        self.sp_r_chance.set("100")
        self.sp_r_chance.pack(side="left", padx=3)
        tk.Label(t_r2, text="%", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left", padx=(0, 8))

        tk.Label(t_r2, text="Ngưỡng HP:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_hp_thresh = ttk.Spinbox(t_r2, from_=5, to=95, increment=5, width=4)
        self.sp_r_hp_thresh.set("50")
        self.sp_r_hp_thresh.pack(side="left", padx=3)
        tk.Label(t_r2, text="%", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left", padx=(0, 8))

        tk.Label(t_r2, text="Đòn nặng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_heavy_thresh = ttk.Spinbox(t_r2, from_=5, to=50, increment=5, width=4)
        self.sp_r_heavy_thresh.set("15")
        self.sp_r_heavy_thresh.pack(side="left", padx=3)
        tk.Label(t_r2, text="%", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left", padx=(0, 8))

        tk.Label(t_r2, text="Combo:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_combo_req = ttk.Spinbox(t_r2, from_=2, to=20, increment=1, width=3)
        self.sp_r_combo_req.set("3")
        self.sp_r_combo_req.pack(side="left", padx=3)
        tk.Label(t_r2, text="hit", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left", padx=(0, 8))

        tk.Label(t_r2, text="Thời gian:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_combat_t = ttk.Spinbox(t_r2, from_=1.0, to=120.0, increment=1.0, width=5)
        self.sp_r_combat_t.set("10.0")
        self.sp_r_combat_t.pack(side="left", padx=3)
        tk.Label(t_r2, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 3. Cấu hình Phần Thưởng (Reward Action)
        rew_box = tk.LabelFrame(r_form, text=" 3. PHẦN THƯỞNG / HIỆU ỨNG SAU KÍCH HOẠT (REWARD ACTION) ",
                                font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        rew_box.pack(fill="x", pady=(0, 6))

        self.REWARD_ACTION_MAP = {
            # Hồi Chiêu & Tài Nguyên Kỹ Năng
            "reduce_cd": "Giảm % Hồi chiêu Kỹ năng (reduce_cd)",
            "reset_cd": "Làm mới Hồi chiêu Lập tức (reset_cd)",
            "gain_charge": "Tăng thêm Charge tích trữ (gain_charge)",
            "free_cast": "Tung chiêu miễn phí (free_cast)",
            "echo_strike": "Vọng kích phụ gây thêm dmg (echo_strike)",

            # Sát Thương & Chỉ Số Tấn Công
            "buff_stat": "Tăng Chỉ Số tạm thời (buff_stat)",
            "stacking_atk": "Tích tầng tăng ATK cộng dồn (stacking_atk)",
            "true_damage": "Gây thêm Sát thương Chuẩn (true_damage)",
            "execute_damage": "Sát thương kết liễu theo % máu mất (execute_damage)",
            "lifesteal": "Hút máu Lifesteal trong T giây (lifesteal)",
            "stamina_leech": "Hút Thể lực đối thủ (stamina_leech)",
            "dot_detonation": "Kích nổ toàn bộ DoT còn lại (dot_detonation)",
            "aoe_shockwave": "Sóng xung kích nổ diện rộng (aoe_shockwave)",
            "def_to_atk": "Chuyển Giáp DEF thành Sức mạnh ATK (def_to_atk)",
            "berserk_scaling": "Cuồng nộ tăng dmg khi mất máu (berserk_scaling)",

            # Sinh Tồn & Phòng Ngự
            "heal": "Hồi phục Máu tức thì (heal)",
            "hot": "Hồi máu theo thời gian (hot)",
            "shield": "Nhận Khiên chống đòn (shield)",
            "reflective_shield": "Khiên phản kích sát thương (reflective_shield)",
            "damage_reflection": "Gai phản đòn sát thương nhận vào (damage_reflection)",
            "iframes": "Khung hình Bất tử miễn nhiễm dmg (iframes)",
            "damage_to_heal": "Chuyển sát thương thành Hồi Máu (damage_to_heal)",
            "death_defiance": "Cứu tử khẩn cấp khi nhận đòn chí mạng (death_defiance)",
            "auto_cleanse": "Tự động thanh tẩy mọi Debuff (auto_cleanse)",
            "super_armor": "Trọng giáp bất động kháng khống chế (super_armor)",

            # Thể Lực & Cơ Động
            "restore_stamina": "Hồi phục Thể lực tức thì (+Stamina)",
            "stamina_regen": "Tăng tốc độ hồi Thể lực (stamina_regen)",
            "zero_stamina_cost": "Lướt/Đỡ không tốn Thể lực (zero_stamina_cost)",
            "reset_dodge_cd": "Xóa thời gian chờ Lướt Né (reset_dodge_cd)",
            "extended_evasion": "Tăng thời gian bất tử khi Lướt (extended_evasion)",
            "cast_speed_buff": "Tăng tốc độ tung kỹ năng (cast_speed_buff)",

            # Gây Hại Lên Kẻ Địch (Debuffs)
            "apply_cc": "Gây Choáng (Stun) / Làm chậm (Slow)",
            "stamina_drain": "Tiêu hao Thể lực của kẻ địch (stamina_drain)",
            "stamina_freeze": "Đóng băng Thể lực không thể hồi (stamina_freeze)",
            "evasion_lock": "Khóa Lướt Né của kẻ địch (evasion_lock)",
            "cooldown_silence": "Kéo dài thời gian hồi chiêu của địch (cooldown_silence)",
            "apply_elemental_status": "Gán trạng thái nguyên tố (apply_elemental_status)",
            "anti_heal": "Giảm 50% hồi máu của địch (anti_heal)",
            "shred_def_res": "Bào mòn Giáp hoặc Kháng của địch (shred_def_res)",
            "contagion": "Phát tán lây lan Debuff sang kẻ địch khác (contagion)"
        }
        self.REWARD_ACTION_REVERSE = {v: k for k, v in self.REWARD_ACTION_MAP.items()}

        act_r1 = tk.Frame(rew_box, bg=self.c_surface)
        act_r1.pack(fill="x", pady=2)

        tk.Label(act_r1, text="Loại Phần Thưởng:", font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface).pack(side="left", padx=(0, 6))
        self.cb_r_action = ttk.Combobox(act_r1, values=list(self.REWARD_ACTION_MAP.values()), width=42, state="readonly")
        self.cb_r_action.set(self.REWARD_ACTION_MAP["reduce_cd"])
        self.cb_r_action.pack(side="left", padx=2)
        self.cb_r_action.bind("<<ComboboxSelected>>", self.on_r_action_change)

        # Dynamic sub-frames cho từng action
        self.frame_act_details = tk.Frame(rew_box, bg=self.c_surface, pady=4)
        self.frame_act_details.pack(fill="x")

        # Widget components for action parameters
        self.act_sub_widgets = {}

        # 1. CD
        row_cd = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["cd"] = row_cd
        tk.Label(row_cd, text="Mục tiêu chiêu:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_cd_target = ttk.Combobox(row_cd, values=["Chiêu Basic (basic)", "Nhánh 1 (branch_a)", "Nhánh 2 (branch_b)", "Toàn bộ chiêu (all)"], width=22, state="readonly")
        self.cb_r_cd_target.set("Chiêu Basic (basic)")
        self.cb_r_cd_target.pack(side="left", padx=4)
        tk.Label(row_cd, text="Giảm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_r_cd_pct = ttk.Spinbox(row_cd, from_=5, to=100, increment=5, width=5)
        self.sp_r_cd_pct.set("50")
        self.sp_r_cd_pct.pack(side="left", padx=2)
        tk.Label(row_cd, text="% CD", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 2. Gain Charge
        row_gc = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["gain_charge"] = row_gc
        tk.Label(row_gc, text="Mục tiêu chiêu:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_gc_target = ttk.Combobox(row_gc, values=["Chiêu Basic (basic)", "Nhánh 1 (branch_a)", "Nhánh 2 (branch_b)", "Toàn bộ chiêu (all)"], width=22, state="readonly")
        self.cb_r_gc_target.set("Chiêu Basic (basic)")
        self.cb_r_gc_target.pack(side="left", padx=4)
        tk.Label(row_gc, text="+ Số Charge:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_r_gc_num = ttk.Spinbox(row_gc, from_=1, to=5, increment=1, width=4)
        self.sp_r_gc_num.set("1")
        self.sp_r_gc_num.pack(side="left", padx=2)

        # 3. Echo Strike
        row_echo = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["echo"] = row_echo
        tk.Label(row_echo, text="Tỉ lệ sát thương đòn vọng lại (Echo):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_echo_pct = ttk.Spinbox(row_echo, from_=10, to=150, increment=10, width=5)
        self.sp_r_echo_pct.set("50")
        self.sp_r_echo_pct.pack(side="left", padx=4)
        tk.Label(row_echo, text="% dmg", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 4. Buff Stat
        row_buff = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["buff"] = row_buff
        tk.Label(row_buff, text="Chỉ số buff:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_buff_stat = ttk.Combobox(row_buff, values=["atk", "defense", "damage_mult", "cdr", "mc", "pct_def_ignore"], width=13, state="readonly")
        self.cb_r_buff_stat.set("atk")
        self.cb_r_buff_stat.pack(side="left", padx=4)
        tk.Label(row_buff, text="Giá trị (%):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_buff_val = ttk.Spinbox(row_buff, from_=5, to=200, increment=5, width=5)
        self.sp_r_buff_val.set("20")
        self.sp_r_buff_val.pack(side="left", padx=2)
        tk.Label(row_buff, text="%   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_buff_dur = ttk.Spinbox(row_buff, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_buff_dur.set("4.0")
        self.sp_r_buff_dur.pack(side="left", padx=2)
        tk.Label(row_buff, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 5. Stacking ATK
        row_stk = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["stacking_atk"] = row_stk
        tk.Label(row_stk, text="+ Mỗi tầng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_stk_val = ttk.Spinbox(row_stk, from_=1, to=50, increment=1, width=4)
        self.sp_r_stk_val.set("5")
        self.sp_r_stk_val.pack(side="left", padx=2)
        tk.Label(row_stk, text="% ATK   Tối đa:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(4, 2))
        self.sp_r_stk_max = ttk.Spinbox(row_stk, from_=2, to=30, increment=1, width=4)
        self.sp_r_stk_max.set("5")
        self.sp_r_stk_max.pack(side="left", padx=2)
        tk.Label(row_stk, text="tầng   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(4, 2))
        self.sp_r_stk_dur = ttk.Spinbox(row_stk, from_=1.0, to=30.0, increment=1.0, width=5)
        self.sp_r_stk_dur.set("6.0")
        self.sp_r_stk_dur.pack(side="left", padx=2)
        tk.Label(row_stk, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 6. True Damage
        row_td = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["true_dmg"] = row_td
        tk.Label(row_td, text="Sát thương chuẩn phẳng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_td_flat = ttk.Spinbox(row_td, from_=0, to=5000, increment=50, width=6)
        self.sp_r_td_flat.set("150")
        self.sp_r_td_flat.pack(side="left", padx=4)
        tk.Label(row_td, text="+ % Max HP địch:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_td_pct = ttk.Spinbox(row_td, from_=0, to=50, increment=1, width=5)
        self.sp_r_td_pct.set("0")
        self.sp_r_td_pct.pack(side="left", padx=2)
        tk.Label(row_td, text="%", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 7. Execute Damage
        row_exec = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["execute"] = row_exec
        tk.Label(row_exec, text="Sát thương cơ bản:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_exec_base = ttk.Spinbox(row_exec, from_=50, to=5000, increment=50, width=6)
        self.sp_r_exec_base.set("200")
        self.sp_r_exec_base.pack(side="left", padx=2)
        tk.Label(row_exec, text="+ Hệ số nhân theo % máu mất:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_exec_mult = ttk.Spinbox(row_exec, from_=0.5, to=5.0, increment=0.25, width=5)
        self.sp_r_exec_mult.set("1.5")
        self.sp_r_exec_mult.pack(side="left", padx=2)
        tk.Label(row_exec, text="x", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 8. Lifesteal
        row_ls = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["lifesteal"] = row_ls
        tk.Label(row_ls, text="Tỉ lệ Hút Máu (Lifesteal):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_ls_pct = ttk.Spinbox(row_ls, from_=5, to=100, increment=5, width=5)
        self.sp_r_ls_pct.set("30")
        self.sp_r_ls_pct.pack(side="left", padx=2)
        tk.Label(row_ls, text="%   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_ls_dur = ttk.Spinbox(row_ls, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_ls_dur.set("5.0")
        self.sp_r_ls_dur.pack(side="left", padx=2)
        tk.Label(row_ls, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 9. Stamina Leech
        row_sleech = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["stamina_leech"] = row_sleech
        tk.Label(row_sleech, text="Số Thể Lực cướp từ kẻ địch:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_sleech_amt = ttk.Spinbox(row_sleech, from_=10, to=150, increment=5, width=6)
        self.sp_r_sleech_amt.set("30")
        self.sp_r_sleech_amt.pack(side="left", padx=4)
        tk.Label(row_sleech, text="điểm stamina", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 10. AoE Shockwave
        row_wave = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["aoe_wave"] = row_wave
        tk.Label(row_wave, text="Sát thương cơ bản:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_wave_base = ttk.Spinbox(row_wave, from_=50, to=5000, increment=50, width=6)
        self.sp_r_wave_base.set("250")
        self.sp_r_wave_base.pack(side="left", padx=2)
        tk.Label(row_wave, text="+ Tỉ lệ theo ATK:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_wave_scale = ttk.Spinbox(row_wave, from_=10, to=200, increment=10, width=5)
        self.sp_r_wave_scale.set("50")
        self.sp_r_wave_scale.pack(side="left", padx=2)
        tk.Label(row_wave, text="% ATK", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 11. Def to ATK
        row_d2a = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["def_to_atk"] = row_d2a
        tk.Label(row_d2a, text="Chuyển đổi Giáp thành ATK:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_d2a_pct = ttk.Spinbox(row_d2a, from_=10, to=100, increment=5, width=5)
        self.sp_r_d2a_pct.set("25")
        self.sp_r_d2a_pct.pack(side="left", padx=2)
        tk.Label(row_d2a, text="% DEF   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_d2a_dur = ttk.Spinbox(row_d2a, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_d2a_dur.set("5.0")
        self.sp_r_d2a_dur.pack(side="left", padx=2)
        tk.Label(row_d2a, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 12. Berserk Scaling
        row_ber = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["berserk"] = row_ber
        tk.Label(row_ber, text="+ Sát thương mỗi 10% máu mất:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_berserk_mult = ttk.Spinbox(row_ber, from_=1, to=20, increment=1, width=4)
        self.sp_r_berserk_mult.set("5")
        self.sp_r_berserk_mult.pack(side="left", padx=2)
        tk.Label(row_ber, text="% Mult   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_berserk_dur = ttk.Spinbox(row_ber, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_berserk_dur.set("5.0")
        self.sp_r_berserk_dur.pack(side="left", padx=2)
        tk.Label(row_ber, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 13. Heal / Shield
        row_heal_sh = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["heal_sh"] = row_heal_sh
        tk.Label(row_heal_sh, text="% Max HP:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_heal_pct = ttk.Spinbox(row_heal_sh, from_=0, to=100, increment=5, width=5)
        self.sp_r_heal_pct.set("10")
        self.sp_r_heal_pct.pack(side="left", padx=2)
        tk.Label(row_heal_sh, text="%   + Điểm phẳng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_heal_flat = ttk.Spinbox(row_heal_sh, from_=0, to=5000, increment=100, width=6)
        self.sp_r_heal_flat.set("0")
        self.sp_r_heal_flat.pack(side="left", padx=2)
        tk.Label(row_heal_sh, text="Thời gian (khiên):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 2))
        self.sp_r_sh_dur = ttk.Spinbox(row_heal_sh, from_=1.0, to=30.0, increment=1.0, width=5)
        self.sp_r_sh_dur.set("5.0")
        self.sp_r_sh_dur.pack(side="left", padx=2)
        tk.Label(row_heal_sh, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 14. HoT
        row_hot = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["hot"] = row_hot
        tk.Label(row_hot, text="Tổng hồi % Max HP:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_hot_pct = ttk.Spinbox(row_hot, from_=5, to=100, increment=5, width=5)
        self.sp_r_hot_pct.set("15")
        self.sp_r_hot_pct.pack(side="left", padx=2)
        tk.Label(row_hot, text="%   + Điểm phẳng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_hot_flat = ttk.Spinbox(row_hot, from_=0, to=5000, increment=100, width=6)
        self.sp_r_hot_flat.set("0")
        self.sp_r_hot_flat.pack(side="left", padx=2)
        tk.Label(row_hot, text="Thời gian:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_hot_dur = ttk.Spinbox(row_hot, from_=1.0, to=30.0, increment=1.0, width=5)
        self.sp_r_hot_dur.set("5.0")
        self.sp_r_hot_dur.pack(side="left", padx=2)
        tk.Label(row_hot, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 15. Reflect
        row_ref = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["reflect"] = row_ref
        tk.Label(row_ref, text="Tỉ lệ Phản Sát Thương:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_ref_pct = ttk.Spinbox(row_ref, from_=10, to=100, increment=5, width=5)
        self.sp_r_ref_pct.set("35")
        self.sp_r_ref_pct.pack(side="left", padx=2)
        tk.Label(row_ref, text="%   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_ref_dur = ttk.Spinbox(row_ref, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_ref_dur.set("5.0")
        self.sp_r_ref_dur.pack(side="left", padx=2)
        tk.Label(row_ref, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 16. Duration Only (iframes, damage_to_heal, super_armor, zero_stam, cast_speed, stamina_freeze, evasion_lock, anti_heal...)
        row_dur = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["duration_only"] = row_dur
        tk.Label(row_dur, text="Thời gian hiệu lực:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_dur_val = ttk.Spinbox(row_dur, from_=0.5, to=30.0, increment=0.5, width=5)
        self.sp_r_dur_val.set("3.0")
        self.sp_r_dur_val.pack(side="left", padx=4)
        tk.Label(row_dur, text="giây", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 17. Death Defiance
        row_dd = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["death_defiance"] = row_dd
        tk.Label(row_dd, text="Máu giữ lại:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_dd_hp = ttk.Spinbox(row_dd, from_=5, to=50, increment=5, width=4)
        self.sp_r_dd_hp.set("20")
        self.sp_r_dd_hp.pack(side="left", padx=2)
        tk.Label(row_dd, text="% HP   Bất tử:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(4, 2))
        self.sp_r_dd_iframe = ttk.Spinbox(row_dd, from_=0.5, to=5.0, increment=0.5, width=4)
        self.sp_r_dd_iframe.set("1.5")
        self.sp_r_dd_iframe.pack(side="left", padx=2)
        tk.Label(row_dd, text="s   Cấp khiên:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(4, 2))
        self.sp_r_dd_shield = ttk.Spinbox(row_dd, from_=10, to=80, increment=5, width=4)
        self.sp_r_dd_shield.set("35")
        self.sp_r_dd_shield.pack(side="left", padx=2)
        tk.Label(row_dd, text="% Max HP", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 18. Restore Stamina
        row_stam = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["stam"] = row_stam
        tk.Label(row_stam, text="Hồi Thể Lực:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_stam_amt = ttk.Spinbox(row_stam, from_=5, to=150, increment=5, width=6)
        self.sp_r_stam_amt.set("30")
        self.sp_r_stam_amt.pack(side="left", padx=4)
        tk.Label(row_stam, text="điểm stamina", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 19. Stamina Regen
        row_sreg = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["stam_regen"] = row_sreg
        tk.Label(row_sreg, text="Tốc độ hồi Thể Lực:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_sreg_mult = ttk.Spinbox(row_sreg, from_=1.5, to=5.0, increment=0.5, width=4)
        self.sp_r_sreg_mult.set("2.0")
        self.sp_r_sreg_mult.pack(side="left", padx=2)
        tk.Label(row_sreg, text="x   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_sreg_dur = ttk.Spinbox(row_sreg, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_sreg_dur.set("5.0")
        self.sp_r_sreg_dur.pack(side="left", padx=2)
        tk.Label(row_sreg, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 20. CC
        row_cc = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["cc"] = row_cc
        tk.Label(row_cc, text="Hiệu ứng CC:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_cc_type = ttk.Combobox(row_cc, values=["Choáng (stun)", "Làm chậm (slow)"], width=16, state="readonly")
        self.cb_r_cc_type.set("Choáng (stun)")
        self.cb_r_cc_type.pack(side="left", padx=4)
        tk.Label(row_cc, text="Thời gian:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_cc_dur = ttk.Spinbox(row_cc, from_=0.5, to=10.0, increment=0.5, width=5)
        self.sp_r_cc_dur.set("1.5")
        self.sp_r_cc_dur.pack(side="left", padx=2)
        tk.Label(row_cc, text="s   (Nếu slow) Giảm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_cc_slow = ttk.Spinbox(row_cc, from_=10, to=90, increment=5, width=5)
        self.sp_r_cc_slow.set("30")
        self.sp_r_cc_slow.pack(side="left", padx=2)
        tk.Label(row_cc, text="%", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 21. Stamina Drain
        row_sdrain = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["stamina_drain"] = row_sdrain
        tk.Label(row_sdrain, text="Thể Lực bị trừ của địch:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_sdrain_amt = ttk.Spinbox(row_sdrain, from_=10, to=150, increment=5, width=6)
        self.sp_r_sdrain_amt.set("40")
        self.sp_r_sdrain_amt.pack(side="left", padx=4)
        tk.Label(row_sdrain, text="điểm stamina", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 22. Cooldown Silence
        row_silence = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["cd_silence"] = row_silence
        tk.Label(row_silence, text="Kéo dài hồi chiêu kỹ năng của địch thêm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_r_silence_amt = ttk.Spinbox(row_silence, from_=0.5, to=10.0, increment=0.5, width=5)
        self.sp_r_silence_amt.set("2.0")
        self.sp_r_silence_amt.pack(side="left", padx=4)
        tk.Label(row_silence, text="giây", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 23. Element Status
        row_elem = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["element"] = row_elem
        tk.Label(row_elem, text="Trạng thái gán lên địch:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_elem_choice = ttk.Combobox(row_elem, values=["Ẩm Ướt (wet)", "Lạnh Buốt (frigid)", "Mất Máu (blood_loss)", "Hư Vô (vague)"], width=20, state="readonly")
        self.cb_r_elem_choice.set("Ẩm Ướt (wet)")
        self.cb_r_elem_choice.pack(side="left", padx=4)
        tk.Label(row_elem, text="Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_elem_dur = ttk.Spinbox(row_elem, from_=1.0, to=30.0, increment=1.0, width=5)
        self.sp_r_elem_dur.set("5.0")
        self.sp_r_elem_dur.pack(side="left", padx=2)
        tk.Label(row_elem, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 24. Shred DEF / RES
        row_shred = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["shred"] = row_shred
        tk.Label(row_shred, text="Chỉ số bào mòn:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.cb_r_shred_stat = ttk.Combobox(row_shred, values=["Giáp (defense)", "Toàn bộ kháng (res)"], width=18, state="readonly")
        self.cb_r_shred_stat.set("Giáp (defense)")
        self.cb_r_shred_stat.pack(side="left", padx=4)
        tk.Label(row_shred, text="Giảm:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_shred_val = ttk.Spinbox(row_shred, from_=10, to=80, increment=5, width=4)
        self.sp_r_shred_val.set("30")
        self.sp_r_shred_val.pack(side="left", padx=2)
        tk.Label(row_shred, text="%   Duy trì:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(6, 2))
        self.sp_r_shred_dur = ttk.Spinbox(row_shred, from_=1.0, to=30.0, increment=0.5, width=5)
        self.sp_r_shred_dur.set("4.0")
        self.sp_r_shred_dur.pack(side="left", padx=2)
        tk.Label(row_shred, text="s", font=("Segoe UI", 8), fg=self.c_dim, bg=self.c_surface).pack(side="left")

        # 25. Instant Info
        row_instant = tk.Frame(self.frame_act_details, bg=self.c_surface)
        self.act_sub_widgets["instant_info"] = row_instant
        self.lbl_r_instant_info = tk.Label(row_instant, text="✓ Hiệu ứng kích hoạt tức thì không cần thêm tham số.",
                                           font=("Segoe UI", 8, "italic"), fg="#00e676", bg=self.c_surface)
        self.lbl_r_instant_info.pack(side="left", padx=4)

        self.on_r_action_change()

        self.on_r_action_change()

        # 4. Chỉ Số Tĩnh Cộng Thẳng (Passive Stat Mods)
        mods_box = tk.LabelFrame(r_form, text=" 4. CHỈ SỐ TĨNH LIÊN TỤC (PASSIVE STAT MODS - TÙY CHỌN) ",
                                 font=("Segoe UI", 8, "bold"), fg=self.c_fg, bg=self.c_surface, padx=10, pady=6, bd=1, relief="solid")
        mods_box.pack(fill="x", pady=(0, 6))

        self.var_r_has_mods = tk.BooleanVar(value=False)
        cb_has_mods = tk.Checkbutton(mods_box, text="Cộng chỉ số tĩnh liên tục (Stat Mods)",
                                     variable=self.var_r_has_mods, font=("Segoe UI", 8, "bold"),
                                     fg="#ffffff", bg=self.c_surface, selectcolor="#000000",
                                     activebackground=self.c_surface, activeforeground="#ffffff",
                                     command=self.toggle_r_mods_view)
        cb_has_mods.pack(anchor="w")

        self.frame_mods_settings = tk.Frame(mods_box, bg=self.c_surface)
        self.frame_mods_settings.pack(fill="x", pady=4)

        mod_r1 = tk.Frame(self.frame_mods_settings, bg=self.c_surface)
        mod_r1.pack(fill="x", pady=2)

        tk.Label(mod_r1, text="ATK (+):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_mod_atk = ttk.Spinbox(mod_r1, from_=0, to=2000, increment=50, width=6)
        self.sp_mod_atk.set("0")
        self.sp_mod_atk.pack(side="left", padx=4)

        tk.Label(mod_r1, text="DEF (+):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_mod_def = ttk.Spinbox(mod_r1, from_=0, to=5000, increment=100, width=6)
        self.sp_mod_def.set("0")
        self.sp_mod_def.pack(side="left", padx=4)

        tk.Label(mod_r1, text="HP (+):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_mod_hp = ttk.Spinbox(mod_r1, from_=0, to=20000, increment=500, width=7)
        self.sp_mod_hp.set("0")
        self.sp_mod_hp.pack(side="left", padx=4)

        mod_r2 = tk.Frame(self.frame_mods_settings, bg=self.c_surface)
        mod_r2.pack(fill="x", pady=2)

        tk.Label(mod_r2, text="CDR (%):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left")
        self.sp_mod_cdr = ttk.Spinbox(mod_r2, from_=0, to=60, increment=5, width=5)
        self.sp_mod_cdr.set("0")
        self.sp_mod_cdr.pack(side="left", padx=4)

        tk.Label(mod_r2, text="MC (%):", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_mod_mc = ttk.Spinbox(mod_r2, from_=0, to=50, increment=5, width=5)
        self.sp_mod_mc.set("0")
        self.sp_mod_mc.pack(side="left", padx=4)

        tk.Label(mod_r2, text="Xuyên giáp phẳng:", font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_surface).pack(side="left", padx=(8, 0))
        self.sp_mod_fignore = ttk.Spinbox(mod_r2, from_=0, to=500, increment=25, width=6)
        self.sp_mod_fignore.set("0")
        self.sp_mod_fignore.pack(side="left", padx=4)

        self.toggle_r_mods_view()

        # 5. Thanh Lưu & Phản Hồi
        save_box = tk.Frame(r_form, bg=self.c_surface, pady=8)
        save_box.pack(fill="x", pady=(4, 8))

        btn_save_r = tk.Button(save_box, text="💾 LƯU RELIC VÀO HỆ THỐNG", font=("Segoe UI", 9, "bold"),
                               bg="#ffffff", fg="#000000", relief="flat", padx=18, pady=5,
                               cursor="hand2", activebackground="#dddddd", command=self.save_relic_action)
        btn_save_r.pack(side="left")

        self.lbl_relic_form_msg = tk.Label(save_box, text="", font=("Segoe UI", 8, "bold"),
                                           bg=self.c_surface, fg="#00e676")
        self.lbl_relic_form_msg.pack(side="left", padx=8)

        self.refresh_relics_tree()

    def toggle_r_trigger_view(self):
        if self.var_r_has_trigger.get():
            self.frame_trig_settings.pack(fill="x", pady=4)
        else:
            self.frame_trig_settings.pack_forget()

    def toggle_r_mods_view(self):
        if self.var_r_has_mods.get():
            self.frame_mods_settings.pack(fill="x", pady=4)
        else:
            self.frame_mods_settings.pack_forget()

    def on_r_action_change(self, event=None):
        raw_choice = self.cb_r_action.get()
        act_key = self.REWARD_ACTION_REVERSE.get(raw_choice, "reduce_cd")

        for w in self.act_sub_widgets.values():
            w.pack_forget()

        if act_key in ("reduce_cd", "reset_cd"):
            self.act_sub_widgets["cd"].pack(fill="x")
        elif act_key == "gain_charge":
            self.act_sub_widgets["gain_charge"].pack(fill="x")
        elif act_key == "echo_strike":
            self.act_sub_widgets["echo"].pack(fill="x")
        elif act_key == "buff_stat":
            self.act_sub_widgets["buff"].pack(fill="x")
        elif act_key == "stacking_atk":
            self.act_sub_widgets["stacking_atk"].pack(fill="x")
        elif act_key == "true_damage":
            self.act_sub_widgets["true_dmg"].pack(fill="x")
        elif act_key == "execute_damage":
            self.act_sub_widgets["execute"].pack(fill="x")
        elif act_key == "lifesteal":
            self.act_sub_widgets["lifesteal"].pack(fill="x")
        elif act_key == "stamina_leech":
            self.act_sub_widgets["stamina_leech"].pack(fill="x")
        elif act_key == "aoe_shockwave":
            self.act_sub_widgets["aoe_wave"].pack(fill="x")
        elif act_key == "def_to_atk":
            self.act_sub_widgets["def_to_atk"].pack(fill="x")
        elif act_key == "berserk_scaling":
            self.act_sub_widgets["berserk"].pack(fill="x")
        elif act_key in ("heal", "shield"):
            self.act_sub_widgets["heal_sh"].pack(fill="x")
        elif act_key == "hot":
            self.act_sub_widgets["hot"].pack(fill="x")
        elif act_key in ("reflective_shield", "damage_reflection"):
            self.act_sub_widgets["reflect"].pack(fill="x")
        elif act_key in ("free_cast", "iframes", "damage_to_heal", "super_armor", "zero_stamina_cost",
                         "extended_evasion", "cast_speed_buff", "stamina_freeze", "evasion_lock", "anti_heal"):
            self.act_sub_widgets["duration_only"].pack(fill="x")
        elif act_key == "death_defiance":
            self.act_sub_widgets["death_defiance"].pack(fill="x")
        elif act_key == "restore_stamina":
            self.act_sub_widgets["stam"].pack(fill="x")
        elif act_key == "stamina_regen":
            self.act_sub_widgets["stam_regen"].pack(fill="x")
        elif act_key == "apply_cc":
            self.act_sub_widgets["cc"].pack(fill="x")
        elif act_key == "stamina_drain":
            self.act_sub_widgets["stamina_drain"].pack(fill="x")
        elif act_key == "cooldown_silence":
            self.act_sub_widgets["cd_silence"].pack(fill="x")
        elif act_key == "apply_elemental_status":
            self.act_sub_widgets["element"].pack(fill="x")
        elif act_key == "shred_def_res":
            self.act_sub_widgets["shred"].pack(fill="x")
        elif act_key in ("reset_dodge_cd", "dot_detonation", "auto_cleanse", "contagion"):
            self.act_sub_widgets["instant_info"].pack(fill="x")

    def refresh_relics_tree(self):
        for item in self.tree_relics.get_children():
            self.tree_relics.delete(item)

        filter_txt = (self.ent_search_relic.get() if hasattr(self, "ent_search_relic") else "").lower().strip()
        cat = (self.cb_relic_cat.get() if hasattr(self, "cb_relic_cat") else "Tất cả")

        for rid, r in sorted(self.cfg.get("relics", {}).items()):
            if rid.startswith("_"):
                continue
            name = r.get("name", rid)
            has_trig = bool(r.get("triggers"))
            has_mods = bool(r.get("mods"))
            has_grants = bool(r.get("grants"))

            kind = "Trigger" if has_trig else ("Chỉ số" if has_mods else ("Nguyên tố" if has_grants else "Khác"))

            if cat == "Nội tại kích hoạt (Triggers)" and not has_trig:
                continue
            elif cat == "Chỉ số tĩnh (Mods)" and not has_mods:
                continue
            elif cat == "Nội tại nguyên tố" and not has_grants:
                continue

            if filter_txt and (filter_txt not in rid.lower() and filter_txt not in name.lower()):
                continue

            self.tree_relics.insert("", "end", iid=rid, values=(name, kind))

    def on_relic_tree_select(self, event=None):
        sel = self.tree_relics.selection()
        if not sel:
            return
        rid = sel[0]
        r = self.cfg.get("relics", {}).get(rid)
        if not r:
            return

        self.editing_relic_key = rid
        self.ent_relic_key.delete(0, "end")
        self.ent_relic_key.insert(0, rid)

        self.ent_relic_name.delete(0, "end")
        self.ent_relic_name.insert(0, r.get("name", rid))

        self.ent_relic_desc.delete(0, "end")
        self.ent_relic_desc.insert(0, r.get("desc", ""))

        # Triggers
        trigs = r.get("triggers", [])
        if trigs:
            self.var_r_has_trigger.set(True)
            self.toggle_r_trigger_view()
            tr0 = trigs[0]
            ev = tr0.get("type", "on_dodge")
            self.cb_r_event.set(self.TRIGGER_EVENT_MAP.get(ev, list(self.TRIGGER_EVENT_MAP.values())[0]))
            self.sp_r_icd.set(str(tr0.get("icd", tr0.get("every", 1.5))))
            self.sp_r_chance.set(str(int(tr0.get("chance", 1.0) * 100)))
            self.sp_r_hp_thresh.set(str(int(tr0.get("hp_threshold", 0.5) * 100)))
            self.sp_r_heavy_thresh.set(str(int(tr0.get("heavy_hit_pct", 0.15) * 100)))
            self.sp_r_combo_req.set(str(tr0.get("min_combo", 3)))
            self.sp_r_combat_t.set(str(tr0.get("combat_time", 10.0)))

            act = tr0.get("action", "reduce_cd")
            self.cb_r_action.set(self.REWARD_ACTION_MAP.get(act, list(self.REWARD_ACTION_MAP.values())[0]))
            self.on_r_action_change()

            if act in ("reduce_cd", "reset_cd"):
                tsk = tr0.get("target_skill", "basic")
                cd_map = {"basic": "Chiêu Basic (basic)", "branch_a": "Nhánh 1 (branch_a)", "branch_b": "Nhánh 2 (branch_b)", "all": "Toàn bộ chiêu (all)"}
                self.cb_r_cd_target.set(cd_map.get(tsk, "Chiêu Basic (basic)"))
                self.sp_r_cd_pct.set(str(int(tr0.get("value_pct", 0.5) * 100)))
            elif act == "gain_charge":
                tsk = tr0.get("target_skill", "basic")
                cd_map = {"basic": "Chiêu Basic (basic)", "branch_a": "Nhánh 1 (branch_a)", "branch_b": "Nhánh 2 (branch_b)", "all": "Toàn bộ chiêu (all)"}
                self.cb_r_gc_target.set(cd_map.get(tsk, "Chiêu Basic (basic)"))
                self.sp_r_gc_num.set(str(tr0.get("charges", 1)))
            elif act == "echo_strike":
                self.sp_r_echo_pct.set(str(int(tr0.get("echo_pct", 0.5) * 100)))
            elif act == "buff_stat":
                self.cb_r_buff_stat.set(tr0.get("stat", "atk"))
                self.sp_r_buff_val.set(str(int(tr0.get("value", 0.2) * 100) if tr0.get("mode") == "pct" else tr0.get("value", 20)))
                self.sp_r_buff_dur.set(str(tr0.get("duration", 4.0)))
            elif act == "stacking_atk":
                self.sp_r_stk_val.set(str(int(tr0.get("value", 0.05) * 100)))
                self.sp_r_stk_max.set(str(tr0.get("max_stacks", 5)))
                self.sp_r_stk_dur.set(str(tr0.get("duration", 6.0)))
            elif act == "true_damage":
                self.sp_r_td_flat.set(str(tr0.get("amount", 150)))
                self.sp_r_td_pct.set(str(int(tr0.get("pct_max", 0.0) * 100)))
            elif act == "execute_damage":
                self.sp_r_exec_base.set(str(tr0.get("amount", 200)))
                self.sp_r_exec_mult.set(str(tr0.get("missing_scale", 1.5)))
            elif act == "lifesteal":
                self.sp_r_ls_pct.set(str(int(tr0.get("lifesteal_pct", 0.3) * 100)))
                self.sp_r_ls_dur.set(str(tr0.get("duration", 5.0)))
            elif act == "stamina_leech":
                self.sp_r_sleech_amt.set(str(tr0.get("amount", 30)))
            elif act == "aoe_shockwave":
                self.sp_r_wave_base.set(str(tr0.get("amount", 250)))
                self.sp_r_wave_scale.set(str(int(tr0.get("atk_scale", 0.5) * 100)))
            elif act == "def_to_atk":
                self.sp_r_d2a_pct.set(str(int(tr0.get("conversion_pct", 0.25) * 100)))
                self.sp_r_d2a_dur.set(str(tr0.get("duration", 5.0)))
            elif act == "berserk_scaling":
                self.sp_r_berserk_mult.set(str(int(tr0.get("mult_per_10pct", 0.05) * 100)))
                self.sp_r_berserk_dur.set(str(tr0.get("duration", 5.0)))
            elif act in ("heal", "shield"):
                self.sp_r_heal_pct.set(str(int(tr0.get("pct_max", 0.1) * 100)))
                self.sp_r_heal_flat.set(str(tr0.get("amount", 0)))
                self.sp_r_sh_dur.set(str(tr0.get("duration", 5.0)))
            elif act == "hot":
                self.sp_r_hot_pct.set(str(int(tr0.get("pct_max", 0.15) * 100)))
                self.sp_r_hot_flat.set(str(tr0.get("amount", 0)))
                self.sp_r_hot_dur.set(str(tr0.get("duration", 5.0)))
            elif act in ("reflective_shield", "damage_reflection"):
                self.sp_r_ref_pct.set(str(int(tr0.get("reflect_pct", 0.35) * 100)))
                self.sp_r_ref_dur.set(str(tr0.get("duration", 5.0)))
            elif act in ("free_cast", "iframes", "damage_to_heal", "super_armor", "zero_stamina_cost",
                         "extended_evasion", "cast_speed_buff", "stamina_freeze", "evasion_lock", "anti_heal"):
                self.sp_r_dur_val.set(str(tr0.get("duration", 3.0)))
            elif act == "death_defiance":
                self.sp_r_dd_hp.set(str(int(tr0.get("hp_pct", 0.20) * 100)))
                self.sp_r_dd_iframe.set(str(tr0.get("duration", 1.5)))
                self.sp_r_dd_shield.set(str(int(tr0.get("shield_pct", 0.35) * 100)))
            elif act == "restore_stamina":
                self.sp_r_stam_amt.set(str(tr0.get("amount", 30)))
            elif act == "stamina_regen":
                self.sp_r_sreg_mult.set(str(tr0.get("regen_mult", 2.0)))
                self.sp_r_sreg_dur.set(str(tr0.get("duration", 5.0)))
            elif act == "apply_cc":
                eff = (tr0.get("effects") or [{}])[0]
                cc_typ = tr0.get("cc_type") or eff.get("type", "stun")
                self.cb_r_cc_type.set("Choáng (stun)" if cc_typ == "stun" else "Làm chậm (slow)")
                self.sp_r_cc_dur.set(str(tr0.get("duration", eff.get("duration", 1.5))))
                self.sp_r_cc_slow.set(str(int(tr0.get("slow_pct", eff.get("value", 0.3)) * 100)))
            elif act == "stamina_drain":
                self.sp_r_sdrain_amt.set(str(tr0.get("amount", 40)))
            elif act == "cooldown_silence":
                self.sp_r_silence_amt.set(str(tr0.get("amount", 2.0)))
            elif act == "apply_elemental_status":
                el = tr0.get("element", "wet")
                el_map = {"wet": "Ẩm Ướt (wet)", "frigid": "Lạnh Buốt (frigid)", "blood_loss": "Mất Máu (blood_loss)", "vague": "Hư Vô (vague)"}
                self.cb_r_elem_choice.set(el_map.get(el, "Ẩm Ướt (wet)"))
                self.sp_r_elem_dur.set(str(tr0.get("duration", 5.0)))
            elif act == "shred_def_res":
                self.cb_r_shred_stat.set("Giáp (defense)" if tr0.get("stat") == "defense" else "Toàn bộ kháng (res)")
                self.sp_r_shred_val.set(str(int(tr0.get("value", 0.3) * 100)))
                self.sp_r_shred_dur.set(str(tr0.get("duration", 4.0)))
        else:
            self.var_r_has_trigger.set(False)
            self.toggle_r_trigger_view()

        # Mods
        mods = r.get("mods", [])
        if mods:
            self.var_r_has_mods.set(True)
            self.toggle_r_mods_view()
            m_dict = {m.get("stat"): m.get("value", 0) for m in mods}
            self.sp_mod_atk.set(str(int(m_dict.get("atk", 0))))
            self.sp_mod_def.set(str(int(m_dict.get("defense", 0))))
            self.sp_mod_hp.set(str(int(m_dict.get("hp", 0))))
            self.sp_mod_cdr.set(str(int(m_dict.get("cdr", 0) * 100)))
            self.sp_mod_mc.set(str(int(m_dict.get("mc", 0) * 100)))
            self.sp_mod_fignore.set(str(int(m_dict.get("flat_def_ignore", 0))))
        else:
            self.var_r_has_mods.set(False)
            self.toggle_r_mods_view()

        # Update card
        card_text = f"• Mã: {rid}\n• Tên: {r.get('name', rid)}\n• Mô tả: {r.get('desc', 'Không')}\n"
        if trigs:
            card_text += f"• Trigger: {tr0.get('type')} → {tr0.get('action')} (ICD {tr0.get('icd', 0)}s)\n"
        if mods:
            card_text += f"• Mods: " + ", ".join(f"{m.get('stat')} +{m.get('value')}" for m in mods) + "\n"
        if r.get("grants"):
            card_text += f"• Cấp nội tại: {', '.join(r.get('grants'))}"
        self.lbl_relic_card.config(text=card_text)
        self.lbl_relic_form_msg.config(text=f"Đang xem [{rid}]", fg="#cccccc")

    def new_relic_form(self):
        self.editing_relic_key = None
        idx = 1
        while f"relic_custom_{idx}" in self.cfg.get("relics", {}):
            idx += 1
        new_id = f"relic_custom_{idx}"

        self.ent_relic_key.delete(0, "end")
        self.ent_relic_key.insert(0, new_id)

        self.ent_relic_name.delete(0, "end")
        self.ent_relic_name.insert(0, f"Nội tại Tự Chọn #{idx}")

        self.ent_relic_desc.delete(0, "end")
        self.ent_relic_desc.insert(0, "Mô tả cơ chế kích hoạt của nội tại")

        self.var_r_has_trigger.set(True)
        self.toggle_r_trigger_view()
        self.cb_r_event.set(self.TRIGGER_EVENT_MAP["on_dodge"])
        self.sp_r_icd.set("1.5")
        self.sp_r_chance.set("100")
        self.sp_r_hp_thresh.set("50")
        self.sp_r_heavy_thresh.set("15")
        self.sp_r_combo_req.set("3")
        self.sp_r_combat_t.set("10.0")
        self.cb_r_action.set(self.REWARD_ACTION_MAP["reduce_cd"])
        self.on_r_action_change()
        self.cb_r_cd_target.set("Chiêu Basic (basic)")
        self.sp_r_cd_pct.set("50")

        self.var_r_has_mods.set(False)
        self.toggle_r_mods_view()
        self.sp_mod_atk.set("0")
        self.sp_mod_def.set("0")
        self.sp_mod_hp.set("0")
        self.sp_mod_cdr.set("0")
        self.sp_mod_mc.set("0")
        self.sp_mod_fignore.set("0")

        self.lbl_relic_card.config(text=f"Đang soạn thảo Relic mới [{new_id}].")
        self.lbl_relic_form_msg.config(text="Đang soạn Relic mới", fg="#cccccc")

    def clone_relic_action(self):
        sel = self.tree_relics.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 Relic để nhân bản!")
            return
        rid = sel[0]
        orig = self.cfg.get("relics", {}).get(rid)
        if not orig:
            return

        new_rid = f"{rid}_copy"
        idx = 2
        while new_rid in self.cfg.get("relics", {}):
            new_rid = f"{rid}_copy_{idx}"
            idx += 1

        cloned = copy.deepcopy(orig)
        cloned["name"] = f"{orig.get('name', rid)} (Bản sao)"
        self.cfg["relics"][new_rid] = cloned
        self.save_relics_to_disk()
        self.refresh_relics_tree()
        self.tree_relics.selection_set(new_rid)
        self.on_relic_tree_select()
        self.lbl_relic_form_msg.config(text=f"✓ Đã nhân bản thành [{new_rid}]!", fg="#00e676")

    def delete_relic_action(self):
        sel = self.tree_relics.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 Relic để xóa!")
            return
        rid = sel[0]
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa Relic '{rid}' không?\nHành động này sẽ cập nhật config/relics.json."):
            return
        if rid in self.cfg.get("relics", {}):
            del self.cfg["relics"][rid]
            self.save_relics_to_disk()
            self.refresh_relics_tree()
            self.new_relic_form()
            self.lbl_relic_form_msg.config(text=f"✓ Đã xóa relic [{rid}].", fg="#ff6666")

    def save_relic_action(self):
        rid = self.ent_relic_key.get().strip()
        if not rid:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập Mã Relic (Key ID)!")
            return
        rname = self.ent_relic_name.get().strip() or rid
        rdesc = self.ent_relic_desc.get().strip()

        relic_obj = {
            "name": rname,
            "desc": rdesc
        }

        # Triggers
        if self.var_r_has_trigger.get():
            ev_label = self.cb_r_event.get()
            ev_key = self.TRIGGER_EVENT_REVERSE.get(ev_label, "on_dodge")
            icd_val = float(self.sp_r_icd.get() or 1.5)
            chance_val = float(self.sp_r_chance.get() or 100) / 100.0

            act_label = self.cb_r_action.get()
            act_key = self.REWARD_ACTION_REVERSE.get(act_label, "reduce_cd")

            trig_dict = {
                "type": ev_key,
                "icd": icd_val,
                "chance": chance_val,
                "action": act_key
            }

            if ev_key in ("on_hp_below", "on_hp_above", "on_target_hp_below"):
                trig_dict["hp_threshold"] = float(self.sp_r_hp_thresh.get() or 50) / 100.0
            elif ev_key == "on_take_heavy_hit":
                trig_dict["heavy_hit_pct"] = float(self.sp_r_heavy_thresh.get() or 15) / 100.0
            elif ev_key == "on_combo_hits":
                trig_dict["min_combo"] = int(self.sp_r_combo_req.get() or 3)
            elif ev_key == "on_combat_time_elapsed":
                trig_dict["combat_time"] = float(self.sp_r_combat_t.get() or 10.0)

            target_map = {
                "Chiêu Basic (basic)": "basic",
                "Nhánh 1 (branch_a)": "branch_a",
                "Nhánh 2 (branch_b)": "branch_b",
                "Toàn bộ chiêu (all)": "all"
            }

            if act_key in ("reduce_cd", "reset_cd"):
                trig_dict["target_skill"] = target_map.get(self.cb_r_cd_target.get(), "basic")
                if act_key == "reduce_cd":
                    trig_dict["value_pct"] = float(self.sp_r_cd_pct.get() or 50) / 100.0
            elif act_key == "gain_charge":
                trig_dict["target_skill"] = target_map.get(self.cb_r_gc_target.get(), "basic")
                trig_dict["charges"] = int(self.sp_r_gc_num.get() or 1)
            elif act_key == "echo_strike":
                trig_dict["echo_pct"] = float(self.sp_r_echo_pct.get() or 50) / 100.0
            elif act_key == "buff_stat":
                st = self.cb_r_buff_stat.get()
                v = float(self.sp_r_buff_val.get() or 20) / 100.0
                dur = float(self.sp_r_buff_dur.get() or 4.0)
                trig_dict["stat"] = st
                trig_dict["mode"] = "pct"
                trig_dict["value"] = v
                trig_dict["duration"] = dur
            elif act_key == "stacking_atk":
                trig_dict["value"] = float(self.sp_r_stk_val.get() or 5) / 100.0
                trig_dict["max_stacks"] = int(self.sp_r_stk_max.get() or 5)
                trig_dict["duration"] = float(self.sp_r_stk_dur.get() or 6.0)
            elif act_key == "true_damage":
                trig_dict["amount"] = float(self.sp_r_td_flat.get() or 150)
                trig_dict["pct_max"] = float(self.sp_r_td_pct.get() or 0) / 100.0
            elif act_key == "execute_damage":
                trig_dict["amount"] = float(self.sp_r_exec_base.get() or 200)
                trig_dict["missing_scale"] = float(self.sp_r_exec_mult.get() or 1.5)
            elif act_key == "lifesteal":
                trig_dict["lifesteal_pct"] = float(self.sp_r_ls_pct.get() or 30) / 100.0
                trig_dict["duration"] = float(self.sp_r_ls_dur.get() or 5.0)
            elif act_key == "stamina_leech":
                trig_dict["amount"] = float(self.sp_r_sleech_amt.get() or 30)
            elif act_key == "aoe_shockwave":
                trig_dict["amount"] = float(self.sp_r_wave_base.get() or 250)
                trig_dict["atk_scale"] = float(self.sp_r_wave_scale.get() or 50) / 100.0
            elif act_key == "def_to_atk":
                trig_dict["conversion_pct"] = float(self.sp_r_d2a_pct.get() or 25) / 100.0
                trig_dict["duration"] = float(self.sp_r_d2a_dur.get() or 5.0)
            elif act_key == "berserk_scaling":
                trig_dict["mult_per_10pct"] = float(self.sp_r_berserk_mult.get() or 5) / 100.0
                trig_dict["duration"] = float(self.sp_r_berserk_dur.get() or 5.0)
            elif act in ("heal", "shield"):
                pct = float(self.sp_r_heal_pct.get() or 0) / 100.0
                flat = float(self.sp_r_heal_flat.get() or 0)
                dur = float(self.sp_r_sh_dur.get() or 5.0)
                trig_dict["pct_max"] = pct
                trig_dict["amount"] = flat
                if act == "shield":
                    trig_dict["duration"] = dur
            elif act == "hot":
                trig_dict["pct_max"] = float(self.sp_r_hot_pct.get() or 15) / 100.0
                trig_dict["amount"] = float(self.sp_r_hot_flat.get() or 0)
                trig_dict["duration"] = float(self.sp_r_hot_dur.get() or 5.0)
            elif act in ("reflective_shield", "damage_reflection"):
                trig_dict["reflect_pct"] = float(self.sp_r_ref_pct.get() or 35) / 100.0
                trig_dict["duration"] = float(self.sp_r_ref_dur.get() or 5.0)
                if act == "reflective_shield":
                    trig_dict["pct_max"] = float(self.sp_r_heal_pct.get() or 20) / 100.0
                    trig_dict["amount"] = float(self.sp_r_heal_flat.get() or 0)
            elif act in ("free_cast", "iframes", "damage_to_heal", "super_armor", "zero_stamina_cost",
                         "extended_evasion", "cast_speed_buff", "stamina_freeze", "evasion_lock", "anti_heal"):
                trig_dict["duration"] = float(self.sp_r_dur_val.get() or 3.0)
            elif act == "death_defiance":
                trig_dict["hp_pct"] = float(self.sp_r_dd_hp.get() or 20) / 100.0
                trig_dict["duration"] = float(self.sp_r_dd_iframe.get() or 1.5)
                trig_dict["shield_pct"] = float(self.sp_r_dd_shield.get() or 35) / 100.0
            elif act == "restore_stamina":
                trig_dict["amount"] = float(self.sp_r_stam_amt.get() or 30)
            elif act == "stamina_regen":
                trig_dict["regen_mult"] = float(self.sp_r_sreg_mult.get() or 2.0)
                trig_dict["duration"] = float(self.sp_r_sreg_dur.get() or 5.0)
            elif act == "apply_cc":
                c_raw = self.cb_r_cc_type.get()
                cc_typ = "stun" if "stun" in c_raw else "slow"
                dur = float(self.sp_r_cc_dur.get() or 1.5)
                eff = {"type": cc_typ, "duration": dur}
                trig_dict["cc_type"] = cc_typ
                trig_dict["duration"] = dur
                if cc_typ == "slow":
                    slow_v = float(self.sp_r_cc_slow.get() or 30) / 100.0
                    eff["value"] = slow_v
                    trig_dict["slow_pct"] = slow_v
                trig_dict["effects"] = [eff]
            elif act == "stamina_drain":
                trig_dict["amount"] = float(self.sp_r_sdrain_amt.get() or 40)
            elif act == "cooldown_silence":
                trig_dict["amount"] = float(self.sp_r_silence_amt.get() or 2.0)
            elif act == "apply_elemental_status":
                raw_el = self.cb_r_elem_choice.get()
                elem = "wet" if "wet" in raw_el else ("frigid" if "frigid" in raw_el else ("blood_loss" if "blood_loss" in raw_el else "vague"))
                trig_dict["element"] = elem
                trig_dict["duration"] = float(self.sp_r_elem_dur.get() or 5.0)
            elif act == "shred_def_res":
                trig_dict["stat"] = "defense" if "defense" in self.cb_r_shred_stat.get() else "*"
                trig_dict["value"] = float(self.sp_r_shred_val.get() or 30) / 100.0
                trig_dict["duration"] = float(self.sp_r_shred_dur.get() or 4.0)

            relic_obj["triggers"] = [trig_dict]

        # Mods
        if self.var_r_has_mods.get():
            mods_list = []
            atk = float(self.sp_mod_atk.get() or 0)
            if atk > 0:
                mods_list.append({"stat": "atk", "mode": "add", "value": atk})
            defense = float(self.sp_mod_def.get() or 0)
            if defense > 0:
                mods_list.append({"stat": "defense", "mode": "add", "value": defense})
            hp = float(self.sp_mod_hp.get() or 0)
            if hp > 0:
                mods_list.append({"stat": "hp", "mode": "add", "value": hp})
            cdr = float(self.sp_mod_cdr.get() or 0) / 100.0
            if cdr > 0:
                mods_list.append({"stat": "cdr", "mode": "add", "value": cdr})
            mc = float(self.sp_mod_mc.get() or 0) / 100.0
            if mc > 0:
                mods_list.append({"stat": "mc", "mode": "add", "value": mc})
            fign = float(self.sp_mod_fignore.get() or 0)
            if fign > 0:
                mods_list.append({"stat": "flat_def_ignore", "mode": "add", "value": fign})

            if mods_list:
                relic_obj["mods"] = mods_list

        if self.editing_relic_key and self.editing_relic_key != rid:
            if rid in self.cfg.get("relics", {}):
                if not messagebox.askyesno("Ghi đè?", f"Relic '{rid}' đã tồn tại! Bạn có muốn ghi đè không?"):
                    return
            if self.editing_relic_key in self.cfg.get("relics", {}):
                del self.cfg["relics"][self.editing_relic_key]

        self.cfg["relics"][rid] = relic_obj
        self.editing_relic_key = rid
        self.save_relics_to_disk()
        self.refresh_relics_tree()
        self.tree_relics.selection_set(rid)
        self.on_relic_tree_select()

        self.lbl_relic_form_msg.config(text=f"✓ Đã lưu relic [{rid}] vào config/relics.json!", fg="#00e676")

    # --- Lưu & Đồng bộ cấu hình ---
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
            messagebox.showinfo("Thành công", "Đã lưu cấu hình mới vào config/rules.json!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu: {e}")

    def reset_all(self):
        if not messagebox.askyesno("Xác nhận", "Khôi phục toàn bộ các thanh trượt về cấu hình mặc định?"):
            return
        self.current_rules = copy.deepcopy(self.baseline_rules)
        self.destroy()
        app = IOMGymMonoApp()
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
    app = IOMGymMonoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
