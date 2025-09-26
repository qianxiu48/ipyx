# IP延迟测试脚本

这是一个自动测试IP延迟、国家和端口信息的Python脚本。

## 功能特性

- 测试IP延迟（毫秒）
- 识别IP所属国家
- 测试指定端口是否开放（443, 8433, 2053, 2083, 2087, 2096）
- 按国家保存结果
- 支持并发测试（默认30个并发）
- 自动过滤非目标国家IP

## 目标国家

默认目标国家：
- JP（日本）
- SG（新加坡）
- US（美国）

每个国家最少保存3个延迟≤300ms的IP。

## GitHub Actions 自动运行

### 设置步骤

1. **创建GitHub仓库**
   - 将本项目的所有文件上传到GitHub仓库

2. **启用Actions**
   - 在GitHub仓库页面，点击"Actions"标签
   - 点击"I understand my workflows, go ahead and enable them"

3. **自动运行**
   - Actions会自动每3小时运行一次
   - 运行结果会自动提交到仓库的`country_results`目录

### Actions配置

- **定时运行**: 每3小时自动运行（使用默认参数）
- **手动触发**: 可在Actions页面手动触发运行，支持自定义参数
- **参数配置**:
  - `target_countries`: 目标国家代码列表（逗号分隔，默认：JP,SG,US）
  - `min_ips_per_country`: 每个国家最少IP数量（默认：3）
  - `max_concurrent`: 最大并发数（默认：30）
- **结果保存**: 测试结果自动提交到仓库

### 手动触发示例

在GitHub Actions页面，点击"Run workflow"，可以设置以下参数：

- **目标国家**: `JP,SG,US,KR`（测试日本、新加坡、美国、韩国）
- **最少IP数**: `5`（每个国家保存5个IP）
- **最大并发**: `50`（使用50个并发测试）

## 本地运行

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行脚本

```bash
python ip_tester.py
```

### 自定义配置

编辑`ip_tester.py`文件中的`main()`函数来修改配置：

```python
# 配置参数
max_concurrent = 30  # 并发数
target_countries = ['JP', 'SG', 'US']  # 目标国家列表
min_ips_per_country = 3  # 每个国家最少IP数
```

## 文件结构

```
├── .github/workflows/
│   └── ip_tester.yml          # GitHub Actions配置
├── country_results/           # 测试结果目录
│   ├── JP.txt                # 日本IP列表
│   ├── SG.txt                # 新加坡IP列表
│   └── US.txt                # 美国IP列表
├── ip_tester.py              # 主脚本文件
├── requirements.txt          # Python依赖
└── README.md                 # 说明文档
```

## 结果格式

每个国家文件包含格式为：`IP#国家 延迟`

示例：
```
103.21.244.3#us 69.35
104.16.0.4#us 104.60
```

## 注意事项

- 脚本需要网络连接来获取IP列表和国家信息
- 测试过程可能需要较长时间（取决于IP数量）
- GitHub Actions运行时间限制为6小时
- 确保仓库有足够的存储空间保存测试结果