# NailMind

这是 NailMind 的总仓库，用来集中放项目说明、方案文档、架构图和仓库导航。

业务代码已经拆分到三个独立仓库，并新增独立 GPU 推理模块。根仓库主要作为公开展示入口和模块导航。

## 仓库分工

- `app`：Android 客户端，负责用户端浏览、AI 试戴、收藏、预约等能力
- `backend`：后端服务，负责业务接口、数据存储、试戴任务与趋势能力
- `web-admin`：商家端与运营端前端，负责后台管理和门店运营
- `inference`：AI 图片编辑推理服务，部署到 GPU 服务器，只负责生成试戴结果图

## 分仓库入口

- App: [kovk/nailmind-app](https://github.com/kovk/nailmind-app)
- Backend: [kovk/nailmind-backend](https://github.com/kovk/nailmind-backend)
- Web Admin: [kovk/nailmind-web-admin](https://github.com/kovk/nailmind-web-admin)
- Inference: 当前在本仓库 `inference/` 下，后续可单独拆仓

## 文档入口

- [方案设计文档](./docs/方案设计文档.md)

当前总仓库只保留这些内容：

- 项目总览与仓库导航
- 方案设计文档
- 架构图、流程图、时序图、ER 图
- 对外展示需要的补充说明材料
