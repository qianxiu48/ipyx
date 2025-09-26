#!/usr/bin/env python3
"""
结果合并脚本 - 合并分批运行的IP测试结果
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict
from dataclasses import dataclass

@dataclass
class IPResult:
    """IP测试结果数据类"""
    ip: str
    port: int
    latency: float
    colo: str
    country: str
    type: str
    
    def to_display_format(self) -> str:
        """转换为显示格式"""
        type_text = "官方优选" if self.type == "official" else "反代优选"
        return f"{self.ip}:{self.port}#{self.country} {type_text} {self.latency:.0f}ms"

def parse_ip_line(line: str) -> IPResult:
    """解析IP结果行"""
    try:
        # 匹配格式: IP:端口#国家 类型 延迟ms
        pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)#([A-Z]{2})\s+(官方优选|反代优选)\s+(\d+)ms'
        match = re.match(pattern, line.strip())
        
        if match:
            ip, port, country, ip_type, latency = match.groups()
            return IPResult(
                ip=ip,
                port=int(port),
                latency=float(latency),
                colo="",  # 合并时不需要colo信息
                country=country,
                type="official" if ip_type == "官方优选" else "proxy"
            )
    except Exception as e:
        print(f"解析行失败: {line.strip()} - {e}")
    
    return None

def merge_batch_results(base_dir: str = "ip_results", output_dir: str = "merged_results") -> None:
    """合并分批运行的结果"""
    base_path = Path(base_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"🔍 在目录 {base_path.absolute()} 中查找批次结果...")
    
    # 查找所有批次目录
    batch_dirs = []
    for item in base_path.iterdir():
        if item.is_dir() and item.name.startswith("ip_results_batch_"):
            batch_dirs.append(item)
    
    if not batch_dirs:
        print("❌ 未找到批次结果目录")
        return
    
    batch_dirs.sort(key=lambda x: int(x.name.split('_')[-1]))
    print(f"📦 找到 {len(batch_dirs)} 个批次结果")
    
    # 按国家合并结果
    country_results = defaultdict(list)
    seen_ips = set()  # 用于去重
    
    for batch_dir in batch_dirs:
        batch_index = batch_dir.name.split('_')[-1]
        print(f"📂 处理批次 {batch_index}...")
        
        # 读取每个国家的文件
        for country_file in batch_dir.glob("*_ips.txt"):
            country = country_file.stem.split('_')[0]
            
            with open(country_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    result = parse_ip_line(line)
                    if result:
                        # 去重检查
                        ip_key = f"{result.ip}:{result.port}"
                        if ip_key not in seen_ips:
                            seen_ips.add(ip_key)
                            country_results[country].append(result)
    
    # 按国家保存合并结果
    print(f"\n💾 保存合并结果到 {output_path.absolute()}")
    
    total_count = 0
    for country, results in country_results.items():
        if not results:
            continue
        
        # 按延迟排序
        results.sort(key=lambda x: x.latency)
        
        # 保存到文件
        file_path = output_path / f"{country}_ips.txt"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            # 写入文件头
            f.write(f"# {country} IP列表 - 合并测试结果\n")
            f.write(f"# 生成时间: {Path(__file__).stat().st_mtime}\n")
            f.write(f"# 总数量: {len(results)} 个\n")
            f.write(f"# 来源批次: {len(batch_dirs)} 个\n\n")
            
            # 写入IP数据
            for result in results:
                f.write(f"{result.to_display_format()}\n")
        
        print(f"✅ {country}: 合并了 {len(results)} 个IP")
        total_count += len(results)
    
    # 创建汇总文件
    summary_path = output_path / "summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# IP测试合并汇总报告\n")
        f.write(f"# 合并批次: {len(batch_dirs)} 个\n")
        f.write(f"# 生成时间: {Path(__file__).stat().st_mtime}\n\n")
        
        for country, results in country_results.items():
            if results:
                count = len(results)
                avg_latency = sum(r.latency for r in results) / count
                f.write(f"{country}: {count} 个IP，平均延迟 {avg_latency:.1f}ms\n")
        
        f.write(f"\n总计: {total_count} 个不重复有效IP")
    
    print(f"\n📊 合并完成: {total_count} 个不重复IP")
    print(f"📁 结果保存在: {output_path.absolute()}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='IP测试结果合并脚本')
    parser.add_argument('--input', type=str, default='ip_results',
                       help='输入目录，包含批次结果')
    parser.add_argument('--output', type=str, default='merged_results',
                       help='输出目录')
    
    args = parser.parse_args()
    
    print("🔄 IP测试结果合并脚本")
    print("-" * 50)
    
    merge_batch_results(args.input, args.output)
    
    print("\n🎉 合并完成！")

if __name__ == "__main__":
    main()