# IP延迟测试脚本

基于CM大佬的Cloudflare IP优选脚本改写的多国家IP延迟测试工具。


### 基本使用
```bash
python ip_tester.py
```

### 自定义参数
```bash
# 指定目标国家和数量
python ip_tester.py --countries CN,US,JP --counts 5,10,8

# 指定并发数量和端口
python ip_tester.py --concurrent 20 --ports 443,80

# 指定输出目录
python ip_tester.py --output my_results

# 限制最大IP数量
python ip_tester.py --max-ips 1000

# 完整的轮询测试示例
python ip_tester.py --countries CN,US --counts 10,5 --max-ips 1000
```

## 依赖安装

确保安装了必要的Python包：

```bash
pip install aiohttp
```

## 遵守相关法律法规

- 本工具仅供学习和测试使用，请遵守相关法律法规。
- 请勿使用本工具进行任何形式的非法活动。