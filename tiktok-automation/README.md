# TikTok Automation

Automation TikTok berbasis session: scrape daftar akun yang kamu **follow**, lalu
kirim satu stiker/emoji ke sebagian dari mereka — pelan, terbatas, dan bisa
dijalankan lewat GitHub Actions.

---

## Baca ini dulu

**Ini melanggar Terms of Service TikTok.** Automation browser dan DM otomatis
bukan penggunaan yang diizinkan. Risikonya nyata: shadowban, pembatasan DM,
sampai akun ditangguhkan permanen. Pakai akun yang kamu siap kehilangan, dan
jangan pakai ini untuk promosi massal ke orang yang tidak mengenalmu.

Yang **tidak** ada di project ini, dan sengaja:

| Tidak ada | Alasan |
|---|---|
| Login otomatis pakai username + password | Password tidak pernah masuk ke kode atau ke CI. Login manual sekali, yang disimpan cuma cookie. |
| Captcha solver / stealth fingerprint patching | Itu evasion terhadap sistem anti-bot, bukan automation. Kalau TikTok menahan traffic-nya, jawabannya melambat — bukan menyamar. |
| Blast ke seluruh following sekaligus | Ada cap per-run, jeda acak, dan cooldown. Tanpa itu ini cuma spam bot. |

Default-nya **dry-run**. Tidak ada satu pesan pun terkirim sampai kamu
menyalakan *dua* saklar: `DRY_RUN=false` **dan** `ALLOW_SEND=true`.

---

## Cara kerja

```
scripts/capture_session.py   kamu login manual di browser → storage_state.json
        │
        ▼
python -m tiktok_bot check    pastikan session masih hidup
        │
        ▼
python -m tiktok_bot scrape   ambil daftar following → out/following.json
        │
        ▼
python -m tiktok_bot send     filter → kirim stiker → catat di state/sent.json
```

Sebelum mengirim ke satu akun, `send` selalu memverifikasi ulang di halaman
profilnya bahwa kamu memang mem-follow akun itu. Kalau tombolnya masih
"Follow", akun tersebut dilewati.

---

## Setup lokal

```bash
cd tiktok-automation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium

cp .env.example .env         # isi TIKTOK_USERNAME
export PYTHONPATH=src
```

Ambil session — ini membuka jendela browser sungguhan, kamu yang login di sana:

```bash
python scripts/capture_session.py
python -m tiktok_bot check
```

Rehearsal (belum mengirim apa pun):

```bash
python -m tiktok_bot scrape --limit 50
python -m tiktok_bot send --only someone_you_know
```

Kirim beneran:

```bash
DRY_RUN=false ALLOW_SEND=true MAX_MESSAGES=3 \
  python -m tiktok_bot send --only someone_you_know
```

---

## Perintah

| Perintah | Fungsi |
|---|---|
| `check` | Verifikasi session masih login. Aman dijalankan kapan saja. |
| `scrape [--limit N]` | Kumpulkan daftar following → `out/following.json`. |
| `send [--only H...] [--rescrape]` | Kirim stiker ke akun yang lolos semua filter. |
| `status` | Tampilkan siapa saja yang sudah pernah dikirimi. |
| `encode-session [path]` | Cetak base64 dari file session, untuk ditempel ke GitHub Secret. |

---

## Konfigurasi

Semua lewat environment variable (lihat `.env.example`):

| Variabel | Default | Keterangan |
|---|---|---|
| `TIKTOK_USERNAME` | — | Handle kamu sendiri, tanpa `@`. |
| `TIKTOK_SESSION_FILE` | `storage_state.json` | Dipakai duluan kalau file-nya ada. |
| `TIKTOK_SESSION_B64` | — | Base64 dari file yang sama. Ini yang dipakai CI. |
| `DRY_RUN` | `true` | `false` = boleh mengirim. |
| `ALLOW_SEND` | `false` | Saklar kedua. Keduanya harus aktif. |
| `MAX_MESSAGES` | `5` | Batas keras jumlah pesan per run. |
| `MIN_DELAY_SECONDS` / `MAX_DELAY_SECONDS` | `45` / `120` | Jeda acak antar pengiriman. |
| `RESEND_COOLDOWN_DAYS` | `30` | Tidak mengirim ulang ke orang yang sama sebelum lewat. |
| `MESSAGE_MODE` | `emoji` | `emoji` mengetik karakter; `sticker` memilih dari panel stiker. |
| `STICKER_EMOJI` | `🎉` | Dipakai saat `MESSAGE_MODE=emoji`. |
| `STICKER_INDEX` | `0` | Item ke-berapa di panel, saat `MESSAGE_MODE=sticker`. |
| `HEADLESS` | `true` | `false` untuk melihat browsernya saat debugging. |

`config/skip_list.txt` — satu handle per baris, akun di situ tidak pernah
dikirimi meskipun kamu mem-follow mereka.

---

## GitHub Actions

Workflow ada di `.github/workflows/tiktok-automation.yml` (root repo, karena
GitHub hanya membaca workflow dari sana).

**Secrets & variables yang perlu diisi** — Settings → Secrets and variables → Actions:

| Nama | Tipe | Isi |
|---|---|---|
| `TIKTOK_SESSION_B64` | Secret | Output dari `python -m tiktok_bot encode-session` |
| `TIKTOK_USERNAME` | Variable | Handle kamu, tanpa `@` |

Menjalankannya: tab **Actions** → *TikTok Automation* → **Run workflow**. Isian
`allow_send` default `false`, jadi tombol Run tanpa mengubah apa pun cuma
rehearsal. Untuk benar-benar mengirim, set `allow_send: true`.

Jadwal mingguan yang ada di workflow **selalu dry-run** — tugasnya cuma
memberi tahu kalau session mati atau selector berubah. Perlu diingat GitHub
hanya menjalankan `schedule` dari default branch, jadi selama workflow ini
masih di branch fitur, yang jalan hanya `workflow_dispatch`.

Sent-log disimpan lewat `actions/cache` supaya cooldown tetap berlaku
antar-run. Cache GitHub terhapus setelah ~7 hari tanpa akses; kalau hilang,
cooldown ter-reset — jalankan `status` untuk mengeceknya.

---

## Kalau selector berubah

Gejalanya: `none of the selectors for 'x.y' matched`. TikTok tidak menjanjikan
DOM yang stabil, jadi ini akan terjadi.

Perbaikannya ada di `config/selectors.yml`, tanpa menyentuh Python: buka
halamannya di browser, inspect elemennya, tambahkan selector baru di **paling
atas** daftar untuk key tersebut. Setiap key menerima list, dan yang pertama
cocok yang dipakai — jadi selector lama boleh dibiarkan sebagai fallback.

Untuk debugging jalankan dengan `HEADLESS=false -v` supaya browsernya kelihatan.

---

## Keamanan session

`storage_state.json` setara dengan password kamu — siapa pun yang memegangnya
bisa bertindak sebagai kamu di TikTok.

- Sudah masuk `.gitignore`. Jangan pernah di-commit.
- Di GitHub simpan hanya sebagai **encrypted secret**, bukan variable.
- Logger menyensor `TIKTOK_SESSION_B64` kalau nilainya muncul di baris log.
- Kalau bocor: ganti password TikTok kamu — itu yang me-revoke semua session.

---

## Tes

```bash
python -m pytest
```

25 tes, tidak menyentuh jaringan: mengunci logika filter target, cooldown,
budget per-run, parsing session, dan aturan "dua saklar" sebelum mengirim.
