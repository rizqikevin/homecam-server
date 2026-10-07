# APP_FLOW

## Status dokumen

Dokumen ini memetakan perilaku yang terlihat dari source saat ini. Ini bukan laporan aplikasi yang sudah dijalankan. Tidak ada startup nyata, kamera nyata, atau cleanup nyata yang diverifikasi untuk penyusunan dokumen ini.

## Pohon root saat ini

```text
.git/                         VCS, bukan source aplikasi
.codegraph/                   indeks lokal codegraph
.omo/                         artefak sesi/continuation lokal
backend/                      source dan image build backend
frontend/                     source, dependency manifest, build image frontend
recordings/                   runtime mount, konfigurasi dan media rekaman
docker-compose.yml            orkestrasi dua container
.gitignore                    aturan file yang diabaikan
```

`.git`, `.codegraph`, dan `.omo` bukan batas runtime aplikasi. `recordings/` memuat `.gitkeep`, `.gitignore`, dan `settings.json`; file video diabaikan oleh root `.gitignore`. `frontend/src/assets/`, `frontend/public/icons/`, `frontend/public/manifest.webmanifest`, serta `frontend/public/favicon.svg` adalah asset source atau publik. `frontend/dist/`, `node_modules/`, `__pycache__/`, dan file video adalah hasil build, dependency, cache, atau runtime, bukan source utama.

Tidak ada root `package.json`, root `pnpm-lock.yaml`, atau root `package-lock.json`. Manifest dan lock berada di `frontend/`. Saat ini ada `frontend/package-lock.json` dan `frontend/pnpm-lock.yaml`. Keduanya belum diaudit konsistensi resolusi dependency. Versi package di bawah adalah rentang atau pin yang tertulis, bukan versi hasil resolve.

`frontend/nginx.conf` dipakai oleh image produksi untuk melayani UI dan proxy `/api/` pada port container `80`.

## Peta source utama

| Area | Path | Peran teramati |
|---|---|---|
| Entry frontend | `frontend/src/main.tsx` | Mount React dan registrasi service worker |
| Composition UI | `frontend/src/App.tsx` | Provider, router, route tree |
| API facade | `frontend/src/api.ts` | Tipe data dan panggilan API frontend |
| State facade | `frontend/src/context/AppContext.tsx` | Fetch awal, polling, settings mutation, PWA prompt |
| Shell | `frontend/src/components/Layout.tsx` | Layout route bersama |
| Halaman | `frontend/src/pages/Dashboard.tsx` | Dashboard |
| Halaman | `frontend/src/pages/Recordings.tsx` | Daftar atau aksi rekaman |
| Halaman | `frontend/src/pages/Settings.tsx` | Konfigurasi kamera, retention, PWA |
| Backend | `backend/app/main.py` | FastAPI, settings, camera, recording, cleanup |
| Test | `backend/tests/test_retention_cleanup.py` | Perilaku cleanup dengan dependency stub |

`frontend/src/index.css` adalah stylesheet utama yang diimpor oleh `frontend/src/main.tsx`. Asset runtime publik berada di `frontend/public/`; asset bundler berada di `frontend/src/assets/`. Detail isi vendor, media, dan hasil bundling tidak dianggap source behavior tanpa audit terpisah.

## Urutan startup aktual

### Deployment dan backend: image sampai serving

1. `frontend/Dockerfile` memakai Node 22 Alpine untuk `npm ci` dan `npm run build`, lalu Nginx pada port container `80`. Compose memetakan host `3005` ke `80`.
2. Backend memakai Python 3.11 dan Uvicorn pada port `8000`. Compose memetakan `127.0.0.1:8005` ke `8000`; akses browser memakai proxy frontend.
3. Saat Uvicorn mengimpor `backend/app/main.py`, modul memuat dependency dan definisi, membangun `app = FastAPI(..., lifespan=lifespan)` pada baris 560, kemudian mendaftarkan route melalui decorator pada baris 588 dan seterusnya. Import tidak sama dengan menjalankan lifespan.
4. `lifespan()` `backend/app/main.py:540-554` mengatur `_app_start_time`, log startup, memanggil `load_settings()`, memanggil `camera.start()`, lalu `start_retention_cleanup_worker()`, kemudian `yield` agar server melayani request.
5. `camera.start()` `backend/app/main.py:200-275` membaca settings lagi, menjalankan `cleanup_old_recordings()` pada boot, membuka kamera atau mock, mengatur status, dan memulai capture thread. Worker retention terpisah dijalankan setelah `camera.start()` oleh lifespan; intervalnya berasal dari `CLEANUP_INTERVAL_SECONDS` pada `backend/app/main.py:87-88`.
6. Saat shutdown setelah `yield`, `lifespan()` memanggil `stop_retention_cleanup_worker()` lalu `camera.stop()` pada `backend/app/main.py:551-554`.

### Frontend: HTML sampai render

1. `frontend/index.html:22-24` membuat `<div id="root"></div>` lalu memuat module `/src/main.tsx`.
2. `frontend/src/main.tsx:6-10` mencari `#root`, lalu merender `StrictMode` dan `App`.
3. `App` memasang `AuthProvider` dan memeriksa `/api/auth/session`. Tanpa sesi, hanya formulir login tampil; dashboard dan polling belum dipasang.
4. Setelah login, `AppProvider`, `BrowserRouter`, dan `Layout` dipasang. Route `/` membuka `Dashboard`, `/recordings` membuka `Recordings`, dan `/settings` membuka `Settings`. Logout atau respons API 401 melepas dashboard dan kembali ke formulir login.
5. Render pertama terjadi sebelum hasil network tersedia. `frontend/src/context/AppContext.tsx:43-55` mulai dengan data `null`, flag online `false`, `loading` `true`, dan `error` `null`.
6. Setelah mount, `AppProvider` memanggil `fetchStatus()` dan `loadInitialData()` dari `frontend/src/context/AppContext.tsx:116-125`. Status dipoll setiap 2 detik.
7. `fetchStatus()` mengambil health dan status kamera bersamaan melalui `api.getHealth()` dan `api.getCameraStatus()` pada `frontend/src/context/AppContext.tsx:84-109`. Sukses menetapkan backend online, status kamera, recording, dan motion. Gagal mengosongkan status server dan kamera, lalu menyimpan error.
8. `loadInitialData()` mengambil settings dan server info bersamaan melalui `frontend/src/context/AppContext.tsx:61-73`.
9. `Dashboard` dapat memulai dari state loading. State aktual mengikuti hasil request, bukan asumsi bahwa backend online, kamera online, atau recording aktif.
10. Setelah `window.load`, `frontend/src/main.tsx:12-23` mendaftarkan `/sw.js`. Registrasi ini terpisah dari render awal.

## Batas PWA

Service worker menyimpan shell saat install dan menghapus cache lama saat activate. Semua request `/api/` melewati cache, termasuk stream dan rekaman. Asset statis memakai cache-first; navigasi offline mencoba shell, tetapi login dan data kamera tetap memerlukan koneksi backend.

## Batas backend dan runtime

`backend/app/main.py:20-23` mengimpor FastAPI, response streaming, file response, dan model Pydantic. Ini import deklarasi, bukan instansiasi app. `app = FastAPI(...)` dibangun di `backend/app/main.py:560` dengan `lifespan=lifespan` yang mengatur urutan startup. `Settings` dan `SettingsPatch` berada di `backend/app/main.py:90-116`. `SETTINGS_PATH` adalah `/recordings/settings.json` pada `backend/app/main.py:87`; `load_settings()` dan `save_settings()` berada di `backend/app/main.py:118-138`.

`CameraManager` dimulai di `backend/app/main.py:164-260`. Objek ini menahan lifecycle capture, frame, motion, dan recording. Saat start, settings dibaca dan `cleanup_old_recordings()` dipanggil. Status internal yang terlihat di source mencakup `offline`, `online`, dan `error`; ini state backend aktual, bukan state UI tambahan.

Cleanup di `backend/app/main.py:143-159` hanya memproses ekstensi rekaman tertentu, melewati nama yang mengandung `_raw`, dan menghapus file yang lebih tua dari batas hari. Test `backend/tests/test_retention_cleanup.py` memakai `tempfile.TemporaryDirectory()` (filesystem sementara sesungguhnya), dependency stub untuk FastAPI/Pydantic/cv2/numpy agar modul bisa diimpor tanpa library asli, serta berisi assertion (`assertEqual`, `assertTrue`, `assertFalse`, `assertRaises`). Cakupan test mencakup cleanup file lama, skip `_raw`, validasi retention/FPS, rollback saat restart kamera gagal, dan urutan set MJPG sebelum resolusi. Test bukan bukti hardware nyata.

## Dependency, konfigurasi, dan deployment

Frontend dependencies di `frontend/package.json:12-29`: React `^19.2.6`, React DOM `^19.2.6`, React Router DOM `^7.16.0` (dependencies); TypeScript `~6.0.2`, Vite `^8.0.12`, dan devDependencies eslint lainnya. Scripts yang tersedia di `frontend/package.json:6-11`: `dev`, `build` (`tsc -b && vite build`), `lint`, `preview`. Tidak ada script `test` di frontend.

`frontend/tsconfig.app.json:2-22` tidak menyertakan flag `strict: true`. Flag lint individu (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`) aktif, tapi `strict` absent.

`frontend/src/api.ts` memakai `VITE_API_BASE_URL` bila diisi; default kosong memakai origin UI. Vite meneruskan `/api` ke `127.0.0.1:8005`; Nginx produksi meneruskan `/api/` ke backend. Semua fetch membawa cookie sesi. `backend/app/auth.py` memvalidasi sesi dan Origin untuk mutation; konfigurasi admin dan panduan HTTPS ada di `frontend/README.md`.

Backend dependencies di `backend/requirements.txt:1-3`: FastAPI `0.115.12`, Uvicorn `0.34.3`, `opencv-python-headless` `4.11.0.86` (pinned exact). FFmpeg dipasang oleh `backend/Dockerfile:3-12`.

`frontend/Dockerfile:9` menyalin `package-lock.json`; `frontend/pnpm-lock.yaml` juga ada. Keduanya belum diaudit konsistensi resolusi.

`recordings/.gitignore:1-3` berisi `*` lalu `!.gitkeep`, artinya Git mengabaikan semua isi `recordings/` kecuali `.gitkeep` — termasuk `settings.json`, video, dan file runtime apapun. Root `.gitignore:13-15` juga mengabaikan `recordings/*.mp4` dan `recordings/*.avi`, tapi `recordings/.gitignore` sudah lebih agresif dengan wildcard `*`.

## Batas audit

Audit ini membaca source, konfigurasi, manifest, lock path, dan path yang dirujuk. Audit tidak mengklaim pemeriksaan baris menyeluruh atas vendor atau dependency terpasang, media rekaman, isi VCS `.git`, database indeks `.codegraph`, atau artefak sesi `.omo`. Tidak ada klaim bahwa service berjalan. Tidak ada klaim bahwa kamera tersedia. Tidak ada klaim bahwa konfigurasi runtime aman untuk produksi.

`docker-compose.yml:7-10` menunjukkan privileged container dan mount `/dev` penuh, sehingga ini observasi batas keamanan, bukan hasil security audit penuh.
