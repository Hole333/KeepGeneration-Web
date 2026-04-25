# Personal Tools

这里放一些和 Web 应用本身无关的个人辅助脚本。

## `process_pic_watermark.py`

这个脚本用于批量处理个人图片：

- 给目标目录下的图片添加居中水印。
- 按文件夹内顺序把图片重命名为 `IMG_1`、`IMG_2` 这类格式。
- 默认处理脚本同级 `pic` 目录中的图片。
- 默认水印文字是 `Watermark {index}`，不会包含个人信息。

它不是 KeepGeneration Web 的运行依赖，也不会被 Flask 应用调用。之所以单独放在这里，是为了和主项目代码区分开，避免别人部署 Web 应用时误以为它是必须文件。

使用示例：

```bash
python personal-tools/process_pic_watermark.py --target personal-tools/pic
```

自定义水印文字：

```bash
python personal-tools/process_pic_watermark.py \
  --target personal-tools/pic \
  --text-template "Sample {index}"
```

如果要使用项目里的中文字体，可以指定字体路径：

```bash
python personal-tools/process_pic_watermark.py \
  --target personal-tools/pic \
  --font keep-html/fonts/SourceHanSansCN-Regular.otf
```
