#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP延迟测试脚本
功能：测试IP库中IP的延迟、国家和端口信息
"""

import asyncio
import aiohttp
import socket
import time
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import requests
import json
import os
import argparse
from typing import List, Dict, Tuple

class IPTester:
    def __init__(self, max_concurrent=30, timeout=5):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.results = {}
        self.country_stats = {}
        
    async def get_ip_list_from_urls(self) -> List[str]:
        """从IP库URL获取IP列表"""
        ip_urls = {
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
        
        all_ips = []
        
        async def fetch_url(source_name, url):
            """异步获取单个URL的IP列表"""
            try:
                print(f"正在获取 {source_name} 的IP列表...")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            text = await response.text()
                            ips = []
                            for line in text.split('\n'):
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    # 处理CIDR格式和单个IP
                                    if '/' in line:
                                        try:
                                            network = ipaddress.ip_network(line, strict=False)
                                            # 限制每个CIDR取前5个IP避免过多
                                            for ip in list(network.hosts())[:5]:
                                                ips.append(str(ip))
                                        except:
                                            continue
                                    else:
                                        try:
                                            ipaddress.ip_address(line)
                                            ips.append(line)
                                        except:
                                            continue
                            
                            print(f"从 {source_name} 获取到 {len(ips)} 个IP")
                            return ips
                        else:
                            print(f"获取 {source_name} 失败: HTTP {response.status}")
                            return []
            except Exception as e:
                print(f"获取 {source_name} 时出错: {e}")
                return []
        
        # 并发获取所有URL
        tasks = []
        for source_name, url in ip_urls.items():
            task = fetch_url(source_name, url)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 合并结果
        for ips in results:
            if ips:
                all_ips.extend(ips)
        
        # 去重
        all_ips = list(set(all_ips))
        print(f"总共获取到 {len(all_ips)} 个唯一IP")
        return all_ips
    
    async def get_country_info(self, ip: str) -> str:
        """获取IP的国家信息"""
        # 多个API备用，提高成功率
        apis = [
            {
                'url': f"http://ipapi.co/{ip}/json/",
                'field': 'country_name',
                'timeout': 3
            },
            {
                'url': f"https://ipinfo.io/{ip}/json",
                'field': 'country',
                'timeout': 3
            },
            {
                'url': f"http://ip-api.com/json/{ip}",
                'field': 'country',
                'timeout': 3
            },
            {
                'url': f"https://api.ipgeolocation.io/ipgeo?apiKey=demo&ip={ip}",
                'field': 'country_name',
                'timeout': 3
            }
        ]
        
        for api in apis:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=api['timeout'])) as session:
                    async with session.get(api['url']) as response:
                        if response.status == 200:
                            data = await response.json()
                            country = data.get(api['field'], '')
                            if country and country != 'Unknown' and country != '':
                                return country
            except Exception as e:
                # 静默失败，尝试下一个API
                continue
        
        # 如果所有API都失败，尝试使用本地IP数据库（简化版）
        # 这里可以添加本地IP数据库查询逻辑
        return 'Unknown'
    
    def test_port(self, ip: str, port: int = 80) -> bool:
        """测试端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def ping_ip(self, ip: str) -> float:
        """测试IP延迟"""
        start_time = time.time()
        try:
            # 使用socket连接测试延迟
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, 80))
            end_time = time.time()
            sock.close()
            return (end_time - start_time) * 1000  # 转换为毫秒
        except:
            return float('inf')
    
    async def test_single_ip(self, ip: str) -> Dict:
        """测试单个IP的延迟、国家和端口"""
        result = {
            'ip': ip,
            'latency': float('inf'),
            'country': 'Unknown',
            'port_443_open': False,
            'port_8433_open': False,
            'port_2053_open': False,
            'port_2083_open': False,
            'port_2087_open': False,
            'port_2096_open': False,
            'status': 'failed'
        }
        
        try:
            # 测试延迟
            latency = self.ping_ip(ip)
            result['latency'] = latency
            
            # 获取国家信息
            country = await self.get_country_info(ip)
            result['country'] = country
            
            # 测试端口
            result['port_443_open'] = self.test_port(ip, 443)
            result['port_8433_open'] = self.test_port(ip, 8433)
            result['port_2053_open'] = self.test_port(ip, 2053)
            result['port_2083_open'] = self.test_port(ip, 2083)
            result['port_2087_open'] = self.test_port(ip, 2087)
            result['port_2096_open'] = self.test_port(ip, 2096)
            
            result['status'] = 'success'
            
        except Exception as e:
            result['status'] = f'error: {str(e)}'
        
        return result
    
    async def test_ip_batch(self, ip_batch: List[str]) -> List[Dict]:
        """批量测试IP"""
        # 使用线程池执行同步操作，避免阻塞事件循环
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 创建所有任务
            tasks = []
            for ip in ip_batch:
                # 将同步方法包装为异步任务
                task = asyncio.get_event_loop().run_in_executor(
                    executor, 
                    self.test_single_ip_sync, 
                    ip
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, dict):
                valid_results.append(result)
        
        return valid_results
    
    def test_single_ip_sync(self, ip: str) -> Dict:
        """同步版本的单个IP测试"""
        result = {
            'ip': ip,
            'latency': float('inf'),
            'country': 'Unknown',
            'port_443_open': False,
            'port_8433_open': False,
            'port_2053_open': False,
            'port_2083_open': False,
            'port_2087_open': False,
            'port_2096_open': False,
            'status': 'failed'
        }
        
        try:
            # 测试延迟
            latency = self.ping_ip(ip)
            result['latency'] = latency
            
            # 获取国家信息（使用同步请求）
            country = self.get_country_info_sync(ip)
            result['country'] = country
            
            # 测试端口
            result['port_443_open'] = self.test_port(ip, 443)
            result['port_8433_open'] = self.test_port(ip, 8433)
            result['port_2053_open'] = self.test_port(ip, 2053)
            result['port_2083_open'] = self.test_port(ip, 2083)
            result['port_2087_open'] = self.test_port(ip, 2087)
            result['port_2096_open'] = self.test_port(ip, 2096)
            
            result['status'] = 'success'
            
        except Exception as e:
            result['status'] = f'error: {str(e)}'
        
        return result
    
    def get_country_info_sync(self, ip: str) -> str:
        """同步版本的国家信息获取"""
        # 多个API备用，提高成功率
        apis = [
            {
                'url': f"http://ipapi.co/{ip}/json/",
                'field': 'country_name',
                'timeout': 3
            },
            {
                'url': f"https://ipinfo.io/{ip}/json",
                'field': 'country',
                'timeout': 3
            },
            {
                'url': f"http://ip-api.com/json/{ip}",
                'field': 'country',
                'timeout': 3
            }
        ]
        
        for api in apis:
            try:
                response = requests.get(api['url'], timeout=api['timeout'])
                if response.status_code == 200:
                    data = response.json()
                    country = data.get(api['field'], '')
                    if country and country != 'Unknown' and country != '':
                        return country
            except:
                continue
        
        return 'Unknown'
    
    def save_results_by_country(self, results: List[Dict], target_countries: list = None, max_ips_per_country: int = 3):
        """按国家保存结果到对应txt文件，只保存目标国家的IP，每个国家最多保存指定数量的IP"""
        if target_countries is None:
            target_countries = ['JP', 'SG', 'US']  # 默认目标国家
            
        country_data = {}
        
        for result in results:
            if result['status'] == 'success' and result['latency'] <= 300:  # 只保存延迟<=300ms的IP
                country = result['country']
                # 只保存目标国家的IP
                if country in target_countries:
                    if country not in country_data:
                        country_data[country] = []
                    
                    country_data[country].append(result)
        
        # 创建国家目录
        country_dir = "country_results"
        if not os.path.exists(country_dir):
            os.makedirs(country_dir)
        
        # 只保存目标国家的IP信息，每个国家最多保存max_ips_per_country个
        for country in target_countries:
            ips = country_data.get(country, [])
            # 按延迟排序，取延迟最低的前max_ips_per_country个
            ips.sort(key=lambda x: x['latency'])
            ips = ips[:max_ips_per_country]  # 只保留前max_ips_per_country个
            
            filename = os.path.join(country_dir, f"{country.replace(' ', '_')}.txt")
            
            with open(filename, 'w', encoding='utf-8') as f:
                for ip_info in ips:
                    # 简化格式：IP#国家 延迟
                    f.write(f"{ip_info['ip']}#{country.lower()} {ip_info['latency']:.2f}\n")
            
            print(f"已保存 {country} 的 {len(ips)} 个延迟<=300ms的IP到 {filename}")
            
        # 删除非目标国家的文件
        for filename in os.listdir(country_dir):
            file_path = os.path.join(country_dir, filename)
            if os.path.isfile(file_path):
                # 检查文件名是否对应目标国家
                country_code = filename.replace('.txt', '').upper()
                if country_code not in target_countries:
                    os.remove(file_path)
                    print(f"已删除非目标国家文件: {filename}")
    
    def should_stop_testing(self, target_countries: list = None, min_ips_per_country: int = 3) -> bool:
        """判断是否满足停止条件"""
        if target_countries is None:
            target_countries = ['JP', 'SG', 'US']  # 默认目标国家
            
        country_counts = {}
        
        for result in self.results.values():
            if result['status'] == 'success' and result['latency'] <= 300:  # 只统计延迟<=300ms的IP
                country = result['country']
                # 只统计目标国家的IP
                if country in target_countries:
                    country_counts[country] = country_counts.get(country, 0) + 1
        
        # 检查所有目标国家是否都满足最小IP数量
        for country in target_countries:
            if country_counts.get(country, 0) < min_ips_per_country:
                return False
        
        return True
    
    async def run_test(self, target_countries: list = None, min_ips_per_country: int = 3):
        """运行IP测试"""
        if target_countries is None:
            target_countries = ['JP', 'SG', 'US']  # 默认目标国家
            
        print(f"目标国家: {target_countries}")
        print(f"每个国家最少IP数: {min_ips_per_country}")
        print(f"最大延迟限制: 300ms")
        
        print("开始获取IP列表...")
        all_ips = await self.get_ip_list_from_urls()
        
        if not all_ips:
            print("未获取到任何IP，程序结束")
            return
        
        print(f"开始测试 {len(all_ips)} 个IP...")
        
        # 跟踪每个目标国家的完成状态
        completed_countries = set()
        
        # 分批测试
        batch_size = self.max_concurrent
        tested_count = 0
        
        for i in range(0, len(all_ips), batch_size):
            batch = all_ips[i:i + batch_size]
            print(f"\n测试批次 {i//batch_size + 1}: {len(batch)} 个IP")
            
            batch_results = await self.test_ip_batch(batch)
            
            # 保存结果
            for result in batch_results:
                self.results[result['ip']] = result
                
                if result['status'] == 'success':
                    country = result['country']
                    self.country_stats[country] = self.country_stats.get(country, 0) + 1
                    
                    # 显示延迟信息，标记超过300ms的IP
                    latency_info = f"延迟: {result['latency']:.2f}ms"
                    if result['latency'] > 300:
                        latency_info += " (超过300ms，不保存)"
                    
                    print(f"  {result['ip']} - {country} - {latency_info}")
                else:
                    print(f"  {result['ip']} - 测试失败")
            
            tested_count += len(batch)
            
            # 检查每个目标国家的完成状态
            country_counts = {}
            for result in self.results.values():
                if result['status'] == 'success' and result['latency'] <= 300:
                    country = result['country']
                    # 只统计目标国家的IP
                    if country in target_countries:
                        country_counts[country] = country_counts.get(country, 0) + 1
            
            # 更新已完成的国家
            for country in target_countries:
                if country not in completed_countries and country_counts.get(country, 0) >= min_ips_per_country:
                    completed_countries.add(country)
                    print(f"\n✅ 国家 {country} 已完成: 找到 {country_counts[country]} 个延迟<=300ms的IP")
            
            # 检查是否所有目标国家都已完成
            if len(completed_countries) == len(target_countries):
                print(f"\n🎉 所有目标国家都已完成!")
                break
            
            # 显示当前状态
            remaining_countries = [c for c in target_countries if c not in completed_countries]
            if remaining_countries:
                print(f"剩余目标国家: {remaining_countries}")
            
            # 进度显示
            progress = (tested_count / len(all_ips)) * 100
            print(f"进度: {progress:.1f}% ({tested_count}/{len(all_ips)})")
            
            # 短暂延迟避免请求过快
            await asyncio.sleep(1)
        
        # 保存结果
        print("\n正在按国家保存结果...")
        self.save_results_by_country(list(self.results.values()), target_countries, min_ips_per_country)
        
        # 显示统计信息
        print("\n=== 测试统计 ===")
        print(f"总测试IP数: {len(self.results)}")
        print(f"成功测试数: {sum(1 for r in self.results.values() if r['status'] == 'success')}")
        
        # 只统计目标国家的延迟<=300ms的IP
        target_country_ips = sum(1 for r in self.results.values() 
                                if r['status'] == 'success' and r['latency'] <= 300 
                                and r['country'] in target_countries)
        print(f"目标国家延迟<=300ms的可用IP数: {target_country_ips}")
        
        print(f"覆盖国家数: {len(self.country_stats)}")
        
        # 显示目标国家的统计
        print("\n目标国家统计:")
        for country in target_countries:
            count = sum(1 for r in self.results.values() if r['status'] == 'success' and r['country'] == country and r['latency'] <= 300)
            status = "✅ 已完成" if country in completed_countries else "⏳ 进行中"
            print(f"  {country}: {count} 个延迟<=300ms的IP ({status})")

async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='IP延迟测试脚本')
    parser.add_argument('--target-countries', type=str, default='JP,SG,US',
                       help='目标国家代码列表（逗号分隔，如：JP,SG,US）')
    parser.add_argument('--min-ips', type=int, default=3,
                       help='每个国家最少IP数量')
    parser.add_argument('--max-concurrent', type=int, default=30,
                       help='最大并发数')
    
    args = parser.parse_args()
    
    # 处理目标国家参数
    target_countries = [country.strip().upper() for country in args.target_countries.split(',')]
    
    print("=== IP延迟测试脚本 ===")
    print(f"目标国家: {target_countries}")
    print(f"每个国家最少IP数: {args.min_ips}")
    print(f"最大并发数: {args.max_concurrent}")
    
    # 配置参数
    max_concurrent = args.max_concurrent  # 并发数
    min_ips_per_country = args.min_ips  # 每个国家最少IP数
    
    tester = IPTester(max_concurrent=max_concurrent)
    
    try:
        await tester.run_test(target_countries, min_ips_per_country)
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试过程中出错: {e}")
    
    print("\n测试完成！")

if __name__ == "__main__":
    asyncio.run(main())