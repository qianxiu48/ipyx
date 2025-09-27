#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP延迟测试脚本
功能：测试IP的延迟、国家、端口，并按国家分类保存结果
"""

import asyncio
import aiohttp
import socket
import time
import ipaddress
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Optional
import requests

# ==================== 用户配置区域 ====================

# IP源配置
IP_SOURCES = {
    "cfip": "https://raw.githubusercontent.com/qianxiu203/cfipcaiji/refs/heads/main/ip.txt",
    "as13335": "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/13335/ipv4-aggregated.txt",
    "as209242": "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/209242/ipv4-aggregated.txt",
    "as24429": "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/24429/ipv4-aggregated.txt",
    "as35916": "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/35916/ipv4-aggregated.txt",
    "as199524": "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/199524/ipv4-aggregated.txt",
    "cm": "https://raw.githubusercontent.com/cmliu/cmliu/main/CF-CIDR.txt",
    "bestali": "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestAli/bestaliv4.txt",
    "bestcfv4": "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/bestcfv4.txt",
    "bestcfv6": "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/bestcfv6.txt",
    "official": "https://www.cloudflare.com/ips-v4/"
}

# 测试配置
CONCURRENT_TESTS = 30  # 并发测试数量
TIMEOUT = 5  # 连接超时时间（秒）
TEST_PORTS = [80]  # 单个或多个测试端口：443，8443，2053，2083，2087，2096
MAX_IPS_PER_COUNTRY = 5  # 每个国家最大IP数量（增加到20）
TARGET_COUNTRIES = ["US", "JP", "SG", "HK"]  # 目标国家列表（修复重复的HK）
MIN_COUNTRIES_REQUIRED = 2  # 满足条件的最小国家数量（增加到4）

# 文件配置
OUTPUT_DIR = "ip_results"  # 输出目录

# 显示配置
DISPLAY_MODE = "minimal"  # minimal（极简模式）, standard（标准模式）, detailed(详细模式)

# ==================== 核心功能类 ====================

class ProgressDisplay:
    """进度显示管理器，支持多种显示模式"""
    def __init__(self, mode="minimal"):
        self.mode = mode  # minimal, standard, detailed
        self.last_lines = 0
        self.current_batch = 0
        self.total_batches = 0
        self.tested_ips = 0
        self.total_ips = 0
        self.source_name = ""
        self.batch_results = []
        self.start_time = time.time()
        self.success_count = 0
        self.failed_count = 0
    
    def update_progress(self, source_name: str, current_batch: int, total_batches: int, 
                       tested_ips: int, total_ips: int, batch_results: List[Dict]):
        """更新进度信息"""
        self.source_name = source_name
        self.current_batch = current_batch
        self.total_batches = total_batches
        self.tested_ips = tested_ips
        self.total_ips = total_ips
        self.batch_results = batch_results
        
        # 更新统计
        self.success_count = sum(1 for r in self.batch_results if r["best_latency"] < float('inf'))
        self.failed_count = len(self.batch_results) - self.success_count
        
        self._display()
    
    def _display(self):
        """根据模式显示进度信息"""
        # 清除之前的进度行
        if self.last_lines > 0:
            for _ in range(self.last_lines):
                print('\033[1A\033[K', end='')
        
        lines = []
        
        if self.mode == "minimal":
            lines = self._minimal_display()
        elif self.mode == "standard":
            lines = self._standard_display()
        else:  # detailed
            lines = self._detailed_display()
        
        # 显示所有行
        for line in lines:
            print(line)
        
        self.last_lines = len(lines)
    
    def _minimal_display(self):
        """极简显示模式 - 只显示核心进度信息"""
        progress = self.tested_ips / self.total_ips * 100 if self.total_ips > 0 else 0
        elapsed_time = time.time() - self.start_time
        ips_per_second = self.tested_ips / elapsed_time if elapsed_time > 0 else 0
        
        # 创建进度条
        bar_length = 20
        filled_length = int(bar_length * progress / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        lines = []
        lines.append(f"{self.source_name}: [{bar}] {progress:.1f}% ({self.tested_ips}/{self.total_ips})")
        lines.append(f"成功: {self.success_count} | 失败: {self.failed_count} | 速度: {ips_per_second:.1f} IP/s")
        
        return lines
    
    def _standard_display(self):
        """标准显示模式 - 显示基本进度信息"""
        progress = self.tested_ips / self.total_ips * 100 if self.total_ips > 0 else 0
        elapsed_time = time.time() - self.start_time
        
        lines = []
        lines.append(f"IP源: {self.source_name} - 批次 {self.current_batch}/{self.total_batches}")
        lines.append(f"进度: {progress:.1f}% ({self.tested_ips}/{self.total_ips})")
        lines.append(f"统计: 成功 {self.success_count}, 失败 {self.failed_count}")
        
        return lines
    
    def _detailed_display(self):
        """详细显示模式 - 显示完整信息"""
        progress = self.tested_ips / self.total_ips * 100 if self.total_ips > 0 else 0
        
        lines = []
        lines.append(f"IP源进度: {self.source_name} - 批次 {self.current_batch}/{self.total_batches} "
                   f"({self.tested_ips}/{self.total_ips} - {progress:.1f}%)")
        lines.append(f"  成功: {self.success_count}, 失败: {self.failed_count}")
        
        # 显示最近3个测试结果
        recent_results = []
        for result in self.batch_results[-3:]:
            if result["best_latency"] < float('inf'):
                recent_results.append(f"✓ {result['ip']}:{result['best_port']} - {result['best_latency']:.2f}ms - {result['country']}")
            else:
                recent_results.append(f"✗ {result['ip']}:80 - 失败")
        
        if recent_results:
            lines.append("  最近结果:")
            for result in recent_results:
                lines.append(f"    {result}")
        
        return lines
    
    def clear(self):
        """清除进度显示"""
        if self.last_lines > 0:
            for _ in range(self.last_lines):
                print('\033[1A\033[K', end='')
            self.last_lines = 0

class IPDelayTester:
    def __init__(self):
        self.session = None
        self.results = {}
        self.country_stats = {}
        self.progress = ProgressDisplay(mode=DISPLAY_MODE)
        
    async def init_session(self):
        """初始化aiohttp会话"""
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
    
    def get_ip_country(self, ip: str) -> str:
        """获取IP所在国家（使用在线API服务）"""
        try:
            # 使用免费的IP地理位置API
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get('countryCode', 'UNKNOWN')
        except:
            pass
        
        # 如果API失败，使用简单的IP段判断作为备用
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                return "PRIVATE"
            
            # 简单的IP段到国家映射（仅用于演示）
            first_octet = int(ip.split('.')[0])
            if first_octet in [1, 8, 13, 23, 24, 32, 34, 35, 50, 52, 54, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 96, 97, 98, 99, 104, 107, 108, 128, 129, 130, 131, 132, 134, 135, 136, 137, 138, 139, 140, 142, 143, 144, 146, 147, 148, 149, 152, 155, 156, 157, 158, 159, 160, 161, 162, 164, 165, 166, 167, 168, 169, 170, 172, 173, 174, 192, 198, 199, 204, 205, 206, 207, 208, 209, 216]:
                return "US"  # 美国IP段
            elif first_octet in [58, 59, 60, 61, 101, 103, 106, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 175, 176, 177, 178, 179, 180, 182, 183, 202, 203, 210, 211, 218, 219, 220, 221, 222, 223]:
                return "CN"  # 中国IP段
            elif first_octet in [43, 49, 58, 59, 60, 61, 103, 106, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 133, 153, 202, 203, 210, 211, 218, 219, 220, 221, 222, 223]:
                return "JP"  # 日本IP段
            
        except:
            pass
        
        return "UNKNOWN"
    
    async def test_single_ip_port(self, ip: str, port: int) -> Tuple[bool, float, str]:
        """测试单个IP和端口的延迟"""
        start_time = time.time()
        success = False
        country = "UNKNOWN"
        
        # 先过滤掉明显无效的IP
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return False, -1, "INVALID"
        except:
            return False, -1, "INVALID"
        
        try:
            # 测试TCP连接延迟
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
            
            latency = (time.time() - start_time) * 1000  # 转换为毫秒
            success = True
            country = self.get_ip_country(ip)
            
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            latency = -1
            
        return success, latency, country
    
    async def test_ip(self, ip: str) -> Dict:
        """测试单个IP的所有端口"""
        results = {
            "ip": ip,
            "ports": {},
            "best_latency": float('inf'),
            "best_port": None,
            "country": "UNKNOWN"
        }
        
        # 并发测试所有端口
        tasks = []
        for port in TEST_PORTS:
            task = self.test_single_ip_port(ip, port)
            tasks.append(task)
        
        port_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (success, latency, country) in enumerate(port_results):
            port = TEST_PORTS[i]
            results["ports"][port] = {
                "success": success,
                "latency": latency if success else -1
            }
            
            if success and latency < results["best_latency"]:
                results["best_latency"] = latency
                results["best_port"] = port
            
            if country != "UNKNOWN":
                results["country"] = country
        
        return results
    
    async def test_ip_batch(self, ips: List[str]) -> List[Dict]:
        """批量测试IP（并发控制）"""
        semaphore = asyncio.Semaphore(CONCURRENT_TESTS)
        
        async def bounded_test(ip):
            async with semaphore:
                return await self.test_ip(ip)
        
        tasks = [bounded_test(ip) for ip in ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if not isinstance(result, Exception):
                valid_results.append(result)
        
        return valid_results
    
    def should_stop_testing(self) -> bool:
        """判断是否满足停止条件"""
        countries_with_enough_ips = 0
        
        for country in TARGET_COUNTRIES:
            if country in self.country_stats:
                if self.country_stats[country] >= MAX_IPS_PER_COUNTRY:
                    countries_with_enough_ips += 1
        
        return countries_with_enough_ips >= MIN_COUNTRIES_REQUIRED
    
    def display_country_stats(self):
        """显示当前国家统计信息"""
        print("当前国家统计:")
        for country in TARGET_COUNTRIES:
            count = self.country_stats.get(country, 0)
            status = "✓" if count >= MAX_IPS_PER_COUNTRY else " "
            print(f"  {status} {country}: {count}/{MAX_IPS_PER_COUNTRY}")
    
    def update_country_stats(self, results: List[Dict]):
        """更新国家统计信息"""
        for result in results:
            country = result["country"]
            if country != "UNKNOWN" and country in TARGET_COUNTRIES:
                if country not in self.country_stats:
                    self.country_stats[country] = 0
                self.country_stats[country] += 1
    
    def save_results_by_country(self, results: List[Dict]):
        """按国家分类保存结果"""
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        country_data = {}
        
        for result in results:
            country = result["country"]
            if country == "UNKNOWN":
                continue
                
            if country not in country_data:
                country_data[country] = []
            
            # 只保存有效的结果
            if result["best_latency"] < float('inf'):
                country_data[country].append(result)
        
        # 按国家保存到文件（覆盖模式）
        for country, data in country_data.items():
            filename = os.path.join(OUTPUT_DIR, f"{country}_ips.txt")
            
            with open(filename, 'w', encoding='utf-8') as f:
                # 按延迟排序
                data.sort(key=lambda x: x["best_latency"])
                
                for result in data:
                    # 格式: IP#国家 延迟信息
                    f.write(f"{result['ip']}#{country} {result['best_latency']:.2f}ms\n")
    
    async def get_ips_from_source(self, source: str) -> List[str]:
        """从指定源获取IP列表"""
        if source not in IP_SOURCES:
            print(f"错误: 不支持的IP源: {source}")
            return []
        
        url = IP_SOURCES[source]
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            ips = []
            for line in response.text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # 尝试解析IP或CIDR
                    try:
                        if '/' in line:
                            # CIDR表示法，展开为单个IP
                            network = ipaddress.ip_network(line, strict=False)
                            for ip in network.hosts():
                                ips.append(str(ip))
                        else:
                            # 单个IP
                            ipaddress.ip_address(line)
                            ips.append(line)
                    except:
                        continue
            
            print(f"从 {source} 获取到 {len(ips)} 个IP")
            return ips
            
        except Exception as e:
            print(f"获取IP列表失败: {e}")
            return []

# ==================== 主程序 ====================

async def main():
    """主程序"""
    print("=== IP延迟测试脚本 ===")
    print(f"配置信息:")
    print(f"  并发测试数: {CONCURRENT_TESTS}")
    print(f"  超时时间: {TIMEOUT}秒")
    print(f"  测试端口: {TEST_PORTS}")
    print(f"  目标国家: {TARGET_COUNTRIES}")
    print(f"  每个国家最大IP数: {MAX_IPS_PER_COUNTRY}")
    print(f"  满足条件的最小国家数: {MIN_COUNTRIES_REQUIRED}")
    print(f"  可用IP源: {list(IP_SOURCES.keys())}")
    print()
    
    tester = IPDelayTester()
    await tester.init_session()
    
    try:
        all_results = []
        tested_sources = 0
        
        # 遍历所有IP源
        for source_name in IP_SOURCES.keys():
            tested_sources += 1
            print(f"=== 正在测试第 {tested_sources}/{len(IP_SOURCES)} 个IP源: {source_name} ===")
            
            # 获取当前IP源的IP列表
            print(f"正在从 {source_name} 获取IP列表...")
            all_ips = await tester.get_ips_from_source(source_name)
            
            if not all_ips:
                print(f"⚠ 从 {source_name} 未获取到IP列表，跳过此源")
                continue
            
            print(f"从 {source_name} 获取到 {len(all_ips)} 个IP")
            print("开始延迟测试...")
            
            batch_size = CONCURRENT_TESTS  # 每批处理IP数量与并发数一致
            tested_ips = 0
            
            total_batches = (len(all_ips) + batch_size - 1) // batch_size
            
            for i in range(0, len(all_ips), batch_size):
                batch_ips = all_ips[i:i + batch_size]
                current_batch = i // batch_size + 1
                
                try:
                    batch_results = await tester.test_ip_batch(batch_ips)
                    all_results.extend(batch_results)
                    tested_ips += len(batch_ips)
                    
                    # 更新统计并检查停止条件
                    tester.update_country_stats(batch_results)
                    
                    # 使用固定位置显示进度
                    tester.progress.update_progress(
                        source_name, current_batch, total_batches,
                        tested_ips, len(all_ips), batch_results
                    )
                    
                    # 检查是否满足停止条件
                    if tester.should_stop_testing():
                        tester.progress.clear()
                        print("✓ 满足停止条件，停止测试")
                        break
                    
                except Exception as e:
                    tester.progress.clear()
                    print(f"批次处理失败: {e}")
                    continue
            
            # 显示当前IP源完成后的统计
            print(f"=== {source_name} IP源测试完成 ===")
            tester.display_country_stats()
            print()
            
            # 检查是否满足停止条件（在切换IP源前）
            if tester.should_stop_testing():
                print("✓ 满足停止条件，停止测试")
                break
        
        # 保存结果
        print("正在保存结果...")
        tester.save_results_by_country(all_results)
        
        # 显示最终统计
        print("\n=== 所有IP源测试完成 ===")
        print("最终国家统计:")
        for country in TARGET_COUNTRIES:
            count = tester.country_stats.get(country, 0)
            status = "✓" if count >= MAX_IPS_PER_COUNTRY else " "
            print(f"  {status} {country}: {count}个IP")
        
        # 检查是否满足停止条件
        if tester.should_stop_testing():
            print("✓ 成功满足停止条件")
        else:
            print("⚠ 未满足停止条件，所有IP源已测试完成")
        
        total_valid_ips = sum(1 for r in all_results if r["best_latency"] < float('inf'))
        print(f"总有效IP数: {total_valid_ips}")
        print(f"结果已保存到 {OUTPUT_DIR} 目录")
        
    except Exception as e:
        print(f"程序执行出错: {e}")
    finally:
        await tester.close_session()

if __name__ == "__main__":
    # 检查依赖
    try:
        import aiohttp
        import ipaddress
    except ImportError as e:
        print(f"缺少依赖包: {e}")
        print("请安装依赖: pip install aiohttp requests")
        exit(1)
    
    # 运行主程序
    asyncio.run(main())