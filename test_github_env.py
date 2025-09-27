#!/usr/bin/env python3
"""
GitHub Actions环境测试脚本
用于验证GitHub环境是否能正常运行IP测试脚本
"""

import os
import sys

def test_environment():
    """测试环境变量和基本功能"""
    print("🔧 GitHub Actions环境测试")
    print("=" * 50)
    
    # 检查环境变量
    github_env = os.environ.get('GITHUB_ACTIONS')
    runner_env = os.environ.get('RUNNER_ENVIRONMENT')
    
    print(f"GITHUB_ACTIONS: {github_env}")
    print(f"RUNNER_ENVIRONMENT: {runner_env}")
    
    # 判断是否为GitHub环境
    is_github = github_env == 'true' or runner_env == 'github-hosted'
    print(f"是否为GitHub环境: {is_github}")
    
    # 检查Python版本
    print(f"Python版本: {sys.version}")
    
    # 检查当前工作目录
    import os
    print(f"当前工作目录: {os.getcwd()}")
    
    # 检查文件是否存在
    files_to_check = ['ip_tester.py', '.github/workflows/ip_test.yml']
    for file in files_to_check:
        exists = os.path.exists(file)
        print(f"文件 {file}: {'✅ 存在' if exists else '❌ 不存在'}")
    
    print("=" * 50)
    
    if is_github:
        print("✅ GitHub Actions环境检测成功")
        return True
    else:
        print("⚠️ 非GitHub环境，请检查配置")
        return False

def test_imports():
    """测试必要的导入"""
    print("\n📦 测试导入依赖")
    print("-" * 30)
    
    try:
        import aiohttp
        print("✅ aiohttp 导入成功")
    except ImportError as e:
        print(f"❌ aiohttp 导入失败: {e}")
        return False
    
    try:
        import asyncio
        print("✅ asyncio 导入成功")
    except ImportError as e:
        print(f"❌ asyncio 导入失败: {e}")
        return False
    
    print("✅ 所有依赖导入成功")
    return True

async def test_basic_functionality():
    """测试基本功能"""
    print("\n🔍 测试基本功能")
    print("-" * 30)
    
    try:
        # 测试简单的异步功能
        import asyncio
        
        async def simple_test():
            await asyncio.sleep(0.1)
            return "异步测试成功"
        
        result = await simple_test()
        print(f"✅ {result}")
        
        # 测试IP地址解析
        import ipaddress
        ip = ipaddress.ip_address('1.1.1.1')
        print(f"✅ IP地址解析成功: {ip}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基本功能测试失败: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 开始GitHub Actions环境测试\n")
    
    # 测试环境
    env_ok = test_environment()
    
    # 测试导入
    imports_ok = test_imports()
    
    # 测试基本功能
    basic_ok = await test_basic_functionality()
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print(f"环境检测: {'✅ 通过' if env_ok else '❌ 失败'}")
    print(f"依赖导入: {'✅ 通过' if imports_ok else '❌ 失败'}")
    print(f"基本功能: {'✅ 通过' if basic_ok else '❌ 失败'}")
    
    overall_success = env_ok and imports_ok and basic_ok
    
    if overall_success:
        print("\n🎉 所有测试通过！GitHub Actions环境可以正常运行")
        print("💡 建议: 现在可以运行完整的IP测试脚本")
    else:
        print("\n⚠️ 部分测试失败，请检查环境配置")
        print("💡 建议: 先修复失败的测试项")
    
    return overall_success

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)