# Spec: Cog nhập emoji từ server khác

## Objective

Thêm slash command `/emoji` để một thành viên dán một hoặc nhiều custom
emoji Discord theo cú pháp `<:ten:id>` hoặc `<a:ten:id>`. Bot tạo **một tin
nhắn preview riêng cho từng emoji**, gồm ảnh preview và nút `Upload emoji`.
Khi người gọi bấm nút, bot tải emoji từ Discord CDN rồi tạo emoji đó trong
server đang chạy lệnh.

Mục tiêu là cho phép chọn từng emoji trong một danh sách mà không tự động
upload cả danh sách.

## Tech Stack

- Python với `discord.py` (đang có trong `requirements.txt`).
- Một cog mới dưới `cogs/` và các `discord.ui.View` tạm thời cho nút upload.
- Discord CDN tại `https://cdn.discordapp.com/emojis/{emoji_id}.{png|gif}`.

## Commands

```powershell
python -m unittest
python index.py
```

Lệnh Discord dự kiến:

```
/emoji emojis:<:cat:123...> <a:dance:456...>
```

## Project Structure

```
cogs/emoji.py                     -> Cog, parser emoji, preview và upload button
index.py                           -> Thêm extension cog mới vào INITIAL_COGS
tests/test_emoji_import.py         -> Unit tests parser, quyền button và URL CDN
docs/specs/emoji_import_cog.md     -> Đặc tả này
```

## Code Style

Giữ kiểu cog hiện tại: slash command có `@app_commands.guilds(config.MAIN_GUILD_ID)`,
phản hồi interaction trước mọi I/O mạng, và trả lỗi bằng tin nhắn ephemeral.

```python
@app_commands.command(name="emoji", description="Lấy emoji custom vào server.")
async def emoji(self, interaction: discord.Interaction, emojis: str):
    await interaction.response.defer(ephemeral=True)
    for emoji in parse_custom_emojis(emojis):
        await interaction.followup.send(embed=preview_embed(emoji), view=EmojiUploadView(...), ephemeral=True)
```

## Testing Strategy

- `unittest` cho parser: emoji tĩnh, animated emoji, nhiều emoji, input không hợp lệ
  và emoji ID bị lặp.
- Unit test URL CDN dùng `.gif` với emoji animated, `.png` với emoji tĩnh.
- Unit test kiểm tra người không phải người gọi không thể bấm nút.
- Kiểm tra thủ công trên Discord: bot và người dùng có quyền cần thiết; thử upload
  một emoji tĩnh, một animated emoji và trường hợp hết slot emoji.

## Boundaries

- Always: chỉ xử lý custom emoji hợp lệ; defer interaction trước khi tải CDN; kiểm
  tra server, quyền và lỗi Discord; mỗi emoji gửi đúng một preview/button riêng.
- Ask first: thêm dependency HTTP mới, thay đổi config hiện có, thay đổi quyền hoặc
  hành vi của các cog khác.
- Never: tự động upload mọi emoji, cho người khác bấm nút upload, ghi token/secret,
  hoặc sửa emoji có sẵn để ghi đè.

## Success Criteria

1. `/emoji` nhận một hay nhiều chuỗi `<:name:id>` hoặc `<a:name:id>` (tối đa 20 emoji).
2. Mỗi emoji hợp lệ có một tin nhắn preview riêng với đúng một nút Upload.
3. Nút chỉ được người gọi lệnh sử dụng; người khác nhận thông báo ephemeral.
4. Upload thành công tạo emoji có đúng tên và trạng thái animated trong server đích,
   sau đó nút bị vô hiệu hóa và tin nhắn xác nhận thành công.
5. Input sai, quyền thiếu, emoji trùng tên, lỗi CDN, giới hạn emoji server và lỗi
   Discord đều trả phản hồi rõ ràng mà không làm dừng các emoji preview khác.
6. Cog được nạp từ `index.py`; unit tests mới chạy được.

## Open Questions

Không còn câu hỏi chặn triển khai. Quy ước đang chọn là chỉ người có quyền `Manage
Expressions` ở server đích được gọi lệnh; bot cũng phải có quyền này. Lệnh chỉ xuất
hiện ở `MAIN_GUILD_ID`, tương tự các slash command hiện có.
