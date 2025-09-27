# GitHub Actions IP延迟测试工作流指南

## 概述

本指南详细说明如何配置和使用GitHub Actions来自动化运行IP延迟测试脚本。工作流文件已创建在 `.github/workflows/ip_delay_test.yml`。

## 工作流配置说明

### 触发条件

工作流支持三种触发方式：

1. **定时触发**：每天UTC时间18:00（北京时间凌晨2:00）自动运行
2. **手动触发**：在GitHub仓库的Actions页面手动启动
3. **代码推送触发**：当代码推送到main或master分支时自动运行

### 定时任务配置

```yaml
on:
  schedule:
    - cron: '0 18 * * *'  # UTC时间18:00（北京时间凌晨2:00）
```

**时区注意事项**：<mcreference link="https://blog.51cto.com/u_16213713/12352109" index="1">1</mcreference>
- GitHub Actions使用UTC时间
- 北京时间 = UTC时间 + 8小时
- 当前配置：UTC 18:00 = 北京时间 02:00

### 执行环境

- **操作系统**：`ubuntu-latest`
- **Python版本**：`3.10`
- **依赖安装**：自动安装requirements.txt中的依赖包

## 使用步骤

### 1. 上传到GitHub仓库

将整个项目上传到GitHub仓库：

```bash
git init
git add .
git commit -m "Initial commit with GitHub Actions workflow"
git branch -M main
git remote add origin https://github.com/yourusername/your-repo-name.git
git push -u origin main
```

### 2. 启用GitHub Actions

1. 进入GitHub仓库页面
2. 点击"Actions"标签页
3. 工作流会自动检测并显示
4. 点击"Enable workflow"启用

### 3. 手动运行工作流

1. 进入"Actions"标签页
2. 选择"IP延迟测试定时任务"工作流
3. 点击"Run workflow"按钮
4. 选择分支并运行

### 4. 查看执行结果

- **实时日志**：在Actions页面查看执行过程
- **测试结果**：工作流会将结果保存为Artifact
- **结果文件**：可在Artifacts中下载`ip-test-results`

## 重要注意事项

### 1. 执行延迟
<mcreference link="https://blog.51cto.com/aiyc/13293825" index="2">2</mcreference>
- GitHub Actions定时任务可能有1-10分钟的延迟
- 这是正常现象，无需担心

### 2. 免费额度限制
<mcreference link="https://blog.51cto.com/aiyc/13293825" index="2">2</mcreference>
- **公共仓库**：每月2000分钟免费额度
- **私有仓库**：每月500分钟免费额度
- 当前脚本运行时间约5-30分钟，完全在免费额度内

### 3. 安全注意事项

- **敏感信息**：不要在代码中硬编码API密钥等敏感信息
- **使用Secrets**：如需配置敏感信息，使用GitHub Secrets
- **权限控制**：工作流默认只有读取仓库的权限

### 4. 结果保存

工作流提供两种结果保存方式：

1. **Artifacts**：自动上传测试结果，保留7天
2. **自动提交**：可选功能，将结果提交回仓库（需要配置GitHub Token）

## 自定义配置

### 修改定时时间

编辑`.github/workflows/ip_delay_test.yml`中的cron表达式：

```yaml
schedule:
  - cron: '0 12 * * *'  # 每天UTC时间12:00（北京时间20:00）
```

cron表达式格式：`分钟 小时 日 月 星期`

### 修改测试参数

编辑`ip_delay_tester.py`中的配置部分：

```python
# 测试配置
CONCURRENT_TESTS = 30  # 并发测试数量
TIMEOUT = 3  # 连接超时时间（秒）
TEST_PORTS = [80]  # 测试端口
MAX_IPS_PER_COUNTRY = 3  # 每个国家最大IP数量
TARGET_COUNTRIES = ["US", "JP", "SG", "HK"]  # 目标国家
```

### 添加更多IP源

在`IP_SOURCES`字典中添加新的IP源：

```python
IP_SOURCES = {
    "your_source": "https://example.com/ip-list.txt",
    # ... 其他源
}
```

## 故障排除

### 常见问题

1. **工作流不运行**：检查cron表达式格式是否正确
2. **依赖安装失败**：确保requirements.txt文件格式正确
3. **脚本执行错误**：查看Actions日志中的详细错误信息

### 调试方法

1. **查看日志**：在Actions页面查看详细执行日志
2. **本地测试**：先在本地运行脚本确保正常工作
3. **简化测试**：减少并发数和测试IP数量进行调试

## 最佳实践

1. **定期检查**：每月检查一次免费额度使用情况
2. **结果备份**：重要结果建议下载保存
3. **代码版本控制**：所有修改都通过Git提交
4. **测试环境**：先在测试分支验证修改

## 相关资源

- [GitHub Actions官方文档](https://docs.github.com/en/actions)
- [cron表达式生成器](https://crontab.guru/)
- [Python虚拟环境配置](https://docs.python.org/3/tutorial/venv.html)

---

**注意**：首次运行工作流可能需要几分钟时间设置环境，后续运行会更快。