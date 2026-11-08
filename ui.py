# -*- coding: utf-8 -*-
"""
IOM GYM - Giao diện trực quan cân bằng hiệu ứng (Magic Balance Studio).
Chạy lệnh: python ui.py
Tự động mở trình duyệt web với giao diện thanh trượt gọn gàng, tinh tế.
Hỗ trợ tinh chỉnh cả hệ thống hiệu ứng và tùy chỉnh chỉ số từng bên (Đội A vs Đội B).
"""
import copy
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import load_cfg, set_path, get_path, Sim  # noqa: E402
from gym import run_batch, soft_check, resolve_team, uptime_rows, pct  # noqa: E402

RULES_PATH = os.path.join(HERE, "config", "rules.json")

# Metadata định nghĩa các thanh trượt theo từng hiệu ứng Magic
SLIDERS_META = [
    # --- 🔥 Amgar (Molten Core) ---
    {
        "category": "amgar",
        "cat_name": "🔥 Amgar (Molten Core)",
        "color": "#f97316",
        "path": "passives.molten_core.def_pct",
        "label": "Tăng Defense %",
        "desc": "Tỉ lệ % Defense cộng thêm cho bản thân khi có Molten Core.",
        "min": 0.0, "max": 0.5, "step": 0.01, "unit": "%", "format": "percent"
    },
    {
        "category": "amgar",
        "cat_name": "🔥 Amgar (Molten Core)",
        "color": "#f97316",
        "path": "passives.molten_core.flat_ignore",
        "label": "Xuyên Giáp Phẳng (Flat Ignore)",
        "desc": "Lượng Defense cố định trừ trực tiếp vào phòng ngự đối phương.",
        "min": 0, "max": 300, "step": 5, "unit": "điểm", "format": "int"
    },
    {
        "category": "amgar",
        "cat_name": "🔥 Amgar (Molten Core)",
        "color": "#f97316",
        "path": "passives.molten_core.pct_ignore",
        "label": "Xuyên Giáp % (Pct Ignore)",
        "desc": "Tỉ lệ % Defense bị bỏ qua của đối thủ trước khi trừ giáp phẳng.",
        "min": 0.0, "max": 0.4, "step": 0.01, "unit": "%", "format": "percent"
    },

    # --- ❄️ Glacia (Frigid Core) ---
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.slow_per_stack",
        "label": "Làm Chậm / Tầng Freezing",
        "desc": "Mức làm chậm mỗi tầng Freezing tác động lên mục tiêu.",
        "min": 0.01, "max": 0.20, "step": 0.01, "unit": "%", "format": "percent"
    },
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.max_stacks",
        "label": "Số Tầng Kích Hoạt Frozen",
        "desc": "Đạt đủ số tầng Freezing này mục tiêu sẽ bị Đóng Băng hoàn toàn.",
        "min": 3, "max": 20, "step": 1, "unit": "tầng", "format": "int"
    },
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.icd",
        "label": "Hồi Chiêu Nhận Tầng (ICD)",
        "desc": "Khoảng cách thời gian tối thiểu giữa 2 lần cộng dồn Freezing.",
        "min": 0.1, "max": 5.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.frozen_duration",
        "label": "Thời Gian Đóng Băng (Frozen)",
        "desc": "Thời gian mục tiêu bị khống chế cứng trong trạng thái Frozen.",
        "min": 0.5, "max": 8.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.frozen_immunity",
        "label": "Thời Gian Miễn Nhiễm Sau Khi Rã Đông",
        "desc": "Sau khi thoát đóng băng, mục tiêu miễn nhiễm Frozen trong bao lâu.",
        "min": 0.0, "max": 10.0, "step": 0.5, "unit": "s", "format": "float"
    },
    {
        "category": "glacia",
        "cat_name": "❄️ Glacia (Frigid Core)",
        "color": "#38bdf8",
        "path": "passives.frigid_core.decay_interval",
        "label": "Chu Kỳ Giảm Tầng Tự Nhiên",
        "desc": "Cứ sau mỗi khoảng thời gian không nhận đòn sẽ mất 1 tầng Freezing.",
        "min": 0.1, "max": 3.0, "step": 0.1, "unit": "s", "format": "float"
    },

    # --- 🩸 Cruor (Blood Loss) ---
    {
        "category": "cruor",
        "cat_name": "🩸 Cruor (Blood Loss)",
        "color": "#f43f5e",
        "path": "passives.blood_loss.pct_per_stack",
        "label": "Mất Máu Mỗi Đòn / Tầng",
        "desc": "Sát thương mất máu theo % Max HP mỗi lần nhận đòn trên mỗi tầng.",
        "min": 0.001, "max": 0.020, "step": 0.001, "unit": "% Max HP", "format": "percent_fine"
    },
    {
        "category": "cruor",
        "cat_name": "🩸 Cruor (Blood Loss)",
        "color": "#f43f5e",
        "path": "passives.blood_loss.max_stacks",
        "label": "Số Tầng Tối Đa",
        "desc": "Số tầng Blood Loss tối đa có thể tích tụ trên 1 mục tiêu.",
        "min": 1, "max": 30, "step": 1, "unit": "tầng", "format": "int"
    },
    {
        "category": "cruor",
        "cat_name": "🩸 Cruor (Blood Loss)",
        "color": "#f43f5e",
        "path": "passives.blood_loss.duration",
        "label": "Thời Gian Duy Trì Tầng",
        "desc": "Thời gian tồn tại của các tầng Blood Loss trước khi hết hiệu lực.",
        "min": 1.0, "max": 15.0, "step": 0.5, "unit": "s", "format": "float"
    },
    {
        "category": "cruor",
        "cat_name": "🩸 Cruor (Blood Loss)",
        "color": "#f43f5e",
        "path": "passives.blood_loss.icd",
        "label": "ICD Nhận Tầng Mới",
        "desc": "Thời gian giãn cách tối thiểu giữa 2 lần cộng dồn Blood Loss.",
        "min": 0.1, "max": 3.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "cruor",
        "cat_name": "🩸 Cruor (Blood Loss)",
        "color": "#f43f5e",
        "path": "passives.blood_loss.lifesteal",
        "label": "Tỉ Lệ Hút Máu (Lifesteal)",
        "desc": "Hồi phục máu cho người tạo sát thương theo % sát thương gây ra.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },

    # --- 👁️ Ether (Vague Drain) ---
    {
        "category": "ether",
        "cat_name": "👁️ Ether (Vague Drain)",
        "color": "#c084fc",
        "path": "passives.vague_drain.icd",
        "label": "ICD Tích Tầng Vague",
        "desc": "Khoảng cách thời gian tối thiểu giữa các lần tích tầng Vague.",
        "min": 0.2, "max": 5.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "ether",
        "cat_name": "👁️ Ether (Vague Drain)",
        "color": "#c084fc",
        "path": "passives.vague_drain.max_stacks",
        "label": "Số Tầng Vague Tối Đa",
        "desc": "Số tầng Vague tối đa tích tụ trên mục tiêu.",
        "min": 1, "max": 20, "step": 1, "unit": "tầng", "format": "int"
    },
    {
        "category": "ether",
        "cat_name": "👁️ Ether (Vague Drain)",
        "color": "#c084fc",
        "path": "passives.vague_drain.drained_per_stack",
        "label": "Điểm Drained / Tầng",
        "desc": "Số điểm Drained tạo ra cho mỗi tầng Vague tích tụ.",
        "min": 0.2, "max": 5.0, "step": 0.1, "unit": "điểm", "format": "float"
    },
    {
        "category": "ether",
        "cat_name": "👁️ Ether (Vague Drain)",
        "color": "#c084fc",
        "path": "passives.vague_drain.drained_cap",
        "label": "Ngưỡng Drained Tối Đa (Chặn Buff)",
        "desc": "Khi đạt điểm Drained này sẽ cấm mục tiêu nhận các hiệu ứng Buff.",
        "min": 1, "max": 30, "step": 1, "unit": "điểm", "format": "int"
    },

    # --- 🌪️ Gale (Zephyr Core) ---
    {
        "category": "gale",
        "cat_name": "🌪️ Gale (Zephyr Core)",
        "color": "#34d399",
        "path": "passives.zephyr_core.stamina_cost_reduction",
        "label": "Giảm Tiêu Hao Thể Lực",
        "desc": "Tỉ lệ % giảm tiêu hao thể lực (Stamina) cho kỹ năng và hành động.",
        "min": 0.0, "max": 0.8, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "gale",
        "cat_name": "🌪️ Gale (Zephyr Core)",
        "color": "#34d399",
        "path": "passives.zephyr_core.speed_bonus",
        "label": "Tăng Tốc Độ Di Chuyển",
        "desc": "Gia tăng tốc độ chạy và cơ động cho nhân vật sở hữu Zephyr Core.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "gale",
        "cat_name": "🌪️ Gale (Zephyr Core)",
        "color": "#34d399",
        "path": "passives.zephyr_core.extra_dodge",
        "label": "Số Lần Né Đòn Thêm",
        "desc": "Số lần kích hoạt né tránh bổ sung mà không tốn lượt.",
        "min": 0, "max": 5, "step": 1, "unit": "lần", "format": "int"
    },

    # --- ⚡ Fulgur (Fulgur Chain) ---
    {
        "category": "fulgur",
        "cat_name": "⚡ Fulgur (Fulgur Chain)",
        "color": "#facc15",
        "path": "passives.fulgur_chain.bonus_pct",
        "label": "Sát Thương Lan / Thêm %",
        "desc": "Tỉ lệ sát thương sét lan thêm lên các mục tiêu phụ.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "fulgur",
        "cat_name": "⚡ Fulgur (Fulgur Chain)",
        "color": "#facc15",
        "path": "passives.fulgur_chain.max_secondary",
        "label": "Số Mục Tiêu Phụ Tối Đa",
        "desc": "Giới hạn số lượng mục tiêu phụ tối đa nhận sát thương chuỗi sét.",
        "min": 1, "max": 10, "step": 1, "unit": "mục tiêu", "format": "int"
    },

    # --- 🌑 Sable (Shadow Screep) ---
    {
        "category": "sable",
        "cat_name": "🌑 Sable (Shadow Screep)",
        "color": "#818cf8",
        "path": "passives.shadow_screep.slow_per_stack",
        "label": "Làm Chậm / Tầng",
        "desc": "Mức giảm tốc độ trên từng tầng Shadow Screep.",
        "min": 0.01, "max": 0.20, "step": 0.01, "unit": "%", "format": "percent"
    },
    {
        "category": "sable",
        "cat_name": "🌑 Sable (Shadow Screep)",
        "color": "#818cf8",
        "path": "passives.shadow_screep.max_stacks",
        "label": "Số Tầng Tối Đa",
        "desc": "Số tầng Shadow Screep tối đa trên mục tiêu.",
        "min": 1, "max": 20, "step": 1, "unit": "tầng", "format": "int"
    },
    {
        "category": "sable",
        "cat_name": "🌑 Sable (Shadow Screep)",
        "color": "#818cf8",
        "path": "passives.shadow_screep.icd",
        "label": "ICD Tích Tầng Mới",
        "desc": "Khoảng cách thời gian tối thiểu giữa các lần nhận tầng.",
        "min": 0.2, "max": 5.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "sable",
        "cat_name": "🌑 Sable (Shadow Screep)",
        "color": "#818cf8",
        "path": "passives.shadow_screep.stack_duration",
        "label": "Thời Gian Duy Trì Tầng",
        "desc": "Thời gian tồn tại của các tầng Shadow Screep trước khi biến mất.",
        "min": 1.0, "max": 20.0, "step": 0.5, "unit": "s", "format": "float"
    },

    # --- 💥 Entropy (Eruptive Core) ---
    {
        "category": "entropy",
        "cat_name": "💥 Entropy (Eruptive Core)",
        "color": "#fb7185",
        "path": "passives.eruptive_core.heal_pct",
        "label": "Hồi Máu Cứu Mạng (Heal %)",
        "desc": "Tỉ lệ % HP tối đa được hồi phục khi kích hoạt Eruptive Core lúc hấp hối.",
        "min": 0.05, "max": 1.0, "step": 0.05, "unit": "% Max HP", "format": "percent"
    },
    {
        "category": "entropy",
        "cat_name": "💥 Entropy (Eruptive Core)",
        "color": "#fb7185",
        "path": "passives.eruptive_core.iframe",
        "label": "Thời Gian Bất Tử (iFrame)",
        "desc": "Thời gian miễn nhiễm hoàn toàn mọi sát thương sau khi kích hoạt.",
        "min": 0.1, "max": 3.0, "step": 0.05, "unit": "s", "format": "float"
    },
    {
        "category": "entropy",
        "cat_name": "💥 Entropy (Eruptive Core)",
        "color": "#fb7185",
        "path": "passives.eruptive_core.cooldown",
        "label": "Hồi Chiêu Kỹ Năng",
        "desc": "Thời gian hồi chiêu trước khi Eruptive Core có thể cứu mạng lần kế.",
        "min": 10, "max": 300, "step": 5, "unit": "s", "format": "int"
    },

    # --- ⏳ TimeFlow (Chronomancy) ---
    {
        "category": "timeflow",
        "cat_name": "⏳ TimeFlow (Chronomancy)",
        "color": "#60a5fa",
        "path": "passives.chronomancy.cd_reduction",
        "label": "Giảm Hồi Chiêu CDR %",
        "desc": "Tỉ lệ % giảm thời gian hồi chiêu của các kỹ năng.",
        "min": 0.0, "max": 0.7, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "timeflow",
        "cat_name": "⏳ TimeFlow (Chronomancy)",
        "color": "#60a5fa",
        "path": "passives.chronomancy.lifetime_bonus",
        "label": "Tăng Thời Lượng Hiệu Ứng %",
        "desc": "Kéo dài thời gian tồn tại của các bùa lợi buff và hiệu ứng.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },

    # --- 🛡️ Agenet (Break & Sturd) ---
    {
        "category": "agenet",
        "cat_name": "🛡️ Agenet (Break & Sturd)",
        "color": "#eab308",
        "path": "passives.break.bonus_pct",
        "label": "Sát Thương Phá Vỡ (Break Bonus %)",
        "desc": "Tỉ lệ sát thương cộng thêm khi phá vỡ lớp bảo vệ Sturd.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "agenet",
        "cat_name": "🛡️ Agenet (Break & Sturd)",
        "color": "#eab308",
        "path": "passives.break.true_pct_max_hp",
        "label": "Sát Thương Chuẩn Theo % Max HP",
        "desc": "Sát thương chuẩn tính trực tiếp theo % máu tối đa của mục tiêu.",
        "min": 0.0, "max": 0.20, "step": 0.01, "unit": "% Max HP", "format": "percent"
    },
    {
        "category": "agenet",
        "cat_name": "🛡️ Agenet (Break & Sturd)",
        "color": "#eab308",
        "path": "passives.break.icd",
        "label": "ICD Break",
        "desc": "Khoảng cách thời gian tối thiểu giữa các lần kích hoạt Break.",
        "min": 0.5, "max": 5.0, "step": 0.1, "unit": "s", "format": "float"
    },
    {
        "category": "agenet",
        "cat_name": "🛡️ Agenet (Break & Sturd)",
        "color": "#eab308",
        "path": "passives.sturd.def_debuff",
        "label": "Giảm Defense Khi Bị Phá Vỡ",
        "desc": "Tỉ lệ % Defense bị trừ khi mục tiêu rơi vào trạng thái vỡ thể.",
        "min": 0.0, "max": 0.8, "step": 0.05, "unit": "%", "format": "percent"
    },

    # --- 💧 Wet & Nguyên Tố ---
    {
        "category": "elements",
        "cat_name": "💧 Wet & Khắc Hệ",
        "color": "#06b6d4",
        "path": "passives.wet.duration",
        "label": "Thời Lượng Hiệu Ứng Wet",
        "desc": "Thời gian tồn tại của trạng thái Ẩm Ướt (Wet) kích hoạt phản ứng.",
        "min": 1.0, "max": 20.0, "step": 0.5, "unit": "s", "format": "float"
    },
    {
        "category": "elements",
        "cat_name": "💧 Wet & Khắc Hệ",
        "color": "#06b6d4",
        "path": "passives.pure_type.damage_bonus",
        "label": "Sát Thương Hệ Thuần (PureType)",
        "desc": "Tỉ lệ % sát thương tăng thêm khi cả 2 nhánh đều chọn cùng một hệ Magic.",
        "min": 0.0, "max": 0.5, "step": 0.01, "unit": "%", "format": "percent"
    },
    {
        "category": "elements",
        "cat_name": "💧 Wet & Khắc Hệ",
        "color": "#06b6d4",
        "path": "passives.pure_type.res_pen",
        "label": "Xuyên Kháng Phép PureType",
        "desc": "Tỉ lệ xuyên kháng Magic Resistance cho nhân vật chơi hệ thuần.",
        "min": 0.0, "max": 0.3, "step": 0.01, "unit": "%", "format": "percent"
    },
    {
        "category": "elements",
        "cat_name": "💧 Wet & Khắc Hệ",
        "color": "#06b6d4",
        "path": "passives.reaction.icd",
        "label": "ICD Phản Ứng Nguyên Tố",
        "desc": "Thời gian giãn cách giữa các phản ứng nguyên tố trên cùng mục tiêu.",
        "min": 0.5, "max": 6.0, "step": 0.2, "unit": "s", "format": "float"
    },

    # --- ⚔️ Combat Giả Định & Chỉ Số ---
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "combat.p_hit",
        "label": "Tỉ Lệ Đánh Trúng (p_hit)",
        "desc": "Xác suất đòn đánh chạm trúng đích (không bị trượt).",
        "min": 0.1, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "combat.guard_q",
        "label": "Tỉ Lệ Đỡ Đòn (Guard / Block)",
        "desc": "Xác suất người phòng thủ vào thế Guard khi nhận đòn đánh.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "combat.gcd",
        "label": "Hồi Chiêu Chung (GCD)",
        "desc": "Khoảng trễ tối thiểu giữa hai hành động kỹ năng kế tiếp nhau.",
        "min": 0.1, "max": 2.0, "step": 0.05, "unit": "s", "format": "float"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "combat.slow_hit_bonus",
        "label": "Thưởng Tỉ Lệ Trúng Khi Đối Thủ Bị Slow",
        "desc": "Cộng thêm xác suất trúng đích khi đối phương đang chịu hiệu ứng làm chậm.",
        "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "stats_base.atk",
        "label": "Tấn Công Gốc (Base ATK)",
        "desc": "Chỉ số ATK mặc định của nhân vật trước khi tính bùa và trang bị.",
        "min": 50, "max": 1000, "step": 10, "unit": "điểm", "format": "int"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "stats_base.defense",
        "label": "Phòng Ngự Gốc (Base Defense)",
        "desc": "Chỉ số Defense mặc định của nhân vật giảm trừ sát thương nhận vào.",
        "min": 50, "max": 1500, "step": 25, "unit": "điểm", "format": "int"
    },
    {
        "category": "combat",
        "cat_name": "⚔️ Luật Chiến Đấu (Combat)",
        "color": "#a855f7",
        "path": "stats_caps.mc",
        "label": "Giới Hạn Tối Đa Magic Capacity",
        "desc": "Ngưỡng Cap cao nhất mà chỉ số Magic Capacity có thể đạt tới.",
        "min": 0.1, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent"
    }
]

# Danh mục các chỉ số có thể tùy chỉnh cho từng bên (Đội A / Đội B)
CUSTOM_STATS_META = [
    {"key": "hp", "label": "Máu (HP)", "min": 200, "max": 60000, "step": 100, "unit": "HP", "format": "int", "desc": "Lượng sinh mệnh tối đa"},
    {"key": "atk", "label": "Tấn Công (ATK)", "min": 0, "max": 2000, "step": 10, "unit": "ATK", "format": "int", "desc": "Sức mạnh đòn đánh gốc"},
    {"key": "defense", "label": "Phòng Ngự (DEF)", "min": 0, "max": 15000, "step": 25, "unit": "DEF", "format": "int", "desc": "Khả năng giảm trừ sát thương"},
    {"key": "mc", "label": "Magic Capacity", "min": 0.0, "max": 0.5, "step": 0.01, "unit": "%", "format": "percent", "desc": "Hệ số tăng cường hiệu ứng magic"},
    {"key": "pct_def_ignore", "label": "Xuyên Giáp %", "min": 0.0, "max": 0.5, "step": 0.01, "unit": "%", "format": "percent", "desc": "Bỏ qua % giáp của đối thủ"},
    {"key": "flat_def_ignore", "label": "Xuyên Giáp Phẳng", "min": 0, "max": 500, "step": 5, "unit": "điểm", "format": "int", "desc": "Trừ trực tiếp giáp phẳng"},
    {"key": "damage_mult", "label": "Hệ Số Damage", "min": 0.2, "max": 3.0, "step": 0.05, "unit": "x", "format": "float", "desc": "Bội số tổng sát thương gây ra"},
    {"key": "cdr", "label": "Giảm Hồi Chiêu", "min": 0.0, "max": 0.6, "step": 0.02, "unit": "%", "format": "percent", "desc": "Tỉ lệ % giảm thời gian CD skill"},
    {"key": "guard_q", "label": "Đỡ Đòn (Guard)", "min": 0.0, "max": 1.0, "step": 0.05, "unit": "%", "format": "percent", "desc": "Xác suất vào thế Guard khi nhận đòn"},
    {"key": "res", "label": "Kháng Toàn Phần", "min": 0.0, "max": 0.75, "step": 0.05, "unit": "%", "format": "percent", "desc": "Tỉ lệ kháng mọi ma thuật"}
]

# Lưu baseline rules gốc một lần để so sánh diff
_INITIAL_RULES = None
def get_baseline_rules():
    global _INITIAL_RULES
    if _INITIAL_RULES is None:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            _INITIAL_RULES = json.load(f)
    return copy.deepcopy(_INITIAL_RULES)


def get_current_rules():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rules(rules_obj):
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules_obj, f, ensure_ascii=False, indent=1)


def get_entity_default_stats(cfg, ent_id):
    """Lấy chỉ số mặc định của nhân vật hoặc dummy."""
    rules = cfg["rules"]
    base = dict(rules["stats_base"])
    guard_val = rules["combat"].get("guard_q", 0.35)
    res_val = 0.0

    if ent_id.startswith("dummy:"):
        did = ent_id[6:]
        d = cfg["scenarios"]["dummies"].get(did, {})
        base["hp"] = d.get("hp", 2000)
        base["defense"] = d.get("defense", 300)
        base["atk"] = 0
        guard_val = d.get("guard_q", 0.0)
        if "res" in d and d["res"]:
            res_val = max(d["res"].values())
    else:
        b = cfg["builds"].get(ent_id, {})
        base.update(b.get("stats", {}))
        if b.get("guard_q") is not None:
            guard_val = b["guard_q"]
        if "res" in b and b["res"]:
            res_val = max(b["res"].values())

    return {
        "hp": base.get("hp", 2000),
        "atk": base.get("atk", 200),
        "defense": base.get("defense", 300),
        "mc": base.get("mc", 0.0),
        "pct_def_ignore": base.get("pct_def_ignore", 0.05),
        "flat_def_ignore": base.get("flat_def_ignore", 50),
        "damage_mult": base.get("damage_mult", 1.0),
        "cdr": base.get("cdr", 0.0),
        "guard_q": guard_val,
        "res": res_val
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IOM GYM - Cân Bằng Hiệu Ứng & Chỉ Số Từng Bên</title>
  <style>
    :root {
      --bg: #0b0e14;
      --card-bg: #141824;
      --card-border: #23293b;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --accent-glow: rgba(56, 189, 248, 0.15);
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --team-a: #ef4444;
      --team-b: #3b82f6;
      --input-bg: #1b2030;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    body {
      background-color: var(--bg);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation Header */
    header {
      background: #111420;
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      font-size: 26px;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-text h1 {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-text p {
      font-size: 12px;
      color: var(--text-muted);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.2s ease;
      user-select: none;
    }

    .btn-primary { background: #0284c7; color: #fff; }
    .btn-primary:hover { background: #0369a1; }
    .btn-secondary { background: #1e2436; color: #cbd5e1; border-color: #333d54; }
    .btn-secondary:hover { background: #272f45; color: #fff; }
    .btn-success { background: #059669; color: #fff; }
    .btn-success:hover { background: #047857; }
    .btn-preset { background: #1c2336; border: 1px solid #2d3748; color: #cbd5e1; font-size: 11px; padding: 3px 8px; border-radius: 4px; cursor: pointer; }
    .btn-preset:hover { background: #29344d; color: #fff; border-color: var(--primary); }

    .badge-diff {
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 700;
      background: #1e293b;
      color: #94a3b8;
      border: 1px solid #334155;
    }
    .badge-diff.has-changes {
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border-color: #f59e0b;
    }

    /* Subheader / Tabs bar */
    .filter-bar {
      background: #0e121c;
      border-bottom: 1px solid var(--card-border);
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }

    .category-tabs {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
    }

    .tab-btn {
      padding: 6px 12px;
      border-radius: 6px;
      background: #161b28;
      color: var(--text-muted);
      border: 1px solid #232a3d;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .tab-btn:hover { background: #20273a; color: #fff; }
    .tab-btn.active { background: #1e3a5f; color: #38bdf8; border-color: #0284c7; }

    .filter-controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .search-input {
      background: var(--input-bg);
      border: 1px solid #2d3748;
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      width: 200px;
      outline: none;
    }
    .search-input:focus { border-color: var(--primary); }

    .toggle-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--text-muted);
      cursor: pointer;
      user-select: none;
    }

    /* Main Content Area */
    main {
      padding: 20px 24px;
      flex: 1;
      max-width: 1440px;
      margin: 0 auto;
      width: 100%;
    }

    .grid-container {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 20px;
    }

    /* Effect Card */
    .effect-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    .card-header {
      padding: 12px 16px;
      background: #181d2c;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .card-title {
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .card-badge {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: #252e46;
      color: #94a3b8;
    }
    .card-body {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    /* Slider Row */
    .slider-row {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding-bottom: 14px;
      border-bottom: 1px solid #1a2030;
    }
    .slider-row:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }
    .slider-meta {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
    }
    .slider-label {
      font-size: 13px;
      font-weight: 600;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .slider-path {
      font-size: 10px;
      color: #64748b;
      font-family: monospace;
    }
    .slider-diff-tag {
      font-size: 11px;
      font-weight: 600;
      padding: 1px 6px;
      border-radius: 4px;
      display: none;
    }
    .slider-diff-tag.changed {
      display: inline-block;
      background: rgba(245, 158, 11, 0.2);
      color: #f59e0b;
      border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .slider-controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .range-wrap {
      flex: 1;
      display: flex;
      align-items: center;
    }
    input[type=range] {
      -webkit-appearance: none;
      width: 100%;
      height: 6px;
      border-radius: 3px;
      background: #23293c;
      outline: none;
      cursor: pointer;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--thumb-color, #38bdf8);
      cursor: pointer;
      box-shadow: 0 0 6px rgba(56, 189, 248, 0.6);
      transition: transform 0.1s;
    }
    input[type=range]::-webkit-slider-thumb:hover {
      transform: scale(1.15);
    }
    .input-box {
      width: 82px;
      padding: 6px 8px;
      border-radius: 6px;
      background: var(--input-bg);
      border: 1px solid #2d3748;
      color: #f8fafc;
      font-size: 13px;
      font-weight: 600;
      text-align: right;
      outline: none;
    }
    .input-box:focus { border-color: var(--primary); }
    .unit-text { font-size: 11px; color: #94a3b8; min-width: 38px; }
    .btn-reset-item {
      background: transparent; border: none; color: #64748b; cursor: pointer; font-size: 13px; padding: 4px; border-radius: 4px;
    }
    .btn-reset-item:hover { color: #f87171; background: #1e2436; }
    .slider-desc { font-size: 11px; color: var(--text-muted); line-height: 1.4; }

    /* Custom Teams Section / Drawer */
    .sim-panel {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: #0f131f;
      border-top: 2px solid #252d42;
      box-shadow: 0 -8px 24px rgba(0,0,0,0.6);
      z-index: 90;
      transform: translateY(calc(100% - 46px));
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      max-height: 88vh;
      display: flex;
      flex-direction: column;
    }
    .sim-panel.open { transform: translateY(0); }

    .sim-header {
      padding: 12px 24px;
      background: #141826;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      user-select: none;
    }
    .sim-title {
      font-size: 14px;
      font-weight: 700;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .sim-content {
      padding: 18px 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    /* Dual Columns for Team A & Team B */
    .teams-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    @media (max-width: 860px) {
      .teams-grid { grid-template-columns: 1fr; }
    }

    .team-box {
      background: #131724;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .team-box.team-a-box { border-top: 3px solid var(--team-a); }
    .team-box.team-b-box { border-top: 3px solid var(--team-b); }

    .team-box-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }
    .team-title {
      font-size: 14px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .team-presets {
      display: flex;
      gap: 4px;
      flex-wrap: wrap;
    }

    .team-stats-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      background: #0d101b;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid #1e2436;
    }
    .team-stat-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .team-stat-lbl {
      font-size: 12px;
      font-weight: 600;
      width: 140px;
      color: #cbd5e1;
    }
    .team-stat-input {
      width: 76px;
      padding: 4px 6px;
      border-radius: 4px;
      background: #1a2030;
      border: 1px solid #2d3748;
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      text-align: right;
    }

    /* Simulation Control Row */
    .sim-match-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      background: #161b28;
      border: 1px solid #232c40;
      padding: 12px 18px;
      border-radius: 8px;
      flex-wrap: wrap;
    }
    .sim-bar-params {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }
    .select-box, .text-input {
      padding: 6px 10px;
      border-radius: 6px;
      background: var(--input-bg);
      border: 1px solid #2d3748;
      color: #fff;
      font-size: 13px;
      outline: none;
    }

    /* Results Card */
    .results-card {
      background: #141825;
      border: 1px solid #232c40;
      border-radius: 8px;
      padding: 16px;
    }
    .win-bar-wrap {
      margin: 12px 0;
      background: #1e2436;
      border-radius: 8px;
      height: 28px;
      overflow: hidden;
      display: flex;
      font-weight: 700;
      font-size: 12px;
      line-height: 28px;
    }
    .win-bar-a { background: #ef4444; color: #fff; text-align: left; padding-left: 10px; transition: width 0.3s; }
    .win-bar-draw { background: #475569; color: #fff; text-align: center; transition: width 0.3s; }
    .win-bar-b { background: #3b82f6; color: #fff; text-align: right; padding-right: 10px; transition: width 0.3s; }

    .table-responsive { overflow-x: auto; margin-top: 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
    th, td { padding: 8px 12px; border-bottom: 1px solid #202738; }
    th { background: #1a2030; color: #94a3b8; font-weight: 600; }
    tr:hover td { background: #1e2538; }

    .toast {
      position: fixed;
      bottom: 60px;
      right: 24px;
      padding: 12px 20px;
      background: #1e293b;
      color: #fff;
      border-radius: 8px;
      border: 1px solid #334155;
      box-shadow: 0 4px 16px rgba(0,0,0,0.4);
      z-index: 1000;
      font-size: 13px;
      font-weight: 600;
      display: none;
      align-items: center;
      gap: 8px;
    }
    .toast.show { display: flex; animation: fadeIn 0.2s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">✦</div>
      <div class="brand-text">
        <h1>IOM GYM <span style="font-weight: normal; font-size: 13px; color: var(--primary);">| Studio Cân Bằng & Custom Chỉ Số</span></h1>
        <p>Tinh chỉnh thanh trượt hiệu ứng và custom chỉ số từng bên (Đội A vs Đội B)</p>
      </div>
    </div>
    <div class="header-actions">
      <span id="diff-counter" class="badge-diff">0 chỉ số đã đổi</span>
      <button class="btn btn-secondary" onclick="copyCliCommand()" title="Sao chép câu lệnh --set">
        📋 Sao chép --set
      </button>
      <button class="btn btn-secondary" onclick="resetAllDefaults()" title="Đặt lại toàn bộ về cấu hình gốc">
        ↺ Khôi phục gốc
      </button>
      <button class="btn btn-primary" onclick="saveConfiguration()" title="Lưu trực tiếp vào config/rules.json">
        💾 Lưu Cấu Hình
      </button>
      <button class="btn btn-success" onclick="toggleSimPanel()" title="Mở phòng test mô phỏng trực tiếp">
        ⚔️ Test Nhanh & Custom
      </button>
    </div>
  </header>

  <!-- Filter & Tab Navigation -->
  <div class="filter-bar">
    <div class="category-tabs" id="category-tabs">
      <button class="tab-btn active" data-cat="all">Tất Cả</button>
      <button class="tab-btn" data-cat="amgar">🔥 Amgar (Hỏa)</button>
      <button class="tab-btn" data-cat="glacia">❄️ Glacia (Băng)</button>
      <button class="tab-btn" data-cat="cruor">🩸 Cruor (Huyết)</button>
      <button class="tab-btn" data-cat="ether">👁️ Ether (Hư Vô)</button>
      <button class="tab-btn" data-cat="gale">🌪️ Gale (Phong)</button>
      <button class="tab-btn" data-cat="fulgur">⚡ Fulgur (Lôi)</button>
      <button class="tab-btn" data-cat="sable">🌑 Sable (Ám)</button>
      <button class="tab-btn" data-cat="entropy">💥 Entropy (Hỗn Loạn)</button>
      <button class="tab-btn" data-cat="timeflow">⏳ TimeFlow (Thời Gian)</button>
      <button class="tab-btn" data-cat="agenet">🛡️ Agenet (Kim)</button>
      <button class="tab-btn" data-cat="elements">💧 Wet & Khắc Hệ</button>
      <button class="tab-btn" data-cat="combat">⚔️ Combat & Base</button>
    </div>
    <div class="filter-controls">
      <input type="text" id="search-input" class="search-input" placeholder="🔍 Tìm chỉ số / hiệu ứng...">
      <label class="toggle-label">
        <input type="checkbox" id="filter-modified-only">
        Chỉ hiện đã đổi
      </label>
    </div>
  </div>

  <!-- Sliders Container Grid -->
  <main>
    <div class="grid-container" id="sliders-grid">
      <!-- Cards populated dynamically -->
    </div>
  </main>

  <!-- Bottom Simulation & Custom Stats Drawer -->
  <div class="sim-panel" id="sim-panel">
    <div class="sim-header" onclick="toggleSimPanel()">
      <div class="sim-title">
        <span>⚔️ PHÒNG THÍ NGHIỆM CHIẾN ĐẤU & TÙY CHỈNH CHỈ SỐ TỪNG BÊN</span>
      </div>
      <div>
        <span style="font-size: 12px; color: var(--text-muted);">Bấm để ẩn / hiện bảng điều khiển ▲▼</span>
      </div>
    </div>

    <div class="sim-content">
      <!-- DUAL TEAMS CUSTOM STATS -->
      <div class="teams-grid">
        
        <!-- TEAM A COLUMN -->
        <div class="team-box team-a-box">
          <div class="team-box-header">
            <span class="team-title" style="color: var(--team-a);">🔴 ĐỘI A (Chiến Binh)</span>
            <div class="team-presets">
              <span style="font-size: 11px; color: var(--text-muted); line-height: 22px;">Preset:</span>
              <button class="btn-preset" onclick="applyPreset('a', 'default')">↺ Mặc định</button>
              <button class="btn-preset" onclick="applyPreset('a', 'dps_heavy')">⚔️ Dồn Dame</button>
              <button class="btn-preset" onclick="applyPreset('a', 'caster')">🧙 Pháp Sư</button>
              <button class="btn-preset" onclick="applyPreset('a', 'tank')">🛡️ Đỡ Đòn</button>
            </div>
          </div>

          <div style="display: flex; gap: 8px; align-items: center;">
            <label style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Chọn Build:</label>
            <select id="sim-team-a" class="select-box" style="flex: 1;" onchange="onTeamAChange()">
              <!-- Options populated via JS -->
            </select>
          </div>

          <!-- Team A Sliders -->
          <div class="team-stats-grid" id="team-a-stats-container">
            <!-- Populated via JS -->
          </div>
        </div>

        <!-- TEAM B COLUMN -->
        <div class="team-box team-b-box">
          <div class="team-box-header">
            <span class="team-title" style="color: var(--team-b);">🔵 ĐỘI B (Đối Thủ / Mục Tiêu)</span>
            <div class="team-presets">
              <span style="font-size: 11px; color: var(--text-muted); line-height: 22px;">Preset:</span>
              <button class="btn-preset" onclick="applyPreset('b', 'default')">↺ Mặc định</button>
              <button class="btn-preset" onclick="applyPreset('b', 'tank1k')">🛡️ Giáp 1,000</button>
              <button class="btn-preset" onclick="applyPreset('b', 'tank3k')">🏰 Tank 3,000</button>
              <button class="btn-preset" onclick="applyPreset('b', 'tank10k')">🏔️ Bức Tường 10k</button>
            </div>
          </div>

          <div style="display: flex; gap: 8px; align-items: center;">
            <label style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Chọn Đối Thủ:</label>
            <select id="sim-team-b" class="select-box" style="flex: 1;" onchange="onTeamBChange()">
              <!-- Options populated via JS -->
            </select>
          </div>

          <!-- Team B Sliders -->
          <div class="team-stats-grid" id="team-b-stats-container">
            <!-- Populated via JS -->
          </div>
        </div>

      </div>

      <!-- MATCH CONTROL BAR -->
      <div class="sim-match-bar">
        <div class="sim-bar-params">
          <div style="display: flex; align-items: center; gap: 6px;">
            <label style="font-size: 12px; color: var(--text-muted);">Chế độ:</label>
            <select id="sim-mode" class="select-box">
              <option value="fight">Fight (Đấu sinh tử - Đến khi chết)</option>
              <option value="dps">DPS (Đo sát thương - HP vô hạn)</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <label style="font-size: 12px; color: var(--text-muted);">Thời gian:</label>
            <input type="number" id="sim-time" class="text-input" style="width: 65px;" value="60" min="10" max="180">
            <span style="font-size: 12px; color: var(--text-muted);">giây</span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <label style="font-size: 12px; color: var(--text-muted);">Số trận:</label>
            <input type="number" id="sim-runs" class="text-input" style="width: 65px;" value="50" min="5" max="300">
          </div>
        </div>

        <button class="btn btn-primary" style="padding: 10px 24px; font-size: 14px;" onclick="runSimulation()">
          🚀 BẮT ĐẦU MÔ PHỎNG
        </button>
      </div>

      <!-- SIMULATION RESULTS -->
      <div id="sim-results" style="display: none;" class="results-card">
        <h3 id="res-headline" style="font-size: 15px; margin-bottom: 8px;">Kết Quả Trận Đấu</h3>
        <div class="win-bar-wrap" id="res-win-bar">
          <div class="win-bar-a" id="bar-a" style="width: 50%;">Đội A: 50%</div>
          <div class="win-bar-draw" id="bar-draw" style="width: 0%;">Hòa: 0%</div>
          <div class="win-bar-b" id="bar-b" style="width: 50%;">Đội B: 50%</div>
        </div>

        <div style="font-size: 13px; color: #cbd5e1; margin-bottom: 12px;" id="res-summary"></div>

        <h4 style="font-size: 13px; color: var(--primary); margin-top: 10px;">Thống Kê Sát Thương & Tác Động:</h4>
        <div class="table-responsive">
          <table id="res-damage-table">
            <thead>
              <tr>
                <th>Người</th>
                <th>Tổng Damage</th>
                <th>DPS</th>
                <th>Sát Thương Trực Tiếp</th>
                <th>Sát Thương DoT</th>
                <th>Sát Thương Chuẩn</th>
                <th>Hồi Máu</th>
                <th>Đỡ Đòn</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>

        <h4 style="font-size: 13px; color: #38bdf8; margin-top: 14px;">Tỉ Lệ Duy Trì Hiệu Ứng (Uptime):</h4>
        <div class="table-responsive">
          <table id="res-uptime-table">
            <thead>
              <tr>
                <th>Mục tiêu</th>
                <th>Frozen</th>
                <th>Freezing</th>
                <th>Drained</th>
                <th>Wet</th>
                <th>Choáng</th>
                <th>Làm Chậm (Max)</th>
                <th>Tầng Máu</th>
                <th>Tầng Vague</th>
                <th>Buff Bị Chặn</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>

      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    // State
    let metaList = [];
    let customStatsMeta = [];
    let currentRules = {};
    let baselineRules = {};
    let activeCategory = 'all';
    let buildsList = [];
    let dummiesList = [];
    let entityDefaults = {};

    let teamAStats = {};
    let teamBStats = {};

    function getVal(obj, path) {
      const parts = path.split('.');
      let curr = obj;
      for (const p of parts) {
        if (!curr || typeof curr !== 'object') return undefined;
        curr = curr[p];
      }
      return curr;
    }

    function setVal(obj, path, val) {
      const parts = path.split('.');
      let curr = obj;
      for (let i = 0; i < parts.length - 1; i++) {
        const p = parts[i];
        if (!curr[p] || typeof curr[p] !== 'object') curr[p] = {};
        curr = curr[p];
      }
      curr[parts[parts.length - 1]] = val;
    }

    function showToast(msg, isSuccess = true) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.borderColor = isSuccess ? '#10b981' : '#ef4444';
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2600);
    }

    async function init() {
      try {
        const res = await fetch('/api/data');
        const data = await res.json();
        metaList = data.sliders_meta;
        customStatsMeta = data.custom_stats_meta;
        currentRules = data.current_rules;
        baselineRules = data.baseline_rules;
        buildsList = data.builds;
        dummiesList = data.dummies;
        entityDefaults = data.entity_defaults || {};

        populateSimSelects();
        renderSliders();
        updateDiffBadge();
      } catch (e) {
        console.error('Lỗi tải dữ liệu ban đầu:', e);
      }
    }

    function populateSimSelects() {
      const selA = document.getElementById('sim-team-a');
      const selB = document.getElementById('sim-team-b');
      selA.innerHTML = '';
      selB.innerHTML = '';

      buildsList.forEach(b => {
        selA.add(new Option(`${b.label} (${b.id})`, b.id));
        selB.add(new Option(`${b.label} (${b.id})`, b.id));
      });

      dummiesList.forEach(d => {
        selB.add(new Option(`[Dummy] ${d.id} (${d.hp} HP / ${d.def} Def)`, 'dummy:' + d.id));
      });

      selA.value = 'amgar';
      selB.value = 'baseline';

      onTeamAChange();
      onTeamBChange();
    }

    function onTeamAChange() {
      const entId = document.getElementById('sim-team-a').value;
      const def = entityDefaults[entId] || { hp: 2000, atk: 200, defense: 300, mc: 0, pct_def_ignore: 0.05, flat_def_ignore: 50, damage_mult: 1.0, cdr: 0, guard_q: 0.35, res: 0 };
      teamAStats = JSON.parse(JSON.stringify(def));
      renderTeamSliders('a', teamAStats);
    }

    function onTeamBChange() {
      const entId = document.getElementById('sim-team-b').value;
      const def = entityDefaults[entId] || { hp: 2000, atk: 200, defense: 300, mc: 0, pct_def_ignore: 0.05, flat_def_ignore: 50, damage_mult: 1.0, cdr: 0, guard_q: 0.35, res: 0 };
      teamBStats = JSON.parse(JSON.stringify(def));
      renderTeamSliders('b', teamBStats);
    }

    function renderTeamSliders(team, statsObj) {
      const container = document.getElementById(`team-${team}-stats-container`);
      container.innerHTML = '';

      const color = team === 'a' ? 'var(--team-a)' : 'var(--team-b)';

      customStatsMeta.forEach(m => {
        const val = statsObj[m.key] ?? m.min;
        const row = document.createElement('div');
        row.className = 'team-stat-row';

        row.innerHTML = `
          <span class="team-stat-lbl" title="${m.desc}">${m.label}</span>
          <div class="range-wrap">
            <input type="range" 
              style="--thumb-color: ${color};"
              min="${m.min}" max="${m.max}" step="${m.step}" value="${val}"
              oninput="onTeamSliderMove('${team}', '${m.key}', this.value)">
          </div>
          <input type="number" 
            id="team-${team}-num-${m.key}" 
            class="team-stat-input"
            min="${m.min}" max="${m.max}" step="${m.step}" value="${val}"
            onchange="onTeamNumChange('${team}', '${m.key}', this.value)">
          <span style="font-size: 11px; color: #64748b; width: 32px;">${m.unit}</span>
        `;
        container.appendChild(row);
      });
    }

    function onTeamSliderMove(team, key, val) {
      const num = parseFloat(val);
      if (team === 'a') teamAStats[key] = num;
      else teamBStats[key] = num;

      const input = document.getElementById(`team-${team}-num-${key}`);
      if (input) input.value = num;
    }

    function onTeamNumChange(team, key, val) {
      const num = parseFloat(val);
      if (team === 'a') teamAStats[key] = num;
      else teamBStats[key] = num;

      const container = document.getElementById(`team-${team}-stats-container`);
      const row = Array.from(container.children).find(r => r.querySelector(`#team-${team}-num-${key}`));
      if (row) {
        const slider = row.querySelector('input[type=range]');
        if (slider) slider.value = num;
      }
    }

    function applyPreset(team, presetName) {
      let cur = team === 'a' ? teamAStats : teamBStats;
      const entId = document.getElementById(team === 'a' ? 'sim-team-a' : 'sim-team-b').value;
      const def = entityDefaults[entId] || { hp: 2000, atk: 200, defense: 300, mc: 0, pct_def_ignore: 0.05, flat_def_ignore: 50, damage_mult: 1.0, cdr: 0, guard_q: 0.35, res: 0 };

      if (presetName === 'default') {
        Object.assign(cur, JSON.parse(JSON.stringify(def)));
      } else if (presetName === 'dps_heavy') {
        cur.atk = 450;
        cur.hp = 1800;
        cur.damage_mult = 1.35;
        cur.pct_def_ignore = 0.20;
        cur.flat_def_ignore = 100;
      } else if (presetName === 'caster') {
        cur.atk = 240;
        cur.mc = 0.35;
        cur.cdr = 0.30;
      } else if (presetName === 'tank') {
        cur.hp = 8000;
        cur.defense = 1200;
        cur.guard_q = 0.60;
        cur.res = 0.15;
      } else if (presetName === 'tank1k') {
        cur.hp = 6000;
        cur.defense = 1000;
        cur.res = 0.10;
      } else if (presetName === 'tank3k') {
        cur.hp = 20000;
        cur.defense = 3000;
        cur.res = 0.25;
      } else if (presetName === 'tank10k') {
        cur.hp = 50000;
        cur.defense = 10000;
        cur.res = 0.40;
      }

      renderTeamSliders(team, cur);
      showToast(`Đã áp dụng preset cho ${team === 'a' ? 'Đội A' : 'Đội B'}!`);
    }

    // Effect Sliders
    function renderSliders() {
      const grid = document.getElementById('sliders-grid');
      grid.innerHTML = '';

      const query = document.getElementById('search-input').value.trim().toLowerCase();
      const modifiedOnly = document.getElementById('filter-modified-only').checked;

      const groups = {};
      metaList.forEach(item => {
        if (activeCategory !== 'all' && item.category !== activeCategory) return;

        const curVal = getVal(currentRules, item.path);
        const baseVal = getVal(baselineRules, item.path);
        const isModified = curVal !== undefined && baseVal !== undefined && Math.abs(curVal - baseVal) > 0.00001;

        if (modifiedOnly && !isModified) return;

        if (query) {
          const matchLabel = item.label.toLowerCase().includes(query);
          const matchPath = item.path.toLowerCase().includes(query);
          const matchDesc = item.desc.toLowerCase().includes(query);
          const matchCat = item.cat_name.toLowerCase().includes(query);
          if (!matchLabel && !matchPath && !matchDesc && !matchCat) return;
        }

        if (!groups[item.cat_name]) {
          groups[item.cat_name] = {
            name: item.cat_name,
            color: item.color,
            category: item.category,
            items: []
          };
        }
        groups[item.cat_name].items.push(item);
      });

      const catNames = Object.keys(groups);
      if (catNames.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #64748b; padding: 40px;">Không tìm thấy chỉ số phù hợp.</div>';
        return;
      }

      catNames.forEach(catKey => {
        const group = groups[catKey];
        const card = document.createElement('div');
        card.className = 'effect-card';

        let bodyHtml = '';
        group.items.forEach(item => {
          const curVal = getVal(currentRules, item.path) ?? item.min;
          const baseVal = getVal(baselineRules, item.path) ?? curVal;
          const isModified = Math.abs(curVal - baseVal) > 0.00001;

          let diffDisplay = '';
          if (isModified) {
            let changeSign = curVal > baseVal ? '+' : '';
            let pctChange = baseVal !== 0 ? (((curVal - baseVal) / baseVal) * 100).toFixed(0) : '';
            diffDisplay = `Gốc: ${formatVal(baseVal, item.format)} (${changeSign}${pctChange}%)`;
          }

          bodyHtml += `
            <div class="slider-row" id="row-${escapeId(item.path)}">
              <div class="slider-meta">
                <span class="slider-label">
                  ${item.label}
                  <span class="slider-path">${item.path}</span>
                </span>
                <span class="slider-diff-tag ${isModified ? 'changed' : ''}" id="diff-${escapeId(item.path)}">
                  ${diffDisplay}
                </span>
              </div>
              <div class="slider-controls">
                <div class="range-wrap">
                  <input type="range" 
                    id="slider-${escapeId(item.path)}"
                    style="--thumb-color: ${group.color};"
                    min="${item.min}" max="${item.max}" step="${item.step}" value="${curVal}"
                    oninput="onSliderMove('${item.path}', this.value)">
                </div>
                <input type="number" 
                  id="num-${escapeId(item.path)}"
                  class="input-box"
                  min="${item.min}" max="${item.max}" step="${item.step}" value="${curVal}"
                  onchange="onNumChange('${item.path}', this.value)">
                <span class="unit-text">${item.unit}</span>
                <button class="btn-reset-item" title="Đặt lại về gốc" onclick="resetSingleSlider('${item.path}')">↺</button>
              </div>
              <div class="slider-desc">${item.desc}</div>
            </div>
          `;
        });

        card.innerHTML = `
          <div class="card-header" style="border-top: 3px solid ${group.color};">
            <span class="card-title">${group.name}</span>
            <span class="card-badge">${group.items.length} chỉ số</span>
          </div>
          <div class="card-body">${bodyHtml}</div>
        `;
        grid.appendChild(card);
      });
    }

    function escapeId(path) { return path.replace(/\./g, '__'); }

    function formatVal(v, format) {
      if (format === 'percent') return (v * 100).toFixed(0) + '%';
      if (format === 'percent_fine') return (v * 100).toFixed(1) + '%';
      if (format === 'int') return Math.round(v);
      return Number(v).toFixed(2);
    }

    function onSliderMove(path, val) {
      const numVal = parseFloat(val);
      setVal(currentRules, path, numVal);
      const numInput = document.getElementById(`num-${escapeId(path)}`);
      if (numInput) numInput.value = numVal;
      updateSliderDiff(path);
      updateDiffBadge();
    }

    function onNumChange(path, val) {
      const numVal = parseFloat(val);
      setVal(currentRules, path, numVal);
      const slider = document.getElementById(`slider-${escapeId(path)}`);
      if (slider) slider.value = numVal;
      updateSliderDiff(path);
      updateDiffBadge();
    }

    function updateSliderDiff(path) {
      const item = metaList.find(m => m.path === path);
      if (!item) return;
      const curVal = getVal(currentRules, path);
      const baseVal = getVal(baselineRules, path);
      const diffTag = document.getElementById(`diff-${escapeId(path)}`);
      if (!diffTag) return;

      const isModified = Math.abs(curVal - baseVal) > 0.00001;
      if (isModified) {
        let changeSign = curVal > baseVal ? '+' : '';
        let pctChange = baseVal !== 0 ? (((curVal - baseVal) / baseVal) * 100).toFixed(0) : '';
        diffTag.innerText = `Gốc: ${formatVal(baseVal, item.format)} (${changeSign}${pctChange}%)`;
        diffTag.classList.add('changed');
      } else {
        diffTag.innerText = '';
        diffTag.classList.remove('changed');
      }
    }

    function resetSingleSlider(path) {
      const baseVal = getVal(baselineRules, path);
      if (baseVal === undefined) return;
      setVal(currentRules, path, baseVal);
      const slider = document.getElementById(`slider-${escapeId(path)}`);
      const numInput = document.getElementById(`num-${escapeId(path)}`);
      if (slider) slider.value = baseVal;
      if (numInput) numInput.value = baseVal;
      updateSliderDiff(path);
      updateDiffBadge();
      showToast(`Đã khôi phục ${path} về gốc: ${baseVal}`);
    }

    function resetAllDefaults() {
      if (!confirm('Đặt lại toàn bộ thanh trượt về cấu hình mặc định?')) return;
      currentRules = JSON.parse(JSON.stringify(baselineRules));
      renderSliders();
      updateDiffBadge();
      showToast('Đã khôi phục toàn bộ về mặc định!');
    }

    function updateDiffBadge() {
      let count = 0;
      metaList.forEach(m => {
        const cur = getVal(currentRules, m.path);
        const base = getVal(baselineRules, m.path);
        if (cur !== undefined && base !== undefined && Math.abs(cur - base) > 0.00001) count++;
      });
      const badge = document.getElementById('diff-counter');
      badge.innerText = `${count} chỉ số đã đổi`;
      if (count > 0) badge.classList.add('has-changes');
      else badge.classList.remove('has-changes');
    }

    async function saveConfiguration() {
      try {
        const res = await fetch('/api/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentRules)
        });
        const r = await res.json();
        if (r.ok) {
          showToast('✅ Đã lưu cấu hình vào config/rules.json!');
          baselineRules = JSON.parse(JSON.stringify(currentRules));
          renderSliders();
          updateDiffBadge();
        } else {
          showToast('❌ Lỗi khi lưu: ' + r.error, false);
        }
      } catch (e) {
        showToast('❌ Không thể kết nối tới server!', false);
      }
    }

    function copyCliCommand() {
      const sets = [];
      metaList.forEach(m => {
        const cur = getVal(currentRules, m.path);
        const base = getVal(baselineRules, m.path);
        if (cur !== undefined && base !== undefined && Math.abs(cur - base) > 0.00001) {
          sets.push(`--set ${m.path}=${cur}`);
        }
      });
      if (sets.length === 0) {
        showToast('Không có chỉ số nào khác với mặc định!');
        return;
      }
      navigator.clipboard.writeText(sets.join(' '));
      showToast(`Đã sao chép ${sets.length} tham số --set!`);
    }

    document.getElementById('category-tabs').addEventListener('click', (e) => {
      if (!e.target.classList.contains('tab-btn')) return;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeCategory = e.target.dataset.cat;
      renderSliders();
    });

    document.getElementById('search-input').addEventListener('input', () => renderSliders());
    document.getElementById('filter-modified-only').addEventListener('change', () => renderSliders());

    function toggleSimPanel() {
      document.getElementById('sim-panel').classList.toggle('open');
    }

    async function runSimulation() {
      const teamA = document.getElementById('sim-team-a').value;
      const teamB = document.getElementById('sim-team-b').value;
      const mode = document.getElementById('sim-mode').value;
      const time = parseFloat(document.getElementById('sim-time').value) || 60;
      const runs = parseInt(document.getElementById('sim-runs').value) || 50;

      showToast(`Đang mô phỏng ${runs} lượt (${teamA} vs ${teamB})...`);

      try {
        const res = await fetch('/api/run_sim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            team_a: teamA,
            team_b: teamB,
            mode: mode,
            time: time,
            runs: runs,
            rules: currentRules,
            custom_stats_a: teamAStats,
            custom_stats_b: teamBStats
          })
        });

        const data = await res.json();
        if (!data.ok) {
          showToast('❌ Lỗi mô phỏng: ' + data.error, false);
          return;
        }

        renderSimResults(data.result);
        showToast('✅ Đã hoàn thành mô phỏng!');
      } catch (e) {
        showToast('❌ Lỗi kết nối mô phỏng: ' + e.message, false);
      }
    }

    function renderSimResults(res) {
      const box = document.getElementById('sim-results');
      box.style.display = 'block';

      const barA = document.getElementById('bar-a');
      const barDraw = document.getElementById('bar-draw');
      const barB = document.getElementById('bar-b');

      barA.style.width = res.win_a_pct + '%';
      barA.innerText = `Đội A: ${res.win_a_pct}% (${res.wins_a})`;
      barDraw.style.width = res.win_draw_pct + '%';
      barDraw.innerText = res.win_draw_pct > 0 ? `Hòa: ${res.win_draw_pct}%` : '';
      barB.style.width = res.win_b_pct + '%';
      barB.innerText = `Đội B: ${res.win_b_pct}% (${res.wins_b})`;

      document.getElementById('res-headline').innerText = `Kết Quả: ${res.team_a} vs ${res.team_b} (${res.runs} trận, ${res.time}s, chế độ: ${res.mode.toUpperCase()})`;
      document.getElementById('res-summary').innerHTML = `
        Thời gian trận trung bình: <b>${res.avg_duration}s</b> | Damage trung bình Đội A: <b>${Math.round(res.dmg_a)}</b> | Damage trung bình Đội B: <b>${Math.round(res.dmg_b)}</b>
      `;

      const dmgTbody = document.querySelector('#res-damage-table tbody');
      dmgTbody.innerHTML = '';
      res.entities.forEach(ent => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${ent.name}</b> (${ent.team})</td>
          <td><b>${Math.round(ent.total_dmg)}</b></td>
          <td style="color: #38bdf8; font-weight: 700;">${Math.round(ent.dps)}</td>
          <td>${Math.round(ent.direct_dmg)}</td>
          <td>${Math.round(ent.dot_dmg)}</td>
          <td>${Math.round(ent.true_dmg)}</td>
          <td style="color: #10b981;">${Math.round(ent.healing)}</td>
          <td>${Math.round(ent.blocked_count)}</td>
        `;
        dmgTbody.appendChild(tr);
      });

      const upTbody = document.querySelector('#res-uptime-table tbody');
      upTbody.innerHTML = '';
      if (res.uptimes && res.uptimes.length > 0) {
        res.uptimes.forEach(u => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><b>${u[0]}</b></td><td>${u[1]}</td><td>${u[2]}</td><td>${u[3]}</td><td>${u[4]}</td>
            <td>${u[5]}</td><td>${u[6]}</td><td>${u[7]}</td><td>${u[8]}</td><td>${u[9]}</td>
          `;
          upTbody.appendChild(tr);
        });
      } else {
        upTbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #64748b;">Không có hiệu ứng đặc biệt tác động trong trận.</td></tr>';
      }
    }

    window.addEventListener('DOMContentLoaded', init);
  </script>
</body>
</html>
"""


class StudioHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path == "/api/data":
            cfg = load_cfg()
            builds = []
            entity_defaults = {}

            for bid, b in cfg["builds"].items():
                if not bid.startswith("_"):
                    builds.append({"id": bid, "label": b.get("label", bid)})
                    entity_defaults[bid] = get_entity_default_stats(cfg, bid)

            dummies = []
            for did, d in cfg["scenarios"]["dummies"].items():
                if not did.startswith("_"):
                    dummies.append({"id": did, "hp": d.get("hp", 0), "def": d.get("defense", 0)})
                    entity_defaults["dummy:" + did] = get_entity_default_stats(cfg, "dummy:" + did)

            data = {
                "sliders_meta": SLIDERS_META,
                "custom_stats_meta": CUSTOM_STATS_META,
                "current_rules": get_current_rules(),
                "baseline_rules": get_baseline_rules(),
                "builds": builds,
                "dummies": dummies,
                "entity_defaults": entity_defaults
            }
            res = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(res)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")

        if path == "/api/save":
            try:
                new_rules = json.loads(body)
                save_rules(new_rules)
                resp = json.dumps({"ok": True}).encode("utf-8")
            except Exception as e:
                resp = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(resp)
            return

        if path == "/api/run_sim":
            try:
                params = json.loads(body)
                spec_a = params["team_a"]
                spec_b = params["team_b"]
                mode = params.get("mode", "fight")
                T = float(params.get("time", 60.0))
                runs = int(params.get("runs", 50))
                rules_override = params.get("rules")
                custom_a = params.get("custom_stats_a")
                custom_b = params.get("custom_stats_b")

                cfg = load_cfg()
                if rules_override:
                    cfg["rules"] = rules_override

                # Xử lý custom stats cho Đội A
                actual_team_a = [spec_a]
                if custom_a:
                    custom_id_a = "custom_team_a"
                    if spec_a.startswith("dummy:"):
                        d = copy.deepcopy(cfg["scenarios"]["dummies"].get(spec_a[6:], {}))
                        d["hp"] = float(custom_a.get("hp", d.get("hp", 2000)))
                        d["defense"] = float(custom_a.get("defense", d.get("defense", 300)))
                        d["guard_q"] = float(custom_a.get("guard_q", d.get("guard_q", 0.0)))
                        if "res" in custom_a and float(custom_a["res"]) > 0:
                            d.setdefault("res", {})
                            d["res"]["*"] = float(custom_a["res"])
                        cfg["scenarios"]["dummies"][custom_id_a] = d
                        actual_team_a = ["dummy:" + custom_id_a]
                    else:
                        b = copy.deepcopy(cfg["builds"].get(spec_a, {}))
                        b["label"] = f"{b.get('label', spec_a)} (Custom A)"
                        b.setdefault("stats", {})
                        for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr", "stamina"]:
                            if k in custom_a:
                                b["stats"][k] = float(custom_a[k])
                        if "guard_q" in custom_a:
                            b["guard_q"] = float(custom_a["guard_q"])
                        if "res" in custom_a and float(custom_a["res"]) > 0:
                            b.setdefault("res", {})
                            b["res"]["*"] = float(custom_a["res"])
                        cfg["builds"][custom_id_a] = b
                        actual_team_a = [custom_id_a]

                # Xử lý custom stats cho Đội B
                if isinstance(spec_b, list):
                    actual_team_b = list(spec_b)
                elif custom_b:
                    custom_id_b = "custom_team_b"
                    if spec_b.startswith("dummy:"):
                        d = copy.deepcopy(cfg["scenarios"]["dummies"].get(spec_b[6:], {}))
                        d["hp"] = float(custom_b.get("hp", d.get("hp", 2000)))
                        d["defense"] = float(custom_b.get("defense", d.get("defense", 300)))
                        d["guard_q"] = float(custom_b.get("guard_q", d.get("guard_q", 0.0)))
                        if "res" in custom_b and float(custom_b["res"]) > 0:
                            d.setdefault("res", {})
                            d["res"]["*"] = float(custom_b["res"])
                        cfg["scenarios"]["dummies"][custom_id_b] = d
                        actual_team_b = ["dummy:" + custom_id_b]
                    else:
                        b = copy.deepcopy(cfg["builds"].get(spec_b, {}))
                        b["label"] = f"{b.get('label', spec_b)} (Custom B)"
                        b.setdefault("stats", {})
                        for k in ["hp", "atk", "defense", "mc", "pct_def_ignore", "flat_def_ignore", "damage_mult", "cdr", "stamina"]:
                            if k in custom_b:
                                b["stats"][k] = float(custom_b[k])
                        if "guard_q" in custom_b:
                            b["guard_q"] = float(custom_b["guard_q"])
                        if "res" in custom_b and float(custom_b["res"]) > 0:
                            b.setdefault("res", {})
                            b["res"]["*"] = float(custom_b["res"])
                        cfg["builds"][custom_id_b] = b
                        actual_team_b = [custom_id_b]

                A = resolve_team(cfg, actual_team_a, "A")
                B = resolve_team(cfg, actual_team_b, "B")
                soft_check(cfg, A + B)

                probe = Sim(cfg, A, B, infinite=(mode == "dps"), T=T, log=False).run()
                agg, logs = run_batch(cfg, A, B, mode=mode, T=T, runs=runs, seed=42)

                n = max(1, agg.n)
                avg_dur = sum(agg.t_end) / n
                win_a = agg.wins["A"]
                win_b = agg.wins["B"]
                win_draw = agg.wins[None]

                entities_stats = []
                for e in probe.ents:
                    total_dmg = agg.m[e.name]["damage"] / n
                    dur = avg_dur if mode == "fight" else T
                    dps = total_dmg / max(0.1, dur)
                    entities_stats.append({
                        "name": e.name,
                        "team": e.team,
                        "total_dmg": total_dmg,
                        "dps": dps,
                        "direct_dmg": agg.m[e.name]["direct_damage"] / n,
                        "dot_dmg": agg.m[e.name]["dot_damage"] / n,
                        "true_dmg": agg.m[e.name]["true_damage"] / n,
                        "healing": agg.m[e.name]["healed"] / n,
                        "blocked_count": agg.blocked[e.name] / n
                    })

                uptimes = uptime_rows(agg, probe)

                result_data = {
                    "ok": True,
                    "result": {
                        "team_a": spec_a,
                        "team_b": spec_b,
                        "mode": mode,
                        "time": T,
                        "runs": runs,
                        "wins_a": win_a,
                        "wins_b": win_b,
                        "wins_draw": win_draw,
                        "win_a_pct": round(100 * win_a / n, 1),
                        "win_b_pct": round(100 * win_b / n, 1),
                        "win_draw_pct": round(100 * win_draw / n, 1),
                        "avg_duration": round(avg_dur, 1),
                        "dmg_a": agg.dmg["A"] / n,
                        "dmg_b": agg.dmg["B"] / n,
                        "entities": entities_stats,
                        "uptimes": uptimes
                    }
                }
                resp = json.dumps(result_data, ensure_ascii=False).encode("utf-8")
            except Exception as e:
                resp = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(resp)
            return

        self.send_response(404)
        self.end_headers()


def start_server(port=5000, open_browser=True):
    socketserver.TCPServer.allow_reuse_address = True
    server = None
    for p in range(port, port + 20):
        try:
            server = socketserver.TCPServer(("", p), StudioHandler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print("Không thể mở cổng mạng cho giao diện.")
        return

    url = f"http://127.0.0.1:{port}"
    print("=" * 65)
    print(f"  ✦ IOM GYM BALANCE STUDIO - Giao diện thanh trượt hiệu ứng ✦")
    print(f"  Đang chạy tại: {url}")
    print("  Nhấn Ctrl+C để dừng server.")
    print("=" * 65)

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã đóng máy chủ giao diện.")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IOM Gym Slider UI")
    parser.add_argument("--port", type=int, default=5000, help="Cổng web (mặc định 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")
    parser.add_argument("--gui", action="store_true", help="Khởi động giao diện Tkinter desktop")
    args = parser.parse_args()

    if args.gui:
        import gui
        gui.main()
    else:
        start_server(port=args.port, open_browser=not args.no_browser)
