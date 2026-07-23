# Docker Setup — dockerized-app

Flask + PostgreSQL, iki servisli, container'lastirilmis basit bir API.
Cilt 3 (Docker Mastery) cilt sonu projesi olarak hazirlanmistir.

## Mimari

  web (Flask, python app.py)  <-- app-network (bridge) -->  db (PostgreSQL 16-alpine)
  port 8000 (127.0.0.1)                                     named volume: db_data

## Neden Multi-stage Build?

Dockerfile iki asamadan olusur:
- **builder**: bagimliliklari (`pip wheel`) izole bir ortamda derler.
- **production**: sadece derlenmis wheel'leri ve uygulama kodunu alir; build araclari,
  pip cache'i, gereksiz katmanlar final image'e hic girmez.

Sonuc: final image ~275MB (postgres:16-alpine ise 411MB — resmi image bile bizimkinden
buyuk). Tek asamali bir Dockerfile yazsaydik muhtemelen 400MB+ olurdu.

## Neden Kullanici Tanimli Network?

Docker'in varsayilan bridge network'unde otomatik DNS cozumlemesi calismaz.
`app-network` (kullanici tanimli bridge) kullandigimiz icin `web` container'i,
`db` isminden IP'ye ihtiyac duymadan baglanabiliyor (`DB_HOST=db`).

## Neden `depends_on: condition: service_healthy`?

Sade `depends_on: - db` sadece container'in *baslatilmis* olmasini garanti eder,
PostgreSQL'in gercekten baglanti kabul etmeye hazir oldugunu garanti etmez
(PostgreSQL birkac saniye "warm-up" surecinden gecer). `service_healthy` kosulu,
`web`'in `db`'nin healthcheck'i (`pg_isready`) gercekten gecene kadar baslamamasini
sagliyor — "veritabanina baglanamadi" tarzi baslangic hatalarini onluyor.

## Guvenlik Sertlestirmesi ve Karsilasilan Zorluk

**web servisi:**
- `cap_drop: ALL` — hicbir Linux capability'sine ihtiyaci yok (1024 ustu bir port
  dinliyor, root yetkisi gerektirmiyor)
- `read_only: true` + `tmpfs: /tmp` — dosya sistemi salt-okunur, sadece gecici
  dosyalar icin `/tmp` RAM'de tutuluyor
- `security_opt: no-new-privileges:true` — process'in yetki yukseltmesi engelleniyor
- Dockerfile'da `USER appuser` — container root olarak calismiyor

**db servisi — karsilasilan zorluk:**
Ilk denemede `db` servisine de `cap_drop: ALL` uyguladik, ama container
`exited (1)` ile hemen coktu. Sebebi: PostgreSQL'in resmi entrypoint script'i,
ilk acilista veri dizininin sahipligini ayarlamak (`chown`) ve `postgres`
kullanicisina gecmek (`setuid`/`setgid`) icin belirli capability'lere ihtiyac
duyuyor. Kendi yazdigimiz basit uygulama kodu icin "tum yetkileri kaldir"
guvenle uygulanabilirken, resmi/hazir bir image'i ayni sekilde sertlestirmek
o image'in ic mantigini bozabiliyor. Cozum: `db` icin `cap_drop`'u kaldirip
sadece `no-new-privileges` ile biraktik.

## OOMKilled Testi (Debug Pratigi)

`web` image'i, bellek limiti kasitli olarak dusurulerek elle calistirildi:

    docker run -d --name oom-test --memory="20m" \
      --network dockerized-app_app-network \
      -e DB_HOST=db -e DB_PORT=5432 -e DB_NAME=appdb \
      -e DB_USER=appuser -e DB_PASSWORD=apppass \
      dockerized-app-web

Sonuc (`docker inspect oom-test`):

    "OOMKilled": true,
    "ExitCode": 137

`137 = 128 + 9 (SIGKILL)` — kernel, container'i bellek limitini astigi icin
oldurdu. `40MB` limitte container ayakta kaldi, `20MB`'da OOM oldu.

## Disk Kullanimi (`docker system df`)

| Tip            | Toplam | Boyut   | Geri kazanilabilir |
|----------------|--------|---------|---------------------|
| Images         | 3      | 686MB   | 87.5kB              |
| Containers     | 2      | 20.5kB  | 20.5kB              |
| Local Volumes  | 1      | 48.3MB  | 0B                  |
| Build Cache    | 17     | 299MB   | 23MB                |

## Karsilasilan Diger Bir Zorluk: cgroup/BPF Hatasi

Multipass VM uzerinde (ARM64, nested virtualization) `--memory` limitli bir
container ilk denemelerde su hatayla basarisiz oldu:

    failed to call BPF_PROG_ATTACH (BPF_CGROUP_DEVICE, BPF_F_ALLOW_MULTI):
    attach program: no such file or directory

Bu, uygulama/image ile ilgili degildi, VM'in cgroup2 durumuyla ilgili gecici
bir sorundu. `multipass restart devops-tutorial` ile VM'i yeniden baslatmak
sorunu cozdu.

## Build ve Calistirma Komutlari

    # Build + baslat
    docker compose up --build -d

    # Durumu kontrol et (her iki servis de "healthy" olmali)
    docker compose ps

    # Test
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/notes -H "Content-Type: application/json" -d '{"content": "test"}'
    curl http://localhost:8000/notes

    # Durdur
    docker compose down

    # Verilerle birlikte tamamen sil (dikkat, kalici veri kaybolur)
    docker compose down -v
