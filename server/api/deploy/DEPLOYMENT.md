# 远程部署说明

目标服务：

- API: `crpi-j8uhehfe8m5fvjw2.cn-hangzhou.personal.cr.aliyuncs.com/s1nglet/nailmain-api:2026-06-03`
- Worker: `crpi-j8uhehfe8m5fvjw2.cn-hangzhou.personal.cr.aliyuncs.com/s1nglet/nailmind-worker:2026-06-03`

后台入口：

- `http://121.40.171.199:8080/admin`

Android 客户端默认地址已配置为：

- `http://121.40.171.199:8080/`

## 需要服务器满足

- `docker`
- `docker compose`
- 服务器安全组放行 `8080/tcp`
- 能从服务器访问阿里云 ACR

## 上传文件

把以下文件上传到服务器任意目录，例如 `/root/nailmind-deploy`：

- `docker-compose.remote.yml`
- `.env.remote`
- `remote-deploy.sh`

## 执行

```bash
chmod +x remote-deploy.sh
./remote-deploy.sh /opt/nailmind
```

执行过程中会提示输入阿里云镜像仓库密码。

## 部署后验证

```bash
curl http://127.0.0.1:8080/health
docker compose -f /opt/nailmind/docker-compose.yml ps
```

浏览器访问：

- `http://121.40.171.199:8080/admin`
