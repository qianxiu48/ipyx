# IP延迟测试脚本

基于Cloudflare IP优选脚本改写的多国家IP延迟测试工具。

## 功能特性

- ✅ **多国家支持**: 支持测试多个国家的IP延迟
- ✅ **并发测试**: 支持10个IP并发测试（可配置）
- ✅ **条件停止**: 当某个国家的IP数量达到目标时自动停止测试
- ✅ **分类存储**: 按国家创建对应的txt文件保存结果
- ✅ **覆盖更新**: 每次运行都会覆盖之前的测试结果
- ✅ **延迟排序**: 结果按延迟从低到高排序

## 使用方法

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

### 参数说明

- `--countries`: 目标国家列表，用逗号分隔（默认：CN,US,JP,HK,TW,SG,KR）
- `--counts`: 每个国家的目标IP数量，用逗号分隔（默认：10,10,10,10,10,10,10）
- `--concurrent`: 并发测试数量（默认：10）
- `--ports`: 测试端口，用逗号分隔（默认：443）
- `--output`: 输出目录（默认：ip_results）
- `--max-ips`: 最大IP数量限制，0表示无限制（默认：0）

## 输出文件结构

运行脚本后会在指定目录生成以下文件：

```
ip_results/
├── CN_ips.txt      # 中国IP列表
├── US_ips.txt      # 美国IP列表
├── JP_ips.txt      # 日本IP列表
├── HK_ips.txt      # 香港IP列表
├── TW_ips.txt      # 台湾IP列表
├── SG_ips.txt      # 新加坡IP列表
├── KR_ips.txt      # 韩国IP列表
└── summary.txt     # 汇总报告
```

## 文件格式示例

### 国家IP文件（CN_ips.txt）
```
# CN IP列表 - 延迟测试结果
# 生成时间: 2024-01-01 12:00:00
# 总数量: 15 个

1.2.3.4:443#CN 官方优选 45ms
5.6.7.8:443#CN 反代优选 67ms
9.10.11.12:443#CN 官方优选 89ms
```

### 汇总报告（summary.txt）
```
# IP测试汇总报告
# 生成时间: 2024-01-01 12:00:00

CN: 15 个IP，平均延迟 67.3ms
US: 10 个IP，平均延迟 120.5ms
JP: 8 个IP，平均延迟 95.2ms

总计: 33 个有效IP
```

## 支持的IP源

脚本从以下源获取IP：
- **official**: Cloudflare官方IP列表
- **cm**: CM整理的IP列表
- **bestali**: 最佳阿里云IP
- **proxyip**: 反代IP列表

## 支持的国家代码

脚本支持以下国家代码的自动识别：
- **CN**: 中国
- **US**: 美国
- **JP**: 日本
- **HK**: 香港
- **TW**: 台湾
- **SG**: 新加坡
- **KR**: 韩国
- **GB**: 英国
- **DE**: 德国
- **FR**: 法国
- **NL**: 荷兰
- **AU**: 澳大利亚
- **CA**: 加拿大
- **BR**: 巴西
- **IN**: 印度
- 以及其他常见国家

## GitHub Actions 使用

### 自动轮询测试

项目包含GitHub Actions工作流，可以自动进行轮询测试：

1. **手动触发**: 在GitHub仓库的Actions页面，选择"IP延迟测试"工作流
2. **配置参数**: 
   - `countries`: 目标国家列表
   - `counts`: 每个国家的目标IP数量
   - `max_ips`: 最大IP数量限制
   - `concurrent`: 并发测试数量

3. **自动执行**: 工作流会自动：
   - 运行轮询测试
   - 生成测试结果
   - 通过临时分支提交结果
   - 创建Pull Request

### 工作流文件

工作流配置文件位于：`.github/workflows/ip_test.yml`



## 注意事项

1. **网络要求**: 需要稳定的网络连接来获取IP列表和进行延迟测试
2. **并发控制**: 默认10个并发，可根据网络情况调整
3. **测试时间**: 测试大量IP可能需要较长时间
4. **结果覆盖**: 每次运行都会覆盖之前的测试结果
5. **文件编码**: 输出文件使用UTF-8编码
6. **GitHub限制**: GitHub Actions有运行时间限制，请合理设置测试参数

## 依赖安装

确保安装了必要的Python包：

```bash
pip install aiohttp
```

## 故障排除

如果遇到问题，可以尝试：
1. 减少并发数量（--concurrent 5）
2. 增加超时时间（修改脚本中的timeout参数）
3. 检查网络连接
4. 查看详细的错误信息

## 版本信息

- 版本: 1.0.0
- 基于: Cloudflare IP优选脚本
- 语言: Python 3.7+

---

**注意**: 本工具仅供学习和测试使用，请遵守相关法律法规。