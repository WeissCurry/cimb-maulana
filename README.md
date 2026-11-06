# Daftar Tugas Harian

Aplikasi web pencatatan tugas harian internal bank menggunakan Flask 3 dan MySQL 8. Antarmuka menyatukan empat sudut pandang alur kerja (Papan Kanban 5 tahap, Daftar baris, Kalender tenggat bulanan, dan Bagan Gantt) dalam satu halaman dengan parameter `?view=`, form dialog modal `<dialog>`, Tailwind CSS v4, dan animasi GSAP 3.

Aset palet warna dan logo CIMB Niaga bersumber dari cimbniaga.co.id dan digunakan khusus untuk studi kasus penugasan MagangHub ini saja.

```text
cimb-maulana/
├── .env.example              Contoh konfigurasi variabel lingkungan
├── bin/
│   └── tailwindcss           Binary standalone Tailwind CSS v4 tanpa Node.js
├── JAWABAN_QA.md             Dokumentasi jawaban soal validasi API Postman
├── postman_collection.json   Koleksi uji Postman v2.1 untuk seluruh endpoint API
├── README.md                 Dokumentasi teknis proyek
├── requirements.txt          Daftar dependensi Python
├── schema.sql                Skema DDL MySQL 8 (tabel tasks dan task_events)
├── static/
│   ├── app.js                Logika interaksi dialog, tab view, GSAP, dan drag and drop
│   ├── brand/                Logo CIMB Niaga SVG
│   ├── favicon.ico           Ikon browser
│   ├── og-image.png          Pratinjau gambar Open Graph
│   ├── tailwind.css          CSS hasil kompilasi Tailwind v4
│   └── src/
│       ├── input.css         Source Tailwind CSS v4
│       └── views.css         Stylesheet untuk tampilan Daftar dan Gantt
├── templates/
│   ├── app.html              Halaman utama aplikasi
│   ├── base.html             Kerangka dasar HTML
│   ├── error.html            Halaman penanganan kesalahan HTTP 400, 404, dan 500
│   ├── components/
│   │   └── ui.html           Makro Jinja untuk button, chip, badge, field, dan move_form
│   ├── dialogs/
│   │   ├── create.html       Dialog modal form tambah tugas
│   │   └── task.html         Dialog modal detail, riwayat, form ubah, dan hapus
│   └── views/
│       ├── board.html        Tampilan Papan Kanban 5 kolom
│       ├── calendar.html     Tampilan Kalender bulanan dan agenda
│       ├── gantt.html        Tampilan visual rentang waktu Gantt
│       └── list.html         Tampilan tabel Daftar tugas
└── test_app.py               Pengujian otomatis pytest (95 test)
```

## Running it locally

1. Pastikan layanan MySQL Server 8 berjalan di komputer lokal. Buat database `todo_db` dan user `todo_user` dengan password `todo_pass`.
2. Siapkan virtual environment Python 3.12 (`.venv`), aktifkan, lalu pasang paket dependensi dari `requirements.txt`.
3. Salin file konfigurasi lingkungan dari `.env.example` menjadi `.env`. Pastikan `DATABASE_URL` mengarah ke database MySQL lokal.
4. Jalankan `schema.sql` untuk membuat tabel `tasks` dan `task_events`.
5. Kompilasi CSS bersifat opsional karena file `static/tailwind.css` sudah tersedia prebuilt. Jika Anda ingin mengubah styling, binary standalone CLI Tailwind CSS v4 tersedia di `bin/tailwindcss` tanpa memerlukan instalasi Node.js atau npm.
6. Jalankan server Flask pada port 5001. Port 5000 dihindari karena sering dipakai oleh AirPlay Receiver di macOS. Untuk mengisi data awal contoh tugas (14 tugas operasional dan riwayat tahapan), jalankan perintah `flask --app app seed --reset`.

## Quick Start

```bash
# 1. Konfigurasi database MySQL
mysql -u root -p -e "
CREATE DATABASE IF NOT EXISTS todo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'todo_user'@'localhost' IDENTIFIED BY 'todo_pass';
GRANT ALL PRIVILEGES ON todo_db.* TO 'todo_user'@'localhost';
FLUSH PRIVILEGES;
"

# 2. Siapkan venv dan pasang dependensi
cd cimb-maulana
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Salin konfigurasi environment
cp .env.example .env

# 4. Inisialisasi skema tabel database
mysql -u todo_user -p todo_db < schema.sql

# 5. Isi data awal contoh tugas (opsional, 14 tugas dengan riwayat status)
flask --app app seed --reset

# 6. Jalankan server aplikasi lokal pada port 5001
flask --app app run --debug --port 5001
```

Buka peramban di alamat `http://127.0.0.1:5001`.

## Available Scripts

| Command | Description |
|---|---|
| `source .venv/bin/activate` | Mengaktifkan virtual environment Python proyek |
| `flask --app app seed --reset` | Mengisi database dengan 14 contoh tugas operasional dan riwayat tahapan |
| `flask --app app run --debug --port 5001` | Menjalankan server aplikasi Flask mode debug pada port 5001 |
| `.venv/bin/python -m pytest -q` | Menjalankan seluruh pengujian otomatis pytest dengan SQLite in-memory |
| `./bin/tailwindcss -i static/src/input.css -o static/tailwind.css --minify` | Mengompilasi dan meminifikasi Tailwind CSS v4 menggunakan binary standalone tanpa Node.js |
| `./bin/tailwindcss -i static/src/input.css -o static/tailwind.css --watch` | Mengawasi perubahan file CSS dan template untuk kompilasi otomatis |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Ya | URL koneksi database MySQL (`mysql+pymysql://todo_user:todo_pass@127.0.0.1:3306/todo_db`) |
| `SECRET_KEY` | Ya | Kunci acak untuk keamanan sesi dan flash message Flask |
| `FLASK_DEBUG` | Tidak | Mengaktifkan mode debugger dan auto-reload kode (nilai: `1` atau `0`) |

## API Reference

Base URL endpoint API adalah `http://127.0.0.1:5001/api/tasks` dengan format data JSON.

| Method | Path | Deskripsi | Respons Sukses | Respons Error |
|---|---|---|---|---|
| GET | `/api/tasks` | Mengambil daftar tugas dengan filter opsional `status` dan `priority`. | 200 `{"data":[...], "count":n}` | 400 Bad Request |
| POST | `/api/tasks` | Membuat tugas baru. Mengembalikan header `Location: /api/tasks/<id>`. | 201 `{"data":task}` | 400 Bad Request |
| GET | `/api/tasks/<id>` | Mengambil rincian data satu tugas berdasarkan ID. | 200 `{"data":task}` | 404 Not Found |
| PUT | `/api/tasks/<id>` | Memperbarui atribut tugas secara parsial, termasuk status alur kerja. | 200 `{"data":task}` | 400 / 404 |
| POST | `/api/tasks/<id>/move` | Memindahkan tahapan status tugas dengan payload `{"status": key}`. | 200 `{"data":task}` | 400 / 404 |
| GET | `/api/tasks/<id>/history` | Mengambil riwayat transisi tahapan tugas terurut dari yang paling awal. | 200 `{"data":[...]}` | 404 Not Found |
| DELETE | `/api/tasks/<id>` | Menghapus data tugas dan riwayat transisinya. | 200 `{"message":"Tugas dihapus"}` | 404 Not Found |

Contoh payload POST `/api/tasks`:
```json
{
  "title": "Verifikasi dokumen pembukaan deposito nasabah",
  "description": "Pemeriksaan kelengkapan identitas dan otorisasi supervisor",
  "due_date": "2026-11-20",
  "priority": "high",
  "status": "todo"
}
```

Contoh respons POST `/api/tasks` (201 Created):
```json
{
  "data": {
    "id": 1,
    "title": "Verifikasi dokumen pembukaan deposito nasabah",
    "description": "Pemeriksaan kelengkapan identitas dan otorisasi supervisor",
    "due_date": "2026-11-20",
    "priority": "high",
    "status": "todo",
    "status_label": "Belum Mulai",
    "is_overdue": false,
    "created_at": "2026-11-06T10:00:00Z",
    "updated_at": "2026-11-06T10:00:00Z"
  }
}
```

Contoh payload POST `/api/tasks/1/move`:
```json
{
  "status": "in_progress"
}
```

Contoh respons GET `/api/tasks/1/history` (200 OK):
```json
{
  "data": [
    {
      "from_status": null,
      "to_status": "todo",
      "to_label": "Belum Mulai",
      "created_at": "2026-11-06T10:00:00Z"
    },
    {
      "from_status": "todo",
      "to_status": "in_progress",
      "to_label": "Dikerjakan",
      "created_at": "2026-11-06T10:15:00Z"
    }
  ]
}
```

Format respons error validasi (400 Bad Request):
```json
{
  "error": {
    "message": "Data tidak valid.",
    "fields": {
      "title": "Judul wajib diisi."
    }
  }
}
```

## Model Data

Aplikasi menggunakan dua tabel relasional pada MySQL 8:

| Kunci Status | Label UI | Keterangan Alur |
|---|---|---|
| `todo` | Belum Mulai | Tugas baru dibuat dan belum dikerjakan |
| `in_progress` | Dikerjakan | Tugas sedang dalam penanganan aktif |
| `ready` | Siap Dicek | Pengerjaan selesai dan siap diperiksa |
| `review` | Review | Proses pemeriksaan kelengkapan oleh supervisor |
| `done` | Selesai | Tugas disetujui dan tuntas |

Tabel `tasks`:
- Kolom: `id` (INT PK), `title` (VARCHAR 200), `description` (TEXT), `due_date` (DATE), `priority` (ENUM low, medium, high), `status` (ENUM 5 tahap), `created_at` (DATETIME UTC), `updated_at` (DATETIME UTC).
- Aturan: `Task.is_overdue` bernilai true jika `status != 'done'` dan `due_date < today` (Asia/Jakarta). `Task.to_dict()` menyertakan `status_label` dan timestamp ISO 8601 UTC dengan akhiran `Z`.

Tabel `task_events`:
- Kolom: `id` (INT PK), `task_id` (INT FK -> tasks.id ON DELETE CASCADE), `from_status` (ENUM 5 tahap, NULL saat buat tugas), `to_status` (ENUM 5 tahap), `created_at` (DATETIME UTC).
- Aturan: Pembuatan tugas mencatat 1 event awal (`from_status: null`). Setiap pemindahan status mencatat 1 event baru. Pemindahan ke status yang sama tidak mencatat event.

## Keputusan Desain dan Antarmuka (UI Notes)

Aplikasi berjalan dalam satu halaman (`app.html`) yang menampilkan empat sudut pandang tugas lewat parameter `?view=`:
- Kanban (`?view=board`): 5 kolom tahapan alur kerja dengan kartu tugas, tombol navigasi cepat Mundur/Lanjut, dan drag and drop HTML5.
- Daftar (`?view=list`): Tampilan baris data tabular pada layar desktop (>= 600px) dan kartu bertumpuk pada ponsel (< 600px).
- Kalender (`?view=calendar`): Kisi 7 kolom Senin sampai Minggu pada desktop dengan batas 3 tugas per hari, serta beralih ke daftar agenda pada ponsel (< 600px).
- Gantt (`?view=gantt`): Visualisasi horizontal rentang waktu pengerjaan tugas dari tanggal pembuatan hingga tenggat waktu, dengan batas rentang maksimal 45 hari.

Komponen pendukung:
- Dialog modal native HTML5 `<dialog>` digunakan untuk form tambah tugas (`create.html`) dan rincian tugas (`task.html`). Scroll halaman dikunci saat dialog terbuka menggunakan kelas `.is-locked`.
- Animasi GSAP 3 mencakup penekanan tombol (scale 0.97 selama 160ms), pembukaan dialog (fade in 220ms), dan pergantian view. Animasi dinonaktifkan otomatis jika sistem pengguna mengaktifkan `prefers-reduced-motion`.
- Seluruh tombol dibuat lewat makro Jinja di `templates/components/ui.html`. Tombol primer menggunakan warna merah `#D61E22` dengan rasio kontras 5.16:1 terhadap teks putih agar memenuhi standar WCAG AA (warna `#EC2428` bawaan memiliki rasio 4.33:1).
- Batasan sistem: Tanpa autentikasi pengguna (no auth) dan tanpa proteksi CSRF (no CSRF), sesuai instruksi penugasan internal.
