# SPECIFICATION

## Status dan batas

Dokumen ini adalah proposal fondasi. Belum disetujui, belum diterapkan, dan bukan klaim bahwa target architecture sudah ada. Fase pertama hanya boleh menambah struktur kosong setelah gate persetujuan di bawah. Tidak ada folder dibuat oleh pekerjaan ini.

Tujuan: memberi batas Clean Architecture yang kecil, menjaga perilaku HomeCam saat ini, dan menghentikan penambahan state, adapter, serta dependency tanpa bukti kebutuhan.

## Prinsip target

1. Domain tidak bergantung pada FastAPI, React, OpenCV, filesystem, FFmpeg, browser, atau library HTTP.
2. Application memegang use case dan port. Ia menerima dependency melalui port, bukan import framework.
3. Adapters menerjemahkan HTTP, OpenCV, filesystem, dan FFmpeg ke port application.
4. UI dan routes hanya mengurus presentasi, input, navigasi, dan composition root.
5. Backend tetap authoritative untuk health, camera, recording, motion, dan settings. Frontend tidak membuat sumber kebenaran kedua.
6. Perubahan kecil lebih aman daripada pemindahan besar. `frontend/src/api.ts` dan `frontend/src/context/AppContext.tsx` dipertahankan sebagai facade awal. Tidak ada pemindahan sekarang.

## Bentuk target yang diusulkan

Struktur berikut adalah proposal jangka panjang, bukan daftar file yang sudah ada:

```text
frontend/src/
  domain/
  application/
  adapters/http/
  components/
  context/
  pages/

backend/app/
  domain/
  application/
  adapters/
  routes/
  main.py
```

`main.py` tetap menjadi composition root sampai migrasi disetujui. Ia merakit settings, camera manager, use case, adapter, dan route. Jangan membuat `domain` berisi model kosong hanya untuk memenuhi diagram. Jangan membuat repository generik sebelum ada persistence use case yang membutuhkan kontrak itu.

## State model

### Backend authoritative state

Satu sumber kebenaran untuk health, status kamera, recording, motion, server info, dan settings berada di backend. Response API diparse di boundary. Status backend yang boleh direpresentasikan mengikuti data aktual, termasuk `offline`, `online`, dan `error` pada `CameraManager` di `backend/app/main.py:164-260`. Jangan menambah flag online independen yang bisa bertentangan dengan response terakhir.

### Server state dan UI state

Polling dan response server dipisahkan dari state UI lokal. Polling saat ini berada di `AppProvider`, `frontend/src/context/AppContext.tsx:84-125`, dengan interval 2 detik. Draft input, filter, modal, feedback, focus, dan state install PWA adalah state UI lokal atau browser. Draft tidak boleh menimpa settings authoritative sebelum mutation berhasil.

Login saat ini memakai satu akun admin dari environment dan sesi opaque dalam cookie HttpOnly. `AuthProvider` memeriksa sesi sebelum memasang `AppProvider`, sehingga polling dashboard tidak berjalan sebelum login. Respons API 401 melepas dashboard; logout mencabut sesi di backend. Panduan konfigurasi ada di `frontend/README.md`.

`Settings.tsx` sudah membedakan draft retention dari nilai tersimpan pada `frontend/src/pages/Settings.tsx:30-61` dan menunda penyimpanan 700 ms pada `frontend/src/pages/Settings.tsx:201-222`. Perubahan arsitektur harus mempertahankan batas itu sebelum ada characterization test.

Browser PWA state tetap terpisah dari server state. Service worker di `frontend/public/sw.js` mengurus cache shell dan cache-first asset. Semua request `/api/` melewati cache agar data privat tidak muncul setelah logout. Cache kosong bukan bukti backend offline, dan backend online bukan bukti kamera online.

TanStack Query dan Zustand belum terpasang. Keduanya opsional untuk fase berikutnya dan memerlukan persetujuan terpisah. Jangan menambahnya untuk mengganti Context tanpa masalah terukur.

## Kontrak publik saat ini (invarian yang ada)

Bagian ini mendokumentasikan kontrak API dan perilaku yang sudah ada di source. Ini fakta saat ini, bukan proposal. Parsing boundary yang disebut di bagian lain adalah proposal perbaikan, bukan perilaku existing.

### Routes backend

Berdasarkan `frontend/src/api.ts:115-145` dan `backend/app/main.py`:

| Endpoint | Method | Payload / Query | Respons |
|---|---|---|---|
| `/api/health` | GET | — | `HealthStatus` |
| `/api/camera/status` | GET | — | `CameraStatus` |
| `/api/camera/start` | POST | — | `{ message }` |
| `/api/camera/stop` | POST | — | `{ message }` |
| `/api/camera/stream` | GET | — | MJPEG `StreamingResponse` |
| `/api/settings` | GET | — | `SettingsData` |
| `/api/settings` | PATCH | `Partial<SettingsData>` JSON | `SettingsData` |
| `/api/recordings` | GET | — | `{ items, total }` |
| `/api/recordings/start` | POST | — | `{ message, filename }` |
| `/api/recordings/stop` | POST | — | `{ message, filename }` |
| `/api/recordings/{filename}` | GET | `?download=true` opsional | `FileResponse` |
| `/api/recordings/{filename}` | DELETE | — | `{ message, filename }` |
| `/api/server/info` | GET | — | `ServerInfo` |

### Port dan base URL

Backend container port `8000`, host loopback `8005`. Frontend container port `80`, host `3005`. Nginx produksi dan Vite development meneruskan `/api/` ke backend. `VITE_API_BASE_URL` default kosong agar cookie login, stream, dan download memakai origin yang sama.

### Persistence

Settings disimpan di `/recordings/settings.json` (`backend/app/main.py:87`). Rekaman video disimpan di direktori `recordings_dir` (default `/recordings`). Tidak ada database.

### Stream bypass

Service worker melewatkan `/api/camera/stream` sepenuhnya (`frontend/public/sw.js:44-47`); stream tidak pernah di-cache.

## Kontrak dan error

Semua input dari HTTP, file, browser, atau kamera diparse di boundary adapter — ini adalah target proposal, bukan perilaku existing. Saat ini `frontend/src/api.ts:14-43` melempar `Error` dari status HTTP tanpa parsing body; response JSON langsung dikembalikan sebagai tipe generik tanpa validasi runtime. Domain menerima nilai terstruktur yang sudah valid adalah tujuan, bukan kondisi saat ini. Error lintas boundary harus typed dan dapat dibedakan dari error jaringan, input, kamera, filesystem, dan FFmpeg. Jangan memakai `any` suppression, empty catch, atau catch yang mengubah kegagalan menjadi sukses.

Port harus kecil dan lahir dari use case nyata. Contoh kandidat masa depan: membaca status kamera, memperbarui settings, mengambil daftar rekaman, memulai atau menghentikan recording, dan menjalankan retention cleanup. Kandidat ini belum menjadi interface atau file sekarang.

## Anti-slop

- Bukti dulu. Setiap ekstraksi harus punya consumer nyata, characterization test, atau bug yang bisa direproduksi.
- Satu owner untuk setiap state. Hindari duplicate stores dan boolean yang menyalin response.
- Dependency minimal. Package baru memerlukan alasan, boundary, dan persetujuan.
- Strict typing adalah proposal konfigurasi berikutnya, bukan klaim bahwa flag strict sudah aktif. Verifikasi config sebelum menyebutnya aktif.
- Jangan menutup type error dengan `any`, assertion luas, atau suppression.
- Jangan memakai generic repository, service base class, barrel kosong, atau interface placeholder tanpa use case.
- Loading, empty, error, offline, dan partial data harus menjadi state eksplisit pada pekerjaan UI berikutnya.
- Untuk desain UI berikutnya, lakukan riset Appllama terlebih dahulu. Ikuti token konsisten, aksesibilitas, light dan dark mode, serta batas performa. Aturan native-specific mobile tidak berlaku untuk web PWA ini.
- Gunakan source lokal `skills/appllama-app-design-skill/SKILL.md` bila path itu tersedia. Path installed skill yang diketahui adalah `/Users/mymac/.agents/skills/appllama-app-design-skill/SKILL.md`. Keduanya referensi skill, bukan source aplikasi dan bukan klaim versi.

## Fase minimal yang diusulkan

### Fase 1, kosong dan dapat ditinjau

Setelah persetujuan eksplisit, tambah hanya direktori kosong berikut, memakai `.gitkeep` hanya bila Git perlu menyimpan direktori:

```text
frontend/src/domain/
frontend/src/application/
frontend/src/adapters/http/
backend/app/domain/
backend/app/application/
backend/app/adapters/
backend/app/routes/
```

Tidak ada runtime logic, model domain, port, adapter, route baru, dependency baru, atau pemindahan file pada fase ini. Tujuan fase hanya menguji nama batas dan menyiapkan tempat review.

### Fase 2, characterization sebelum migrasi

Tambahkan test yang mengunci perilaku saat ini sebelum mengekstrak modul. Backend retention tetap diuji dengan filesystem sementara dan fake hardware. Contoh cakupan: file tepat di batas umur, file lama terhapus, `_raw` dipertahankan, ekstensi tidak dikenal dipertahankan, dan kegagalan filesystem terlihat.

Test existing `backend/tests/test_retention_cleanup.py` memakai dependency stub dan assertion. Jangan menyebutnya stub-only tanpa assertion. Frontend belum memiliki test script di `frontend/package.json:6-11`; setup test memerlukan keputusan terpisah.

### Fase 3, migrasi satu seam per perubahan

Urutan kandidat: adapter filesystem retention, adapter HTTP frontend, lalu camera adapter. Setiap seam memerlukan consumer, kontrak typed, test happy path dan edge path yang berdekatan, serta rollback yang jelas. Jangan mengekstrak retention, HTTP, atau fake adapter sekarang. Hardware tetap opt-in. Jangan memberi production access ke retention tanpa persetujuan.

## Gate persetujuan

### Gate A: folder kosong (fase 1)

Direktori kosong boleh ditambah setelah pemilik proyek menyetujui:

1. nama dan batas direktori yang tercantum di fase 1;
2. apakah `.gitkeep` boleh ditambah.

Gate ini independen dari keputusan migrasi di bawah.

### Gate B: migrasi (fase 2 dan 3, terpisah dan setelah Gate A)

Sebelum mengekstrak seam atau menambah dependency, perlu persetujuan terpisah untuk:

3. seam pertama yang memiliki consumer nyata;
4. strategi characterization test dan environment hardware opt-in;
5. kebutuhan strict typing dan pilihan test frontend;
6. dependency baru, bila ada, beserta alasan dan lockfile yang menjadi sumber resmi.

Persetujuan gate tidak diasumsikan dari dokumen ini. Sampai gate disetujui, perubahan yang diizinkan hanya dokumentasi yang diminta.

## Risiko dan keterbatasan

`backend/app/main.py` saat ini menggabungkan API, settings, camera lifecycle, recording, cleanup, dan FFmpeg. Pemisahan dapat mengubah ordering startup atau error behavior. `docker-compose.yml:7-10` memakai privileged backend dan mount `/dev` penuh; ini observasi risiko, bukan security audit penuh.

Audit ini tidak mencakup pemeriksaan baris menyeluruh atas vendor, dependency terpasang, media, VCS, `.codegraph`, atau `.omo`. Tidak ada runtime QA dalam spesifikasi ini. Tidak ada klaim aplikasi sudah berjalan atau proposal sudah diterima.
