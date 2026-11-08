# FinalStars Gameplay Tool - IOM Gym (Interaction of Magic)

> Công cụ mô phỏng & phòng tập chiến đấu / cân bằng chỉ số (Gameplay Balance Simulator) cho dự án *Interaction of Magic* (FinalStars).

Mô tả một kịch bản (ai đấu với ai, skill/relic nào, số liệu nào đổi), chạy lệnh hoặc thao tác trên giao diện, xem và phân tích kết quả. Mỗi lần chạy tự lưu **file kết quả chi tiết** trong `results/` để phân tích và kiểm tra cân bằng.

Yêu cầu: **Python 3.8+** (sử dụng thư viện chuẩn của Python, không cần cài đặt thêm dependency).

---

## 1. Ứng dụng Desktop Windows & Web Studio

Nhấp đúp vào file `.bat` tương ứng hoặc chạy qua dòng lệnh:

- **Desktop App (Giao diện Desktop trực quan):**
  - Nhấp đúp file `runapp.bat` (chạy ngầm không hiện console CMD) hoặc `run_gui.bat`.
  - Hoặc qua terminal:
    ```bash
    pythonw app.pyw       # Mở trực tiếp app Windows (chạy ngầm không hiện CMD)
    python app.py         # Mở app từ terminal
    python gui.py         # Bản GUI desktop tiêu chuẩn
    ```
- **Web Studio (Giao diện Web tương tác với thanh trượt):**
  - Nhấp đúp file `run_ui.bat`.
  - Hoặc qua terminal:
    ```bash
    python ui.py          # Mở giao diện Web Studio trên trình duyệt
    ```

## 2. Chạy bằng dòng lệnh (CLI)

```bash
python gym.py list                                   # xem nhân vật / mục tiêu / relic / skill có sẵn
python gym.py run scenarios/01_duel_co_ban.json      # chạy một kịch bản có sẵn
python gym.py quick amgar baseline                   # chạy nhanh: A đấu B (nhiều người: a+b+c)
python gym.py new ten_kich_ban                       # tạo file kịch bản mẫu để tự sửa
```

Tùy chọn (dùng được với `run` và `quick`): `--runs 200` số lần chạy · `--time 60` thời gian · `--mode fight|dps` · `--set đường.dẫn=giá_trị` ghi đè tạm một số liệu · `--log 50` số dòng nhật ký in ra · `--no-save` không lưu file.

Ví dụ: `python gym.py quick ice_glacia+ice_aqua+ice_kim dummy:sandbag --mode dps --time 90 --set rules.combat.p_hit=1`

## 2. Kết quả cho bạn thấy gì

- **Kết quả chính:** chế độ `fight` cho tỉ lệ thắng và thời gian trận; chế độ `dps` cho damage hai đội và tỉ lệ A/B.
- **Damage theo người:** trực tiếp / DoT / true / thêm, DPS, hồi máu, damage nhận, số lần block.
- **Skill:** mỗi skill cast bao nhiêu lần, gây bao nhiêu damage.
- **Hiệu ứng:** tỉ lệ thời gian Frozen, Freezing, Drained, Wet, choáng, slow, số tầng Blood Loss/Vague, số buff bị chặn.
- **Diễn biến:** HP trung bình mỗi 5s (fight) hoặc damage tích lũy (dps).
- **Nhật ký trận mẫu:** từng đòn, trượt, block, đóng băng, hồi sinh, chết... của lần chạy #1 (file kết quả lưu đầy đủ).
- **So sánh biến thể:** nếu kịch bản có `variants`, có thêm bảng so sánh các biến thể cạnh nhau.

**Chế độ:** `fight` = đánh đến khi một đội chết (tối đa `time` giây). `dps` = mọi bên HP vô hạn, đo damage trong `time` giây (hợp để đo hiệu ứng và so sức mạnh).

## 3. Viết kịch bản (file JSON)

Chạy `python3 gym.py new ten` để có file mẫu đủ các phần. Các khóa bắt đầu bằng `_` là ghi chú, bị bỏ qua. Chỉ `team_a` và `team_b` là bắt buộc.

| Khóa | Ý nghĩa |
|---|---|
| `name`, `note` | Tên và mô tả (được lưu vào file kết quả) |
| `mode`, `time`, `runs`, `seed` | Chế độ, thời gian (giây), số lần chạy, hạt giống ngẫu nhiên |
| `team_a`, `team_b` | Danh sách người tham gia: tên nhân vật hoặc mục tiêu giả dạng `dummy:<tên>` |
| `fighters` | Định nghĩa nhân vật ngay trong file (xem dưới) |
| `skills_def`, `relics_def`, `dummies` | Định nghĩa skill / relic / mục tiêu mới ngay trong file |
| `set` | Ghi đè số liệu: `"rules.passives.molten_core.flat_ignore": 30` |
| `settings` | `petra_object_present` (bật Genesis), `chain_extra_targets` (mục tiêu ảo cho Fulgur Chain) |
| `variants` | Chạy lại cùng kịch bản với các thay đổi, rồi so sánh |

### Nhân vật (`fighters`)

```json
"fighters": {
  "hero": {
    "skills": ["Glacia_1", "Glacia_2", "Agenet_3", "Agenet_4"],
    "basic": "Glacia_rapid",
    "relics": ["relic_atk", "passive_chronomancy"],
    "stats": {"atk": 250, "hp": 2500},
    "res": {"Cruor": 0.2}
  }
}
```

- `skills`: đúng 4 skill. Hai skill đầu là **nhánh 1**, hai skill sau là **nhánh 2**. Magic của mỗi nhánh tự suy ra từ skill (hoặc ghi `"magics": ["Glacia", "Agenet"]`). Hai nhánh cùng magic thì thành PureType.
- `basic`: skill đánh thường. Bỏ trống thì tool tự lấy `<magic nhánh 1>_basic`; ghi `null` nếu không dùng basic.
- `relics`: danh sách relic/nội tại (xem mục 5). `stats`: ghi đè chỉ số gốc. `res`: kháng theo magic. `priority`: thứ tự ưu tiên cast (tùy chọn).
- Tool không bắt lỗi thiết kế (ví dụ basic khác magic nhánh 1, số relic nhiều): bạn tự do thử mọi thứ.

### Skill mới (`skills_def`)

```json
"skills_def": {
  "ice_lance": {
    "name": "Băng Thương", "magic": "Glacia", "tier": "Mid",
    "base": 220, "cd": 5, "charges": 1, "cast_time": 0.6,
    "hits": 1, "hit_interval": 0.2, "hit_chance": null, "true_base": 0,
    "effects": [{"type": "slow", "value": 0.3, "duration": 3.0}]
  }
}
```

Damage của skill thuộc magic nào sẽ tự kích hoạt hiệu ứng của magic đó (Glacia → Frigid Core, Aqua → Wet, Sable → Shadow Screep, Ether → Vague...). Damage thô = `(ATK + base) × damage_mult`, sau đó qua DefIgnore (% trước, flat sau), Defense, RES, khiên, HP. `hits: 0` nghĩa là skill thuần hỗ trợ (buff/hồi/khiên).

**Các loại `effects`** (mọi effect có thêm `"to": "self"|"enemy"`):

| type | tham số |
|---|---|
| `slow` | `value` (0.3 = 30%), `duration`, `name`, `max_stacks` |
| `stun` | `duration` |
| `dot` | `dps_base`, `atk_coef`, `duration`, `tick`, `magic` |
| `buff` / `debuff` | `stat`, `mode` (`add`/`pct`), `value`, `duration`, `group`, `name`, `max_stacks` (buff bị Drained chặn) |
| `heal` | `amount`, `pct_max` |
| `shield` | `amount`, `pct_max`, `duration` |
| `true_damage` | `amount`, `pct_max` |
| `cleanse`, `wet`, `lock_branch` | `cleanse` không cần tham số; `wet` và `lock_branch` dùng `duration` |

Các hiệu ứng này được nhân với MagicCapacity của người tạo ra chúng.

### Mục tiêu mới (`dummies`)

```json
"dummies": {"armored": {"kind": "player", "hp": 3500, "defense": 700, "res": {"Glacia": 0.25},
                        "in_exothermal": false, "wet": false}}
```
Dùng bằng `"dummy:armored"`. Mục tiêu giả đứng yên, không đánh trả. Vật thể ma thuật: `"kind": "object", "magic": "Agenet"` (Kim có hiệu ứng Sturd riêng).

## 4. Biến thể (`variants`): so sánh nhiều phương án một lần

```json
"variants": [
  {"name": "flat 30", "set": {"rules.passives.molten_core.flat_ignore": 30}},
  {"name": "tank Def 3000", "team_b": ["dummy:tank3000"]},
  {"name": "thêm relic", "fighters": {"hero": {"relics": ["relic_atk"]}}}
]
```
Mỗi biến thể là phần **ghi đè lên kịch bản gốc** (khóa nào cũng đổi được, các khóa dạng bảng được trộn). Kết quả có bảng so sánh: tỉ lệ thắng, thời gian, damage hai đội, tỉ lệ A/B và uptime hiệu ứng trên mục tiêu đầu tiên của đội B.

## 5. Số liệu có thể chỉnh (qua `set`, hoặc sửa trực tiếp `config/*.json`)

| Muốn chỉnh | Đường dẫn `set` | Ví dụ |
|---|---|---|
| Số liệu nội tại | `rules.passives.<tên>.<tham số>` | `rules.passives.frigid_core.frozen_immunity` = 6 |
| Chỉ số gốc / cap | `rules.stats_base.*`, `rules.stats_caps.*` | `rules.stats_caps.mc` = 0.3 |
| Giả định chiến đấu | `rules.combat.p_hit`, `guard_q`, `gcd`... | `rules.combat.p_hit` = 1 (đo "sạch", không trượt) |
| Một skill có sẵn | `skills.<id>.<trường>` | `skills.Glacia_1.base` = 150 |
| Một relic có sẵn | `relics.<id>.<trường>` | `relics.relic_atk.mods` = [...] |
| Số ô relic, magic có cấp nội tại không | `rules.passive_system.relic_slots`, `magic_grants_passive` | 2 / false |

**Nội tại:** `molten_core, zephyr_core, fulgur_chain, shadow_screep, frigid_core, vague_drain, blood_loss, eruptive_core, chronomancy, break`. Nội tại đến từ magic mang theo (nếu `magic_grants_passive` bật) và/hoặc relic có khóa `"grants"`. Bộ mẫu có sẵn relic `passive_<tên>` cho từng nội tại (ví dụ `passive_blood_loss`). Gỡ một nội tại để thử: `"passives_off": ["molten_core"]` trong nhân vật.

**Relic tự tạo:**
```json
"relics_def": {"my_relic": {"name": "VD", "grants": ["molten_core"],
   "mods": [{"stat": "atk", "mode": "add", "value": 100}],
   "triggers": [{"type": "periodic", "every": 12, "effects": [{"type": "shield", "to": "self", "pct_max": 0.1, "duration": 6}]}]}}
```
`stat` hợp lệ: `atk, hp, defense, mc, pct_def_ignore, flat_def_ignore, res_pen, damage_mult, cdr, cdr_nonbasic, stamina_cost_mult, speed_mult, heal_mult`. Mod `pct` cùng `group` thì cộng rồi nhân một lần; khác `group` thì nhân với nhau.

## 6. Gửi kết quả đi kiểm tra

Mỗi lần chạy tạo `results/<ngày-giờ>_<tên>.md`. File này chứa sẵn: kịch bản, bảng số liệu, nhật ký trận mẫu đầy đủ, và **toàn bộ cấu hình đã dùng** (nhân vật, skill, relic, mục tiêu, luật), nên người nhận tái lập được kết quả mà không cần hỏi thêm. Chỉ cần gửi file đó.

## 7. Lưu ý

- Mô phỏng không có vị trí/khoảng cách/né đòn: chỉ có xác suất trúng (`combat.p_hit`) và xác suất Guard (`combat.guard_q`). Đây là giả định, hãy ghi nó trong `note` khi bạn gửi kết quả.
- Kết quả đáng tin nhất ở mức **so sánh tương đối** giữa các biến thể. Tăng `runs` (200–500) khi cần chính xác.
- Skill `M_basic / M_1..M_4` trong bộ mẫu chỉ là số giả định để thử; hãy tự định nghĩa skill thật trong `skills_def` hoặc `config/skills.json`.
- `engine.py` không cần sửa.
