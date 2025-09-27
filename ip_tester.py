#!/usr/bin/env python3
"""
IP延迟测试脚本 - 多国家IP测试与分类存储
基于Cloudflare IP优选脚本改写
"""

# ==================== 用户配置区域 ====================
# 请在此处修改以下参数来调整测试行为

# 目标国家列表（逗号分隔）
TARGET_COUNTRIES = ["US","HK","JP","SG"]

# 每个国家的目标IP数量
TARGET_COUNTS = {"US": 20,"HK": 20,"JP": 5,"SG": 5}

# 测试端口（只测试8443端口）
TARGET_PORTS = "8443"

# 延迟阈值（毫秒）- 超过此延迟的IP将被过滤
MAX_LATENCY = 2000

# 并发测试数量
CONCURRENT_TESTS = 30

# 最大IP数量限制（0表示无限制）
MAX_IPS = 0

# ==================== 导入依赖 ====================

import asyncio
import aiohttp
import json
import random
import ipaddress
import time
import argparse
import sys
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

@dataclass
class IPResult:
    """IP测试结果数据类"""
    ip: str
    port: int
    latency: float
    colo: str
    country: str
    type: str  # 'official' or 'proxy'
    
    def to_display_format(self) -> str:
        """转换为显示格式"""
        type_text = "官方优选" if self.type == "official" else "反代优选"
        return f"{self.ip}:{self.port}#{self.country} {type_text} {self.latency:.0f}ms"

class IPTester:
    """IP测试器 - 支持多国家测试和条件停止"""
    
    def __init__(self, target_countries: List[str] = None, max_concurrent: int = None, 
                 target_counts: Dict[str, int] = None, target_ports: str = None,
                 max_latency: int = None, max_ips: int = None):
        # 使用用户配置或传入参数
        self.target_countries = target_countries or TARGET_COUNTRIES
        self.target_counts = target_counts or TARGET_COUNTS
        self.max_concurrent = max_concurrent or CONCURRENT_TESTS
        self.max_latency = max_latency or MAX_LATENCY
        self.max_ips = max_ips or MAX_IPS
        
        # 端口配置
        ports_config = target_ports or TARGET_PORTS
        if ',' in ports_config:
            self.target_ports = [p.strip() for p in ports_config.split(',')]
        else:
            self.target_ports = [ports_config.strip()]

        # NIP域名
        self.nip_domain = "ip.090227.xyz"
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 测试结果存储
        self.results: Dict[str, List[IPResult]] = defaultdict(list)
        
        # 已完成的计数器
        self.completed_counts: Dict[str, int] = defaultdict(int)
        
        # IP源列表
        self.ip_sources = [
            "official",    # CF官方列表
            "cm",          # CM整理列表
            "bestali",     # 最佳阿里云IP
            "proxyip",     # 反代IP列表
            "cfip",        # CFIP采集
            "as13335",     # AS13335 IP段
            "as209242",    # AS209242 IP段
            "as24429",     # AS24429 IP段
            "as35916",     # AS35916 IP段
            "as199524",    # AS199524 IP段
            "bestcfv4",    # 最佳CF IPv4
            "bestcfv6",    # 最佳CF IPv6
        ]

    async def __aenter__(self):
        """异步上下文管理器入口"""
        connector = aiohttp.TCPConnector(
            ssl=False,
            limit=100,
            limit_per_host=50,
            ttl_dns_cache=300,
            use_dns_cache=True
        )

        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=connector,
            trust_env=True
        )
        await self._get_nip_domain()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def _get_nip_domain(self) -> None:
        """获取NIP域名"""
        import os
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print("检测到GitHub Actions环境，使用GitHub优化域名")
            # GitHub Actions环境专用域名，确保可访问性
            self.nip_domain = "ip.sb"
            return

        # 备用域名列表
        backup_domains = ["nip.lfree.org", "ip.090227.xyz", "nip.top", "ip.sb"]
        self.nip_domain = backup_domains[0]
        print(f"📡 使用域名: {self.nip_domain}")
    
    async def get_all_ips(self) -> List[str]:
        """获取所有IP源的IP列表"""
        all_ips = set()
        
        # 如果是GitHub Actions环境，使用优化的IP源列表
        import os
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print("🔧 GitHub Actions环境：使用优化IP源列表")
            # 在GitHub环境中，优先使用可靠且可访问的IP源
            github_sources = ["official", "as13335", "as209242", "cm"]
            
            for ip_source in github_sources:
                print(f"正在获取 {ip_source} IP列表...")
                
                try:
                    ips = await self._get_ips_from_source(ip_source)
                    all_ips.update(ips)
                    print(f"✅ 从 {ip_source} 获取到 {len(ips)} 个IP，总计 {len(all_ips)} 个IP")
                    
                    # 如果已经获取到足够多的IP，可以提前停止
                    if len(all_ips) > 5000:
                        print("⚠️ IP数量已超过5000，停止获取更多IP")
                        break
                        
                except Exception as e:
                    print(f"❌ 获取 {ip_source} IP失败: {e}")
                    continue
        else:
            # 本地环境使用完整IP源列表
            for ip_source in self.ip_sources:
                print(f"正在获取 {ip_source} IP列表...")
                
                try:
                    ips = await self._get_ips_from_source(ip_source)
                    all_ips.update(ips)
                    print(f"✅ 从 {ip_source} 获取到 {len(ips)} 个IP，总计 {len(all_ips)} 个IP")
                    
                    # 如果已经获取到足够多的IP，可以提前停止
                    if len(all_ips) > 10000:
                        print("⚠️ IP数量已超过10000，停止获取更多IP")
                        break
                        
                except Exception as e:
                    print(f"❌ 获取 {ip_source} IP失败: {e}")
                    continue
        
        # 转换为列表并打乱顺序
        ip_list = list(all_ips)
        random.shuffle(ip_list)
        
        print(f"🎯 最终获取到 {len(ip_list)} 个IP用于测试")
        return ip_list
    
    async def _get_ips_from_source(self, ip_source: str) -> List[str]:
        """从指定源获取IP列表"""
        try:
            # 为GitHub Actions环境添加超时控制
            import os
            timeout_seconds = 10 if os.environ.get('GITHUB_ACTIONS') == 'true' else 30
            
            if ip_source == "cfip":
                url = "https://raw.githubusercontent.com/qianxiu203/cfipcaiji/refs/heads/main/ip.txt"
            elif ip_source == "as13335":
                url = "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/13335/ipv4-aggregated.txt"
            elif ip_source == "as209242":
                url = "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/209242/ipv4-aggregated.txt"
            elif ip_source == "as24429":
                url = "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/24429/ipv4-aggregated.txt"
            elif ip_source == "as35916":
                url = "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/35916/ipv4-aggregated.txt"
            elif ip_source == "as199524":
                url = "https://raw.githubusercontent.com/ipverse/asn-ip/master/as/199524/ipv4-aggregated.txt"
            elif ip_source == "cm":
                url = "https://raw.githubusercontent.com/cmliu/cmliu/main/CF-CIDR.txt"
            elif ip_source == "bestali":
                url = "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestAli/bestaliv4.txt"
            elif ip_source == "bestcfv4":
                url = "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/bestcfv4.txt"
            elif ip_source == "bestcfv6":
                url = "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/bestcfv6.txt"
            elif ip_source == "proxyip":
                return await self._get_proxy_ips(self.target_ports[0])
            else:  # official
                url = "https://www.cloudflare.com/ips-v4/"
            
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
                if response.status == 200:
                    text = await response.text()
                else:
                    # 使用默认CIDR列表
                    text = """173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22"""

            if ip_source in ["bestali", "bestcfv4", "bestcfv6", "cfip"]:
                lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
                valid_ips = []
                for line in lines:
                    if self._is_valid_ip(line):
                        valid_ips.append(line)
                    elif '/' in line:
                        try:
                            cidr_ips = self._generate_ips_from_cidr(line, 5)
                            valid_ips.extend(cidr_ips)
                        except:
                            continue
                return valid_ips
            elif ip_source.startswith("as"):
                # ASN源处理：直接IP列表
                lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
                valid_ips = []
                for line in lines:
                    if self._is_valid_ip(line):
                        valid_ips.append(line)
                    elif '/' in line:
                        try:
                            cidr_ips = self._generate_ips_from_cidr(line, 10)
                            valid_ips.extend(cidr_ips)
                        except:
                            continue
                return valid_ips
            else:
                cidrs = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
                return self._generate_ips_from_cidrs(cidrs, 1000)
                
        except Exception as e:
            print(f"获取 {ip_source} IP失败: {e}")
            return []
    
    async def _get_proxy_ips(self, target_port: str) -> List[str]:
        """获取反代IP列表"""
        try:
            url = "https://raw.githubusercontent.com/cmliu/ACL4SSR/main/baipiao.txt"
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []
                
                text = await response.text()
                lines = [line.strip() for line in text.split('\n') 
                        if line.strip() and not line.startswith('#')]
                
                valid_ips = []
                for line in lines:
                    parsed_ip = self._parse_proxy_ip_line(line, target_port)
                    if parsed_ip:
                        valid_ips.append(parsed_ip)
                
                return valid_ips
                
        except Exception as e:
            print(f"获取反代IP失败: {e}")
            return []
    
    def _parse_proxy_ip_line(self, line: str, target_port: str) -> Optional[str]:
        """解析反代IP行"""
        try:
            line = line.strip()
            if not line:
                return None
            
            ip = ""
            port = ""
            
            if '#' in line:
                parts = line.split('#', 1)
                main_part = parts[0].strip()
            else:
                main_part = line
            
            if ':' in main_part:
                ip_port_parts = main_part.split(':')
                if len(ip_port_parts) == 2:
                    ip = ip_port_parts[0].strip()
                    port = ip_port_parts[1].strip()
                else:
                    return None
            else:
                ip = main_part
                port = "443"
            
            if not self._is_valid_ip(ip):
                return None
            
            try:
                port_num = int(port)
                if port_num < 1 or port_num > 65535:
                    return None
            except ValueError:
                return None
            
            if port != target_port:
                return None
            
            return f"{ip}:{port}"
                
        except Exception:
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式"""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False
    
    def _generate_ips_from_cidrs(self, cidrs: List[str], max_ips: int) -> List[str]:
        """从CIDR列表生成IP"""
        ips = set()
        
        for cidr in cidrs:
            if len(ips) >= max_ips:
                break
            
            cidr_ips = self._generate_ips_from_cidr(cidr.strip(), 10)
            ips.update(cidr_ips)
        
        return list(ips)[:max_ips]
    
    def _generate_ips_from_cidr(self, cidr: str, count: int = 1) -> List[str]:
        """从单个CIDR生成IP"""
        try:
            network = ipaddress.IPv4Network(cidr, strict=False)
            max_hosts = network.num_addresses - 2
            
            if max_hosts <= 0:
                return []
            
            actual_count = min(count, max_hosts)
            ips = set()
            
            attempts = 0
            max_attempts = actual_count * 10
            
            while len(ips) < actual_count and attempts < max_attempts:
                random_offset = random.randint(1, max_hosts)
                random_ip = str(network.network_address + random_offset)
                ips.add(random_ip)
                attempts += 1
            
            return list(ips)

        except Exception as e:
            print(f"生成CIDR {cidr} IP失败: {e}")
            return []

    async def test_ips(self, ips: List[str]) -> Dict[str, List[IPResult]]:
        """测试IP列表，返回当前批次的结果"""
        print(f"🚀 开始测试 {len(ips)} 个IP，并发数: {self.max_concurrent}")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def test_with_semaphore(ip: str) -> Optional[IPResult]:
            async with semaphore:
                return await self.test_ip(ip)
        
        # 批量测试
        tasks = [test_with_semaphore(ip) for ip in ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        valid_results = []
        for result in results:
            if isinstance(result, IPResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                continue
        
        # 创建当前批次的结果字典
        batch_results = {}
        
        # 只保存目标国家的有效IP，并且当某个国家满足条件时不再保存该国家的IP
        for result in valid_results:
            # 只处理目标国家的IP
            if result.country in self.target_countries:
                # 检查该国家是否已经满足条件
                if not self._should_stop_testing(result.country):
                    # 该国家还未满足条件，保存到当前批次结果
                    if result.country not in batch_results:
                        batch_results[result.country] = []
                    batch_results[result.country].append(result)
                    
                    # 同时更新测试器的结果
                    if result.country not in self.results:
                        self.results[result.country] = []
                    self.results[result.country].append(result)
                    # 更新目标国家的计数
                    self.completed_counts[result.country] = len(self.results[result.country])
        
        print(f"✅ 测试完成，有效结果: {len(valid_results)} 个")
        return batch_results
    
    async def test_ip(self, ip: str) -> Optional[IPResult]:
        """测试单个IP"""
        timeout = 5.0
        
        # 测试所有指定的端口
        best_result = None
        
        for port_str in self.target_ports:
            try:
                port = int(port_str)
            except ValueError:
                continue
                
            # 解析IP格式
            parsed_ip = self._parse_ip_format(ip, port)
            if not parsed_ip:
                continue
            
            # 进行测试，最多重试2次
            for attempt in range(1, 3):
                result = await self._single_test(parsed_ip['host'], parsed_ip['port'], timeout)
                if result:
                    # 获取国家代码
                    country_code = await self._get_country_from_colo(result['colo'])
                    
                    # 应用延迟过滤
                    if result['latency'] > self.max_latency:
                        continue  # 跳过延迟过高的IP
                    
                    # 检查是否应该停止测试该国家的IP
                    if self._should_stop_testing(country_code):
                        return None  # 该国家已满足条件，跳过此IP
                    
                    # 记录最佳结果（延迟最低的端口）
                    if best_result is None or result['latency'] < best_result['latency']:
                        best_result = result
                        best_result['port'] = port
                        best_result['country'] = country_code
                    
                    # 如果找到一个有效结果，就继续测试下一个端口
                    break
                else:
                    if attempt < 2:
                        await asyncio.sleep(0.1)
        
        if best_result:
            return IPResult(
                ip=best_result['ip'],
                port=best_result['port'],
                latency=best_result['latency'],
                colo=best_result['colo'],
                country=best_result['country'],
                type=best_result['type']
            )
        
        return None
    
    def _parse_ip_format(self, ip_string: str, default_port: int) -> Optional[Dict]:
        """解析IP格式"""
        try:
            host = ""
            port = default_port
            
            # 处理注释部分
            main_part = ip_string
            if '#' in ip_string:
                parts = ip_string.split('#', 1)
                main_part = parts[0]
            
            # 处理端口部分
            if ':' in main_part:
                parts = main_part.split(':')
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    return None
            else:
                host = main_part
            
            # 验证IP格式
            if not host or not self._is_valid_ip(host.strip()):
                return None
            
            return {
                'host': host.strip(),
                'port': port,
                'comment': None
            }
        except Exception:
            return None
    
    async def _single_test(self, ip: str, port: int, timeout: float) -> Optional[Dict]:
        """单次IP测试"""
        try:
            # 构建测试URL
            parts = ip.split('.')
            hex_parts = [f"{int(part):02x}" for part in parts]
            nip = ''.join(hex_parts)
            test_url = f"https://{nip}.{self.nip_domain}:{port}/cdn-cgi/trace"

            start_time = time.time()

            async with self.session.get(
                test_url,
                timeout=aiohttp.ClientTimeout(total=timeout, connect=timeout/2),
                allow_redirects=False
            ) as response:
                if response.status == 200:
                    latency = (time.time() - start_time) * 1000
                    response_text = await response.text()

                    # 解析trace响应
                    trace_data = self._parse_trace_response(response_text)

                    if trace_data and trace_data.get('ip') and trace_data.get('colo'):
                        response_ip = trace_data['ip']
                        ip_type = 'official'

                        if ':' in response_ip or response_ip == ip:
                            ip_type = 'proxy'

                        return {
                            'ip': ip,
                            'port': port,
                            'latency': latency,
                            'colo': trace_data['colo'],
                            'type': ip_type,
                            'response_ip': response_ip
                        }

            return None

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return None
    
    def _parse_trace_response(self, response_text: str) -> Optional[Dict]:
        """解析trace响应"""
        try:
            lines = response_text.split('\n')
            data = {}

            for line in lines:
                trimmed_line = line.strip()
                if trimmed_line and '=' in trimmed_line:
                    key, value = trimmed_line.split('=', 1)
                    data[key] = value

            return data
        except Exception:
            return None
    
    async def _get_country_from_colo(self, colo: str) -> str:
        """从colo获取国家代码"""
        colo_to_country = {
            # 美国
            'ATL': 'US', 'BOS': 'US', 'BUF': 'US', 'CHI': 'US', 'DEN': 'US',
            'DFW': 'US', 'EWR': 'US', 'IAD': 'US', 'LAS': 'US', 'LAX': 'US',
            'MIA': 'US', 'MSP': 'US', 'ORD': 'US', 'PDX': 'US', 'PHX': 'US',
            'SAN': 'US', 'SEA': 'US', 'SJC': 'US', 'STL': 'US', 'IAH': 'US',
            
            # 中国大陆和地区
            'HKG': 'HK',  # 香港
            'TPE': 'TW',  # 台湾
            
            # 日本
            'NRT': 'JP', 'KIX': 'JP', 'ITM': 'JP',
            
            # 韩国
            'ICN': 'KR', 'GMP': 'KR',
            
            # 新加坡
            'SIN': 'SG',
            
            # 英国
            'LHR': 'GB', 'MAN': 'GB', 'EDI': 'GB',
            
            # 德国
            'FRA': 'DE', 'DUS': 'DE', 'HAM': 'DE', 'MUC': 'DE',
            
            # 法国
            'CDG': 'FR', 'MRS': 'FR',
            
            # 荷兰
            'AMS': 'NL',
            
            # 澳大利亚
            'SYD': 'AU', 'MEL': 'AU', 'PER': 'AU', 'BNE': 'AU',
            
            # 加拿大
            'YYZ': 'CA', 'YVR': 'CA', 'YUL': 'CA',
            
            # 巴西
            'GRU': 'BR', 'GIG': 'BR',
            
            # 印度
            'BOM': 'IN', 'DEL': 'IN',
            
            # 其他常见colo
            'MAD': 'ES', 'MXP': 'IT', 'ARN': 'SE', 'CPH': 'DK',
            'WAW': 'PL', 'PRG': 'CZ', 'VIE': 'AT', 'ZRH': 'CH',
        }
        
        # 提取前三个字母作为colo代码
        colo_code = colo[:3].upper()
        return colo_to_country.get(colo_code, "UNKNOWN")
    
    def _should_stop_testing(self, country_code: str) -> bool:
        """检查是否应该停止测试特定国家的IP"""
        # 如果指定了国家代码，检查该国家是否已满足条件
        if country_code and country_code in self.target_countries:
            current_count = len(self.results.get(country_code, []))
            target_count = self.target_counts.get(country_code, 0)
            
            # 如果该国家已经达到目标数量，停止测试该国家的IP
            if current_count >= target_count:
                return True
        
        # 如果没有指定国家代码，检查是否所有目标国家都已满足条件
        if not country_code:
            for country in self.target_countries:
                current_count = len(self.results.get(country, []))
                target_count = self.target_counts.get(country, 0)
                
                # 如果某个国家还没有达到目标数量，继续测试
                if current_count < target_count:
                    return False
            
            # 所有目标国家都满足条件，停止测试
            print("🎯 所有目标国家已满足条件，停止测试")
            return True
        
        # 指定了国家代码但该国家未满足条件，继续测试
        return False
    
    def save_results_to_files(self, output_dir: str = "ip_results") -> None:
        """将结果保存到对应国家的txt文件"""
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"💾 正在保存结果到目录: {output_path.absolute()}")
        
        # 只保存目标国家的结果
        for country in self.target_countries:
            ip_results = self.results.get(country, [])
            if not ip_results:
                continue
                
            # 按延迟排序
            ip_results.sort(key=lambda x: x.latency)
            
            # 只保存目标数量的IP
            target_count = self.target_counts.get(country, 0)
            if target_count > 0:
                ip_results = ip_results[:target_count]
            
            # 创建国家文件
            file_path = output_path / f"{country}_ips.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # 直接写入IP数据，不包含注释头
                for result in ip_results:
                    f.write(f"{result.to_display_format()}\n")
            
            print(f"✅ {country}: 保存了 {len(ip_results)} 个IP到 {file_path.name}")
        
        # 创建汇总文件
        summary_path = output_path / "summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("# IP测试汇总报告\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            total_count = 0
            # 只汇总目标国家的结果
            for country in self.target_countries:
                ip_results = self.results.get(country, [])
                if ip_results:
                    count = len(ip_results)
                    total_count += count
                    avg_latency = sum(r.latency for r in ip_results) / count
                    f.write(f"{country}: {count} 个IP，平均延迟 {avg_latency:.1f}ms\n")
            
            f.write(f"\n总计: {total_count} 个有效IP")
        
        print(f"📊 汇总报告已保存到 {summary_path.name}")



async def main():
    """主函数"""
    # 始终使用用户配置区域的参数作为默认值
    parser = argparse.ArgumentParser(description='IP延迟测试脚本')
    
    parser.add_argument('--countries', type=str, default=','.join(TARGET_COUNTRIES),
                        help='目标国家列表，逗号分隔')
    parser.add_argument('--counts', type=str, default=','.join(str(TARGET_COUNTS.get(c, 3)) for c in TARGET_COUNTRIES),
                        help='每个国家的目标IP数量，逗号分隔')
    parser.add_argument('--concurrent', type=int, default=CONCURRENT_TESTS,
                        help='并发测试数量')
    parser.add_argument('--ports', type=str, default=TARGET_PORTS,
                        help='测试端口，逗号分隔')
    parser.add_argument('--max-ips', type=int, default=MAX_IPS,
                        help='最大IP数量限制（0表示无限制）')
    parser.add_argument('--max-latency', type=int, default=MAX_LATENCY,
                        help='最大延迟阈值（毫秒）')
    
    parser.add_argument('--output', type=str, default='ip_results',
                        help='输出目录')
    
    args = parser.parse_args()
    
    # 解析参数
    countries = [c.strip().upper() for c in args.countries.split(',')]
    count_list = [int(c.strip()) for c in args.counts.split(',')]
    
    # 确保国家和数量列表长度一致
    if len(countries) != len(count_list):
        print("❌ 错误：国家和数量列表长度不一致")
        return
    
    target_counts = dict(zip(countries, count_list))
    
    print("🎯 IP延迟测试脚本启动")
    print(f"目标国家: {', '.join(countries)}")
    print(f"目标数量: {target_counts}")
    print(f"并发数量: {args.concurrent}")
    print(f"测试端口: {args.ports}")
    print("-" * 50)
    
    # 创建测试器
    async with IPTester(
        target_countries=countries,
        target_counts=target_counts,
        max_concurrent=args.concurrent,
        target_ports=args.ports,
        max_latency=args.max_latency,
        max_ips=args.max_ips
    ) as tester:
        
        # 获取IP列表
        ips = await tester.get_all_ips()
        
        if not ips:
            print("❌ 无法获取IP列表，程序退出")
            return
        
        # 应用最大IP限制
        if args.max_ips > 0 and len(ips) > args.max_ips:
            print(f"📊 应用最大IP限制: {args.max_ips}")
            ips = ips[:args.max_ips]
        
        # 分批测试所有IP，批次大小等于并发测试数量
        batch_size = args.concurrent
        total_batches = (len(ips) + batch_size - 1) // batch_size
        
        print(f"🔄 开始分批测试 {len(ips)} 个IP，共 {total_batches} 批，每批 {batch_size} 个IP（与并发数一致）")
        
        all_results = {}
        should_stop = False
        
        for batch_index in range(total_batches):
            start_idx = batch_index * batch_size
            end_idx = min((batch_index + 1) * batch_size, len(ips))
            batch_ips = ips[start_idx:end_idx]
            
            print(f"\n📦 正在测试第 {batch_index + 1}/{total_batches} 批，本批 {len(batch_ips)} 个IP")
            
            # 测试当前批次
            batch_results = await tester.test_ips(batch_ips)
            
            # 合并结果
            for country, ip_results in batch_results.items():
                if country not in all_results:
                    all_results[country] = []
                all_results[country].extend(ip_results)
            
            # 更新测试器的结果，用于条件检查
            tester.results = all_results
            
            # 检查是否满足停止条件
            should_stop = tester._should_stop_testing("")
            
            current_total = sum(len(r) for r in all_results.values())
            print(f"✅ 第 {batch_index + 1} 批测试完成，当前累计有效IP: {current_total}")
            
            # 显示当前各国家进度
            print("📊 当前进度:")
            for country in tester.target_countries:
                current_count = len(all_results.get(country, []))
                target_count = tester.target_counts.get(country, 0)
                status = "✅" if current_count >= target_count else "⏳"
                print(f"  {status} {country}: {current_count}/{target_count}")
            
            # 每批测试完成后立即保存结果（实时保存）
            print(f"💾 实时保存第 {batch_index + 1} 批测试结果...")
            tester.results = all_results
            tester.save_results_to_files(args.output)
            
            # 如果满足条件，提前停止
            if should_stop:
                print(f"🎯 所有目标国家已满足条件，提前停止测试（第 {batch_index + 1} 批）")
                break
        
        # 最终保存结果（确保所有结果都被保存）
        print("💾 保存最终测试结果...")
        tester.results = all_results
        tester.save_results_to_files(args.output)
        
        # 显示统计信息
        print("\n📊 测试统计:")
        for country in tester.target_countries:
            ip_results = all_results.get(country, [])
            if ip_results:
                avg_latency = sum(r.latency for r in ip_results) / len(ip_results)
                print(f"  {country}: {len(ip_results)} 个IP，平均延迟 {avg_latency:.1f}ms")
        
        # 只计算目标国家的总IP数
        total_count = sum(len(all_results.get(country, [])) for country in tester.target_countries)
        print(f"总计: {total_count} 个有效IP")

if __name__ == "__main__":
    asyncio.run(main())
