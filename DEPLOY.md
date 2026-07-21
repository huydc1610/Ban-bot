# Huong Dan Deploy Ban-bot Len VPS

Huong dan nay gia dinh VPS chay Ubuntu va da co quyen `sudo`.

## 1. Cai Docker va Docker Compose

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Neu VPS khong phai Ubuntu, cai Docker theo tai lieu chinh thuc cua distro do, mien la lenh `docker compose version` chay duoc.

## 2. Lay source len VPS

```bash
mkdir -p ~/projects
cd ~/projects
git clone <URL_REPO_CUA_BAN> Ban-bot
cd Ban-bot
```

Neu da clone repo roi:

```bash
cd ~/projects/Ban-bot
git pull
```

## 3. Tao file moi truong

Tao file `.env` tren VPS:

```bash
nano .env
chmod 600 .env
```

Noi dung toi thieu:

```env
TOKEN=DISCORD_BOT_TOKEN_CUA_BAN
```

Bot cung chap nhan bien `DISCORD_TOKEN`, nhung nen dung mot trong hai bien, khong can ca hai.

## 4. Kiem tra `config.py`

Mo `config.py` va sua cac ID cho dung server:

```bash
nano config.py
```

Nhung gia tri quan trong can dung:

- `MAIN_GUILD_ID`
- `TARGET_ROLE_ID`
- `TARGET_CATEGORY_ID`
- `NHAPKHO_ROLE_ID`
- `NHAPKHO_LOG_CHANNEL_ID`
- `ALLOWED_ROLE_IDS`
- `ALLOWED_USER_IDS`
- `AUTOBAN_CHANNEL_ID`

`docker-compose.yml` se mount `./config.py` vao container, nen sua `config.py` tren VPS xong bot co the hot reload khi co interaction moi. Neu thay doi bien trong `.env`, hay restart container.

## 5. Chay bot

```bash
mkdir -p data
docker compose up -d --build
```

Xem log:

```bash
docker compose logs -f ban-bot
```

Neu thanh cong, log se co dang:

```text
Logged in as <ten bot> (ID: <id>)
------ BAT DAU DONG BO LENH ------
```

## 6. Quan ly bot

Restart bot:

```bash
docker compose restart ban-bot
```

Dung bot:

```bash
docker compose down
```

Chay lai sau khi sua code:

```bash
git pull
docker compose up -d --build
```

Xem trang thai container:

```bash
docker compose ps
```

## 7. Backup va restore data

Bot luu data runtime trong thu muc `./data` tren VPS. Backup nhanh:

```bash
tar -czf ban-bot-data-backup-$(date +%Y%m%d-%H%M%S).tar.gz data config.py .env
```

Restore:

```bash
tar -xzf ban-bot-data-backup-YYYYMMDD-HHMMSS.tar.gz
docker compose up -d --build
```

## 8. Luu y quyen Discord

Trong Discord Developer Portal, bot can bat cac privileged intents phu hop voi code hien tai:

- Server Members Intent
- Message Content Intent

Bot role trong server can cao hon cac role ma bot se gan/go va can quyen quan ly role/channel/message theo cac lenh ban dang dung.
