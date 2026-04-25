# KeepGeneration Web 🏃‍♂️

一个网页版的 Keep 风格跑步截图生成器。

这个项目主要是我在 [eltsen00/KeepGeneration-Web](https://github.com/eltsen00/KeepGeneration-Web) 的基础上继续改出来的版本，上游项目又基于 [Carzit/KeepSultan](https://github.com/Carzit/KeepSultan)。感谢两位作者的开源和思路 🙏

## ✨ 能做什么

- 🖼️ 上传头像和地图图片
- 🏃 自定义跑步公里数、时间、地点、天气、温度等信息
- 📅 按日期范围批量生成截图
- 🌞 支持中午、晚上两个时间段
- 🎲 参数可以在范围内随机波动
- 🗺️ 支持预设地图，也可以上传自己的地图
- 📦 生成后可以直接下载图片或 zip 包
- 🐳 支持 Docker 部署

## 🚀 本地运行

```bash
cd keep-html
pip install -r requirements.txt
python app.py
```

启动后打开终端里显示的地址即可，一般是：

```text
http://127.0.0.1:5010
```

## 🐳 Docker 运行

先构建镜像：

```bash
cd keep-html
docker build -t keepgeneration-web:latest .
```

再启动容器：

```bash
docker run -d \
  --name keepgeneration-web \
  -p 5010:5010 \
  -v ./uploads:/app/static/uploads \
  -v ./output:/app/static/output \
  -e "SECRET_KEY=your_secret_key_here" \
  --restart=unless-stopped \
  keepgeneration-web:latest
```

## 📝 二次开发说明

这个仓库不是从零开始写的，而是基于这些项目继续修改：

- [eltsen00/KeepGeneration-Web](https://github.com/eltsen00/KeepGeneration-Web)
- [Carzit/KeepSultan](https://github.com/Carzit/KeepSultan)

我主要做了一些网页端功能、批量生成、地图选择、部署说明和开源整理相关的修改。

更详细的来源说明可以看 [ATTRIBUTION.md](ATTRIBUTION.md) 和 [NOTICE](NOTICE)。

## ⚠️ 小提醒

- 本项目仅供学习、研究和个人使用。
- 生成内容怎么使用，需要使用者自己负责。
- 如果你继续 fork 或二次开发，记得保留上游项目链接和署名。
- 由于直接上游仓库目前没有明确展示 License，正式公开分发或商业使用前，建议先确认授权。

## 📄 License

本仓库中我新增和修改的部分使用 MIT License 发布，详见 [LICENSE](LICENSE)。

上游项目已有内容仍然遵守它们原本的授权和说明。

## ❤️ Thanks

感谢：

- [eltsen00/KeepGeneration-Web](https://github.com/eltsen00/KeepGeneration-Web)
- [Carzit/KeepSultan](https://github.com/Carzit/KeepSultan)
- 以及所有愿意折腾、分享和改进这个小工具的人
