# Komponen Utama Validasi Response API pada Postman

Pertanyaan:
Dalam pengujian API menggunakan Postman, apa saja komponen utama yang Anda validasi pada response API?

Jawaban:

Saat menguji API menggunakan Postman, saya memvalidasi sembilan komponen utama pada setiap respons backend:

---

### 1. Status Code (Kode Status HTTP)

Saya memeriksa kode status HTTP untuk memastikan server merespons sesuai metode yang dikirim:
- Kode 200 OK untuk query data (GET), update data (PUT), pemindahan tahap (POST /move), dan hapus data (DELETE).
- Kode 201 Created saat membuat tugas baru (POST).
- Kode 400 Bad Request jika input kosong, filter salah, atau status tidak valid.
- Kode 404 Not Found jika ID tugas tidak ada di database.

Contoh pm.test:

```javascript
pm.test("Status code bernilai 200 OK", function () {
    pm.response.to.have.status(200);
});
```

---

### 2. Response Time (Waktu Respon)

Saya memvalidasi waktu pemrosesan server agar selalu berada di bawah batas 500 milidetik. Pengecekan ini mendeteksi kueri database yang lambat sejak awal.

Contoh pm.test:

```javascript
pm.test("Waktu respon kurang dari 500ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(500);
});
```

---

### 3. Response Headers (Header Respon)

Saya mengecek header untuk memastikan tipe konten dan rute entitas baru:
- Header `Content-Type` harus memuat `application/json`.
- Header `Location` harus ada pada status 201 Created dan mengarah ke URI tugas baru (`/api/tasks/<id>`).

Contoh pm.test:

```javascript
pm.test("Header Content-Type adalah application/json", function () {
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
});

pm.test("Header Location tersedia setelah pembuatan tugas", function () {
    if (pm.response.code === 201) {
        pm.response.to.have.header("Location");
        pm.expect(pm.response.headers.get("Location")).to.match(/^\/api\/tasks\/\d+$/);
    }
});
```

---

### 4. Body Structure dan Schema (Struktur dan Skema JSON)

Saya memvalidasi struktur JSON menggunakan `pm.response.to.have.jsonSchema`. Skema ini mengunci susunan properti tugas, enum 5 tahap Kanban, dan format waktu UTC berakhiran Z.

Contoh pm.test:

```javascript
pm.test("Payload respon memenuhi JSON schema tugas", function () {
    const schema = {
        type: "object",
        required: ["data"],
        properties: {
            data: {
                type: "object",
                required: [
                    "id",
                    "title",
                    "description",
                    "due_date",
                    "priority",
                    "status",
                    "status_label",
                    "is_overdue",
                    "created_at",
                    "updated_at"
                ],
                properties: {
                    id: { type: "integer" },
                    title: { type: "string" },
                    description: { type: ["string", "null"] },
                    due_date: { type: ["string", "null"] },
                    priority: { type: "string", enum: ["low", "medium", "high"] },
                    status: {
                        type: "string",
                        enum: ["todo", "in_progress", "ready", "review", "done"]
                    },
                    status_label: {
                        type: "string",
                        enum: ["Belum Mulai", "Dikerjakan", "Siap Dicek", "Review", "Selesai"]
                    },
                    is_overdue: { type: "boolean" },
                    created_at: { type: "string" },
                    updated_at: { type: "string" }
                }
            }
        }
    };
    pm.response.to.have.jsonSchema(schema);
});
```

---

### 5. Data Types and Values (Tipe Data dan Nilai Field)

Saya mengecek tipe data setiap field dan mencocokkan nilainya dengan batasan bisnis:
- Field `id` bertipe integer positif.
- Field `title` bertipe string tidak kosong (1 sampai 200 karakter).
- Field `priority` bernilai low, medium, atau high.
- Field `status` berisi salah satu dari 5 tahap alur kerja.
- Field `status_label` berisi teks bahasa Indonesia yang cocok.
- Waktu `created_at` dan `updated_at` diakhiri huruf Z.

Contoh pm.test:

```javascript
pm.test("Tipe data dan nilai field tugas valid", function () {
    const jsonData = pm.response.json();
    const task = jsonData.data;
    const validStages = ["todo", "in_progress", "ready", "review", "done"];
    const validLabels = ["Belum Mulai", "Dikerjakan", "Siap Dicek", "Review", "Selesai"];

    pm.expect(task.id).to.be.a("number");
    pm.expect(task.title).to.be.a("string").and.to.have.lengthOf.at.least(1);
    pm.expect(["low", "medium", "high"]).to.include(task.priority);
    pm.expect(validStages).to.include(task.status);
    pm.expect(validLabels).to.include(task.status_label);
    pm.expect(task.is_overdue).to.be.a("boolean");
    pm.expect(task.created_at).to.match(/Z$/);
    pm.expect(task.updated_at).to.match(/Z$/);
});
```

---

### 6. Business Rules (Aturan Bisnis dan Logika Aplikasi)

Saya memastikan logika backend berjalan benar:
- Flag `is_overdue` bernilai true jika status belum selesai (`status !== "done"`) dan tanggal tenggat lebih lampau dari hari ini. Jika tugas sudah selesai atau tanggal belum lewat, nilainya harus false.
- Riwayat `task_events` bertambah satu baris setiap kali status tugas dipindahkan.

Contoh pm.test:

```javascript
pm.test("Logika bisnis is_overdue sesuai aturan tenggat", function () {
    const jsonData = pm.response.json();
    const task = jsonData.data;
    const todayStr = new Date().toISOString().slice(0, 10);

    if (task.status !== "done" && task.due_date && task.due_date < todayStr) {
        pm.expect(task.is_overdue).to.be.true;
    } else {
        pm.expect(task.is_overdue).to.be.false;
    }
});
```

---

### 7. Error Handling and Messages (Penanganan Error dan Pesan Kesalahan)

Saya menguji kondisi gagal untuk memastikan server mengembalikan struktur error yang rapi:
- Judul kosong menghasilkan status 400 dengan pesan pada `error.fields.title`.
- Pindah ke status yang salah menghasilkan status 400 dengan pesan pada `error.fields.status`.
- ID yang tidak ada menghasilkan status 404 dengan pesan pada `error.message`.

Contoh pm.test:

```javascript
pm.test("Format error validasi status 400 terstruktur", function () {
    pm.response.to.have.status(400);
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property("error");
    pm.expect(jsonData.error.message).to.be.a("string");
    pm.expect(jsonData.error.fields).to.be.an("object");
    pm.expect(jsonData.error.fields).to.have.property("status");
});
```

---

### 8. Authentication and Cookies (Autentikasi dan Cookies)

Pada sistem dengan login, saya memverifikasi token dan cookie sesi. Pada API internal ini, batasan arsitektur memang tanpa autentikasi (no auth). Saya memastikan endpoint bisa diakses langsung tanpa header Authorization dan server tidak mengirimkan cookie sesi yang tidak perlu.

Contoh pm.test:

```javascript
pm.test("Endpoint publik dapat diakses tanpa token dan tanpa cookie", function () {
    pm.response.to.have.status(200);
    pm.expect(pm.response.headers.get("Set-Cookie")).to.be.undefined;
});
```

---

### 9. Consistency with Request (Konsistensi Data terhadap Permintaan)

Saya mencocokkan data respons dengan data yang dikirim pada body request:
- Nilai `title`, `description`, `due_date`, `priority`, dan `status` pada respons harus sama persis dengan payload request.
- Spasi di awal dan akhir string harus sudah dibersihkan oleh backend (trimmed).

Contoh pm.test:

```javascript
pm.test("Data respon konsisten dengan payload permintaan", function () {
    const requestPayload = JSON.parse(pm.request.body.raw);
    const task = pm.response.json().data;
    if (requestPayload.status) {
        pm.expect(task.status).to.eql(requestPayload.status.trim());
    }
});
```
