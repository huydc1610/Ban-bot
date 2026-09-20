# Deploy Ban-bot lên VPS Linux

Tài liệu này triển khai bot bằng Docker Compose trên Ubuntu/Debian. Docker sẽ tự khởi động lại container sau khi tiến trình bot lỗi hoặc VPS reboot (`restart: unless-stopped`). Bot không mở cổng HTTP, vì vậy không cần cấu hình domain, Nginx hoặc firewall inbound cho bot này.

## 1. Chuẩn bị VPS

Đăng nhập VPS bằng user có quyền `sudo`, rồi cài Docker Engine và Docker Compose plugin theo tài liệu Docker chính thức. Với Ubuntu, các lệnh sau là đủ:

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
sudo usermod -aG docker "$USER"
```

Đăng xuất rồi đăng nhập lại để group `docker` có hiệu lực. Kiểm tra:

```bash
docker compose version
docker run --rm hello-world
```

## 2. Lấy source và tạo cấu hình bí mật

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/mashiro161025/Ban-bot.git
cd Ban-bot
cp .env.example .env
chmod 600 .env
nano .env
```

Điền token vào `TOKEN`. Không gửi file `.env` qua Git, Discord, hoặc log. Nếu token từng bị lộ, hãy tạo token mới trong Discord Developer Portal trước khi deploy.

Rà soát `config.py` và thay các ID Discord cho đúng server của bạn. File này được mount read-only vào container và bot sẽ tự reload khi thay đổi.

## 3. Deploy lần đầu

```bash
bash scripts/deploy-vps.sh
docker compose logs -f ban-bot
```

Đợi log có `Logged in as ...` và thông báo đồng bộ slash command. Lệnh deploy sẽ dừng trước khi build nếu thiếu `.env`, Docker Compose không hợp lệ, hoặc Docker chưa được cài.

## 4. Cập nhật và rollback

Khi đã kiểm tra source mới:

```bash
git pull --ff-only
bash scripts/deploy-vps.sh
```

Nếu bản mới có lỗi, quay lại commit đã biết ổn định rồi chạy deploy lại:

```bash
git log --oneline -n 10
git checkout <commit-da-kiem-tra>
bash scripts/deploy-vps.sh
```

Sau khi xác nhận rollback, có thể tạo branch từ commit đó trước khi tiếp tục phát triển. Không dùng `git reset --hard` trên VPS vì có thể làm mất thay đổi cục bộ.

## 5. Vận hành

```bash
# Xem trạng thái và log
docker compose ps
docker compose logs --tail=200 ban-bot

# Restart sau khi đổi .env
docker compose restart ban-bot

# Dừng bot chủ động (restart policy sẽ không tự chạy lại khi Docker reboot)
docker compose down

# Chạy lại sau khi đã dừng
bash scripts/deploy-vps.sh
```

## 6. Sao lưu

`data/`, `config.py`, và `.env` là dữ liệu cần giữ lại. Sao lưu chúng ở vị trí an toàn, ngoài repository:

```bash
tar -czf "$HOME/ban-bot-backup-$(date +%Y%m%d-%H%M%S).tar.gz" data config.py .env
```

Khi restore, dừng bot, giải nén bản sao lưu vào thư mục project, rồi chạy `bash scripts/deploy-vps.sh`.

## 7. Kiểm tra Discord sau deploy

- Bật **Server Members Intent** và **Message Content Intent** trong Discord Developer Portal.
- Bot role phải cao hơn các role mà bot cần gán/gỡ và có các quyền quản lý role, channel, message tương ứng.
- Kiểm tra tối thiểu một slash command trong đúng server đã cấu hình. Container chạy không chứng minh bot có đủ quyền Discord.
