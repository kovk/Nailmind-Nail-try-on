# NailMind UI Icons

这组图标基于现有 app 图标的视觉语言整理：

- 主线条色：`#DA5B87`
- 点缀色：`#F08DB1`
- 规格：`24 x 24`
- 风格：圆角描边、轻量填充、心形/闪片细节

建议映射：

- `home.svg`：首页
- `styles.svg`：款式 / 分类
- `tryon.svg`：AI 试戴
- `booking.svg`：预约
- `profile.svg`：我的 / 个人中心
- `favorites.svg`：收藏
- `history.svg`：记录 / 最近使用
- `search.svg`：搜索
- `camera.svg`：拍照
- `gallery.svg`：相册 / 上传
- `settings.svg`：设置
- `notifications.svg`：消息 / 通知

如果需要在 Android Compose 中落地，建议将这些 SVG 转成 `ImageVector` 或 `VectorDrawable`，并保留当前两色方案；若用于选中/未选中态，也可以仅保留描边主色作为单色版本。
