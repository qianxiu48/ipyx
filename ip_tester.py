#!/usr/bin/env python3
"""
IP延迟测试脚本 - 多国家IP测试与分类存储
基于Cloudflare IP优选脚本改写
"""

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
    
    def __init__(self, target_countries: List[str] = None, max_concurrent: int = 10, 
                 target_counts: Dict[str, int] = None, target_ports: str = "443"):
        # 目标国家列表
        self.target_countries = target_countries or ["US"]
        
        # 每个国家的目标IP数量
        self.target_counts = target_counts or {country: 10 for country in self.target_countries}
        
        # 并发数量
        self.max_concurrent = max_concurrent
        
        # 支持多个端口
        if ',' in target_ports:
            self.target_ports = [p.strip() for p in target_ports.split(',')]
        else:
            self.target_ports = [target_ports.strip()]

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
            connector=connector
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
            print("检测到GitHub Actions环境，使用预设域名")
            self.nip_domain = "nip.lfree.org"
            return

        # 备用域名列表
        backup_domains = ["nip.lfree.org", "ip.090227.xyz", "nip.top", "ip.sb"]
        self.nip_domain = backup_domains[0]
        print(f"📡 使用域名: {self.nip_domain}")
    
    async def get_all_ips(self) -> List[str]:
        """获取所有IP源的IP列表"""
        all_ips = set()
        
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
            
            async with self.session.get(url) as response:
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
        """测试IP列表"""
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
        
        # 按国家分类
        for result in valid_results:
            if result.country in self.target_countries:
                self.results[result.country].append(result)
                self.completed_counts[result.country] = len(self.results[result.country])
        
        print(f"✅ 测试完成，有效结果: {len(valid_results)} 个")
        return self.results
    
    async def test_ip(self, ip: str) -> Optional[IPResult]:
        """测试单个IP"""
        timeout = 5.0
        
        # 解析IP格式
        parsed_ip = self._parse_ip_format(ip, int(self.target_ports[0]))
        if not parsed_ip:
            return None
        
        # 进行测试，最多重试2次
        for attempt in range(1, 3):
            result = await self._single_test(parsed_ip['host'], parsed_ip['port'], timeout)
            if result:
                # 获取国家代码
                country_code = await self._get_country_from_colo(result['colo'])
                
                # 检查延迟是否超过300ms
                if result['latency'] > 300:
                    print(f"⚠️ 跳过延迟过高的IP: {parsed_ip['host']}:{parsed_ip['port']} - {result['latency']:.0f}ms")
                    return None
                
                # 检查是否满足停止条件
                if self._should_stop_testing(country_code):
                    return None
                
                return IPResult(
                    ip=parsed_ip['host'],
                    port=parsed_ip['port'],
                    latency=result['latency'],
                    colo=result['colo'],
                    country=country_code,
                    type=result['type']
                )
            else:
                if attempt < 2:
                    await asyncio.sleep(0.1)
        
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
        """检查是否应该停止测试"""
        # 在GitHub Actions环境中，不根据目标数量停止测试
        # 而是运行所有批次的IP，让GitHub Actions控制整体流程
        import os
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            return False
        
        # 本地运行时，使用原有的停止条件
        if country_code not in self.target_countries:
            return False
        
        current_count = self.completed_counts.get(country_code, 0)
        target_count = self.target_counts.get(country_code, 0)
        
        return current_count >= target_count
    
    def save_results_to_files(self, output_dir: str = "ip_results") -> None:
        """将结果保存到对应国家的txt文件"""
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print(f"💾 正在保存结果到目录: {output_path.absolute()}")
        
        # 过滤延迟超过300ms的IP
        filtered_results = {}
        for country, ip_results in self.results.items():
            filtered_ips = [r for r in ip_results if r.latency <= 300]
            if filtered_ips:
                filtered_results[country] = filtered_ips
        
        # 更新结果
        self.results = filtered_results
        
        for country, ip_results in self.results.items():
            if not ip_results:
                continue
                
            # 按延迟排序
            ip_results.sort(key=lambda x: x.latency)
            
            # 创建国家文件
            file_path = output_path / f"{country}_ips.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # 直接写入IP数据，不包含注释头
                for result in ip_results:
                    f.write(f"{result.to_display_format()}\n")
            
            print(f"✅ {country}: 保存了 {len(ip_results)} 个IP到 {file_path.name} (已过滤延迟>300ms的节点)")
        
        # 创建汇总文件
        summary_path = output_path / "summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("# IP测试汇总报告\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("# 已过滤延迟超过300ms的节点\n\n")
            
            total_count = 0
            for country, ip_results in self.results.items():
                if ip_results:
                    count = len(ip_results)
                    total_count += count
                    avg_latency = sum(r.latency for r in ip_results) / count
                    f.write(f"{country}: {count} 个IP，平均延迟 {avg_latency:.1f}ms\n")
            
            f.write(f"\n总计: {total_count} 个有效IP (延迟≤300ms)")
        
        print(f"📊 汇总报告已保存到 {summary_path.name}")

def load_config_from_yaml():
    """从GitHub Actions配置文件加载参数"""
    config_path = Path(__file__).parent / ".github" / "workflows" / "ip_test.yml"
    
    if not config_path.exists():
        return None
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 提取workflow_dispatch的inputs配置
        inputs = config_data.get('on', {}).get('workflow_dispatch', {}).get('inputs', {})
        
        config = {
            'countries': inputs.get('countries', {}).get('default', 'US'),
            'counts': inputs.get('counts', {}).get('default', '3'),
            'batch_size': inputs.get('batch_size', {}).get('default', '20'),
            'max_ips': inputs.get('max_ips', {}).get('default', '0'),
            'concurrent': inputs.get('concurrent', {}).get('default', '10'),
            'ports': inputs.get('ports', {}).get('default', '443')
        }
        
        print(f"📋 从配置文件加载参数: {config}")
        return config
        
    except Exception as e:
        print(f"⚠️ 加载配置文件失败: {e}")
        return None

async def main():
    """主函数"""
    # 首先尝试从配置文件加载参数
    config = load_config_from_yaml()
    
    parser = argparse.ArgumentParser(description='IP延迟测试脚本')
    
    # 如果配置文件存在，使用配置文件中的默认值
    if config:
        parser.add_argument('--countries', type=str, default=config['countries'],
                            help='目标国家列表，逗号分隔')
        parser.add_argument('--counts', type=str, default=config['counts'],
                            help='每个国家的目标IP数量，逗号分隔')
        parser.add_argument('--concurrent', type=int, default=int(config['concurrent']),
                            help='并发测试数量')
        parser.add_argument('--ports', type=str, default=config['ports'],
                            help='测试端口，逗号分隔')
        parser.add_argument('--batch-size', type=int, default=int(config['batch_size']),
                            help='每批处理的IP数量（0表示不分批）')
        parser.add_argument('--max-ips', type=int, default=int(config['max_ips']),
                            help='最大IP数量限制（0表示无限制）')
    else:
        # 如果配置文件不存在，使用硬编码默认值
        parser.add_argument('--countries', type=str, default='CN,US,JP,HK,TW,SG,KR',
                            help='目标国家列表，逗号分隔')
        parser.add_argument('--counts', type=str, default='10,10,10,10,10,10,10',
                            help='每个国家的目标IP数量，逗号分隔')
        parser.add_argument('--concurrent', type=int, default=10,
                            help='并发测试数量')
        parser.add_argument('--ports', type=str, default='443',
                            help='测试端口，逗号分隔')
        parser.add_argument('--batch-size', type=int, default=0,
                            help='每批处理的IP数量（0表示不分批）')
        parser.add_argument('--max-ips', type=int, default=0,
                            help='最大IP数量限制（0表示无限制）')
    
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
        target_ports=args.ports
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
        
        # 自动分批处理逻辑
        if args.batch_size > 0:
            total_batches = (len(ips) + args.batch_size - 1) // args.batch_size
            all_results = []
            
            for batch_index in range(total_batches):
                start_idx = batch_index * args.batch_size
                end_idx = min(start_idx + args.batch_size, len(ips))
                batch_ips = ips[start_idx:end_idx]
                
                print(f"\n📦 处理批次: 第 {batch_index + 1}/{total_batches} 批")
                print(f"📊 处理IP范围: {start_idx + 1}-{end_idx} (共{len(batch_ips)}个)")
                
                # 测试当前批次的IP
                batch_results = await tester.test_ips(batch_ips)
                all_results.extend(batch_results)
                
                # 检查是否已达到目标数量
                if tester._should_stop_testing('US'):  # 假设主要测试US
                    print(f"✅ 已达到目标数量，停止测试")
                    break
            
            results = all_results
        else:
            # 不分批，测试所有IP
            results = await tester.test_ips(ips)
        
        # 保存结果
        tester.save_results_to_files(args.output)
        
        # 显示统计信息
        print("\n📊 测试统计:")
        for country, ip_results in results.items():
            if ip_results:
                avg_latency = sum(r.latency for r in ip_results) / len(ip_results)
                print(f"  {country}: {len(ip_results)} 个IP，平均延迟 {avg_latency:.1f}ms")
        
        total_count = sum(len(r) for r in results.values())
        print(f"总计: {total_count} 个有效IP")
        
        print(f"\n✅ 测试完成，结果已保存到: {args.output}")

if __name__ == "__main__":
    asyncio.run(main())