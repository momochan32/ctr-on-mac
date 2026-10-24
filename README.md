# CTR-Online on Mac (By Momochan32)

**Crash Team Racing: Nitro-Fueled berjalan native di macOS (Apple Silicon), lengkap dengan mode online RyuNET, layar ultrawide 21:9, dan launcher berbahasa Indonesia.**

Ini fork pribadi dari [SacredFire / OCTR](https://github.com/T3CHNOLOG1C/SacredFire), port PC native CTR-NF yang dibuat komunitas. Semua yang ada di sini berdiri di atas karya mereka (lihat [Kredit](#kredit--terima-kasih)). Fork ini menambahkan dukungan macOS: runtime, GPU, launcher, dan paket aplikasinya.

![Balapan online di monitor ultrawide 21:9](docs/macos/online-race-ultrawide.jpg)

---

## Tampilan

| Ultrawide 21:9 (2560×1080) | MacBook Pro (fullscreen 2560×1440) |
|---|---|
| ![Ultrawide race](docs/macos/race-ultrawide-21x9.jpg) | ![MacBook race](docs/macos/race-macbook-1440p.jpg) |
| ![Ultrawide intro](docs/macos/intro-ultrawide-21x9.jpg) | ![MacBook race 66 FPS](docs/macos/race-macbook-66fps.jpg) |

| Online: memuat balapan (FPS + ping ke pemain lain) | Online: balapan dengan pemain lain (61 FPS) |
|---|---|
| ![Online loading](docs/macos/online-loading-ping.jpg) | ![Online race](docs/macos/online-race-ultrawide.jpg) |

| Lobby online | Pilih kart |
|---|---|
| ![Online lobby](docs/macos/online-lobby.jpg) | ![Kart select](docs/macos/kart-select.jpg) |

| Launcher (Bahasa Indonesia) | Pencapaian |
|---|---|
| ![Launcher](docs/macos/launcher-settings.jpg) | ![Launcher trophies](docs/macos/launcher-trophies.jpg) |

---

## Hasil di MacBook Pro M3 Max

| Skenario | FPS saat balapan |
|---|---|
| Monitor ultrawide 2560×1080 (75 Hz), layout 21:9 | **75 (batas monitor)** |
| Balapan **online** di ultrawide | ~61 |
| Layar MacBook, mode PS4 Pro + FSR 3.1 AA | ~63–70 |

Fitur yang jalan: grafis 3D lengkap (termasuk bulu karakter), patch 60 FPS, tanpa motion blur, Unlock Everything, mode PS4 Pro, FSR 3.1 (anti-aliasing dan upscaling), layout 21:9 dengan HUD di tengah, online RyuNET (lobby, matchmaking, balapan dengan pemain lain), DualSense / kontroler, save, dan pencapaian.

---

## Instalasi

### 1. Yang dibutuhkan

- Mac **Apple Silicon** (M1 atau lebih baru), macOS 14 ke atas
- **Rosetta 2**: `softwareupdate --install-rosetta --agree-to-license`
- **Homebrew** ([brew.sh](https://brew.sh)), lalu:
  ```sh
  brew install bash python gtk4 libadwaita pygobject3 adwaita-icon-theme
  ```
- **Dump game kamu sendiri**: CTR Nitro-Fueled **CUSA13795 versi 1.21** (base + update 1.21 digabung, berisi `eboot.bin`). File game **tidak** disertakan.

### 2. Pasang aplikasinya

1. Buka **`CTR-Online on Mac.dmg`**.
2. Seret **CTR-Online on Mac** ke folder **Applications**.
3. Buka aplikasinya. Kalau macOS memperingatkan "aplikasi dari developer tidak dikenal": klik kanan → **Open** → **Open**.

Kalau ada komponen yang belum terpasang, aplikasi akan menampilkan perintah `brew` yang perlu dijalankan.

### 3. Pertama kali jalan

1. Di **Pengaturan → Game**, pilih folder game (yang berisi `eboot.bin`).
2. (Opsional) **Online (RyuNET)**: nyalakan **Main online** dan isi nickname kamu (3–16 karakter).
3. Tekan **Main**. Start pertama menyiapkan shader untuk GPU kamu (sekitar 2 menit). Start berikutnya langsung masuk.

Pengaturan, save, dan file hasil olahan disimpan di `~/Library/Application Support/CTR-Online`.

---

## Kontrol

| Aksi | Tombol |
|---|---|
| Menu pengaturan di dalam game | **Shift + W** (atau F1 / Insert, atau L3+R3 di kontroler) |
| Main / berhenti | Tombol **Main** dan **Stop** di launcher |

DualSense dan kontroler lain langsung terdeteksi.

---

## Pengaturan default (sudah dites di M3 Max)

| Pengaturan | Nilai | Alasan |
|---|---|---|
| Mode PS4 Pro | Aktif | Grafis lebih detail, FPS sama |
| Anti-aliasing | FSR 3.1 | Pengganti MSAA |
| MSAA | **Mati, tidak tersedia** | Driver Vulkan di Mac menggambar scene MSAA game ini hitam |
| Patch | 60 FPS, tanpa motion blur, Pro 1080p, Unlock Everything | |
| Presentasi | FIFO (VSync) | Satu-satunya mode di Metal |
| Batas FPS | 240 (dibatasi refresh rate layar) | |

Catatan:
- Layout **21:9** memakai jalur render biasa, jadi mode Pro otomatis mati saat layout ini aktif. Di layar 16:9 mode Pro aktif lagi.
- Layar MacBook (16:10) menampilkan bar hitam tipis di atas dan bawah, karena game ini 16:9.
- Setelah restart Mac, kalau online gagal dan kamu memakai VPN, pastikan VPN tidak memblokir UDP ke server game.

---

## Cara kerjanya di Mac (ringkas, teknis)

Kode game PS4 (x86-64) dijalankan langsung lewat **Rosetta 2**. Grafis PS4 diterjemahkan ke Vulkan, lalu ke Metal lewat **Mesa KosmicKrisp**. Perubahan utama dari versi Linux:

- **TLS / data thread game**: TCB guest disimpan di slot `pthread` macOS (`gs:[8*key]`), mengikuti trik port Windows.
- **Jendela**: Cocoa wajib di main thread, jadi kode game dipindah ke thread kedua.
- **Memori**: Apple Silicon memakai rentang 64–448 GB untuk GPU, jadi memori PS4 digeser ke `0x7000000000` ke atas. Page fault pelacakan GPU datang sebagai `SIGBUS`.
- **Memori bersama GPU**: memori game diimpor ke Vulkan lewat `VK_EXT_external_memory_host`, tanpa salinan.
- **Performa**: "GPU breadcrumbs" (penanda per draw) dimatikan di Mac karena memaksa GPU bekerja serial. FPS naik ~30%. Ditambah 6 thread perekam dan 2 frame di depan.
- **FSR 3.1**: fallback tipe memori untuk unified memory Apple.
- **Restart dari game**: `posix_spawn` dengan `SETEXEC`.

---

## Build dari source

```sh
git clone --recursive <repo> && cd octr-src
git checkout macos-port
# dependensi library diambil dari checkout shadPS4 (SHADPS4_EXTERNALS) dan Vulkan loader + KosmicKrisp
cmake -S gpu -B out/gpu-mac -G Ninja -DCMAKE_OSX_ARCHITECTURES=x86_64 -DBB_LTO=OFF
ninja -C out/gpu-mac sacredfire bb-gpu-capabilities
./packaging/macos/make_dmg.sh        # -> out/CTR-Online on Mac.dmg
```

Untuk pengembangan: `./play-octr-mac.command` (langsung jalan) dan `./play-octr-launcher.command` (launcher).

---

## Kredit & terima kasih

Fork ini tidak akan ada tanpa komunitas berikut:

- **SacredFire / OCTR**: T3CHNOLOG1C, Ryu7w7. Port PC native dan online RyuNET yang menjadi dasar fork ini.
- **CTR-NitroFueled-PC**: GetLostIn. Riset port PC: perbaikan MSAA, bulu karakter, dan rendering.
- **bbport**: desain runtime PS4 native tempat port ini berawal.
- **Tim shadPS4**: inti grafis PS4 dan shader recompiler.
- **Mesa KosmicKrisp**: driver Vulkan di atas Metal yang membuat versi Mac ini mungkin.
- **tcosi**: layout 21:9 dan 32:9 (menu, background, HUD).
- **illusion** (PS-Game-Patch): patch 60 FPS dan motion blur.
- **TroyWarez**: patch resolusi PS4 Pro 1080p.
- **Camiloop**: patch Unlock Everything.
- **AMD FidelityFX**: FSR 3.1.
- **Komunitas Crash Team Racing**: para pemain, tester, dan semua yang menjaga mode online tetap hidup.

## Catatan legal

Proyek komunitas non-komersial untuk pemakaian pribadi. Tidak berafiliasi dengan Activision, Beenox, atau Sony. Tidak ada file game yang disertakan: gunakan dump dari salinan game milikmu sendiri. Lisensi mengikuti proyek asal (GPL-2.0-or-later).

> README asli proyek SacredFire / OCTR: [README-SacredFire.md](README-SacredFire.md)
