import requests
import ipaddress
import random
import traceback
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# 环境变量读取
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TEST_URL_TEMPLATE = os.environ.get("TEST_URL_TEMPLATE", "http://{ip}/")
EXPECTED_STATUS_CODE = int(os.environ.get("EXPECTED_STATUS_CODE", "403"))
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "5"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "5"))
GENERATE_IPV6 = os.environ.get("GENERATE_IPV6", "true").lower() == "true"
IPV6_COUNT = int(os.environ.get("IPV6_COUNT", "10"))

def get_cloudflare_ips():
    """从Cloudflare获取IPv4和IPv6地址范围"""
    ipv4_url = "https://www.cloudflare.com/ips-v4/"
    ipv6_url = "https://raw.githubusercontent.com/leung7963/CFIPS/main/cfipv6"
    
    ipv4_cidrs = []
    ipv6_cidrs = []
    
    try:
        # 获取IPv4地址范围
        response = requests.get(ipv4_url, timeout=10)
        response.raise_for_status()
        ipv4_cidrs = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"获取到 {len(ipv4_cidrs)} 个IPv4 CIDR范围")
    except requests.RequestException as e:
        print(f"获取IPv4地址范围失败: {e}")
    
    try:
        # 获取IPv6地址范围
        response = requests.get(ipv6_url, timeout=10)
        response.raise_for_status()
        ipv6_cidrs = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"获取到 {len(ipv6_cidrs)} 个IPv6 CIDR范围")
    except requests.RequestException as e:
        print(f"获取IPv6地址范围失败: {e}")
    
    return ipv4_cidrs, ipv6_cidrs

def generate_random_ip_from_cidr(cidr, is_ipv6=False):
    """从CIDR范围内生成随机IP地址"""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        
        # 检查网络类型是否匹配
        if is_ipv6 and network.version != 6:
            print(f"警告: CIDR {cidr} 不是IPv6地址")
            return None
        elif not is_ipv6 and network.version != 4:
            print(f"警告: CIDR {cidr} 不是IPv4地址")
            return None
        
        # 计算网络地址和广播地址
        network_address = int(network.network_address)
        broadcast_address = int(network.broadcast_address)
        
        # 生成网络地址和广播地址之间的随机IP
        if network.prefixlen <= (126 if is_ipv6 else 30):  # IPv6 /126, IPv4 /30
            start_ip = network_address + 1
            end_ip = broadcast_address - 1
        else:  # 对于小网络，特殊处理
            start_ip = network_address
            end_ip = broadcast_address
        
        # 生成随机IP
        random_ip_int = random.randint(start_ip, end_ip)
        
        if is_ipv6:
            random_ip = ipaddress.IPv6Address(random_ip_int)
        else:
            random_ip = ipaddress.IPv4Address(random_ip_int)
        
        return str(random_ip)
    except Exception as e:
        print(f"从CIDR {cidr} 生成IP失败: {e}")
        return None

def test_ip_status(ip_address, test_url_template, expected_status_code=403):
    """测试IP地址是否返回指定状态码"""
    try:
        # 判断是否为IPv6地址
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            is_ipv6 = ip_obj.version == 6
        except:
            is_ipv6 = ':' in ip_address
        
        # 构建测试URL
        if is_ipv6:
            # IPv6地址在URL中需要用方括号括起来
            test_url = test_url_template.format(ip=f"[{ip_address}]")
        else:
            test_url = test_url_template.format(ip=ip_address)
        
        # 发送HTTP请求
        response = requests.get(
            test_url, 
            timeout=REQUEST_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            allow_redirects=False  # 不跟随重定向
        )
        
        status_code = response.status_code
        print(f"测试 IP {ip_address}: 状态码 {status_code}, URL: {test_url}")
        
        # 检查是否为期望的状态码
        return status_code == expected_status_code, status_code, response.reason, is_ipv6
        
    except requests.exceptions.Timeout:
        print(f"测试 IP {ip_address}: 请求超时")
        return False, 0, "Timeout", False
    except requests.exceptions.ConnectionError:
        print(f"测试 IP {ip_address}: 连接错误")
        return False, 0, "Connection Error", False
    except Exception as e:
        print(f"测试 IP {ip_address} 时发生异常: {e}")
        return False, 0, str(e), False

def generate_and_test_ips(num_ips=10, is_ipv6=False):
    """生成并测试IP地址，确保返回指定状态码"""
    cidr_type = "IPv6" if is_ipv6 else "IPv4"
    print(f"正在获取Cloudflare {cidr_type}地址范围...")
    
    ipv4_cidrs, ipv6_cidrs = get_cloudflare_ips()
    cidrs = ipv6_cidrs if is_ipv6 else ipv4_cidrs
    
    if not cidrs:
        print(f"无法获取{cidr_type}地址范围")
        return []
    
    print(f"获取到 {len(cidrs)} 个{cidr_type} CIDR范围")
    print(f"测试配置: 期望状态码={EXPECTED_STATUS_CODE}, URL模板={TEST_URL_TEMPLATE}")
    
    # 存储符合条件的IP地址
    qualified_ips = []
    # 存储所有尝试过的IP及其结果
    attempted_ips = {}
    # 记录总尝试次数
    total_attempts = 0
    max_total_attempts = num_ips * 10  # 防止无限循环
    
    while len(qualified_ips) < num_ips and total_attempts < max_total_attempts:
        # 随机选择一个CIDR范围
        random_cidr = random.choice(cidrs)
        
        # 从该范围生成随机IP
        random_ip = generate_random_ip_from_cidr(random_cidr, is_ipv6)
        
        if not random_ip:
            total_attempts += 1
            continue
        
        # 检查是否已经尝试过这个IP
        if random_ip in attempted_ips:
            total_attempts += 1
            continue
        
        # 测试IP
        is_qualified, status_code, reason, detected_ipv6 = test_ip_status(
            random_ip, 
            TEST_URL_TEMPLATE, 
            EXPECTED_STATUS_CODE
        )
        
        # 记录尝试结果
        attempted_ips[random_ip] = {
            'qualified': is_qualified,
            'status_code': status_code,
            'reason': reason,
            'cidr': random_cidr
        }
        total_attempts += 1
        
        if is_qualified:
            qualified_ips.append(random_ip)
            print(f"✓ 找到合格{cidr_type} IP {len(qualified_ips)}/{num_ips}: {random_ip} (来自范围: {random_cidr})")
        else:
            print(f"✗ {cidr_type} IP不合格: {random_ip} (状态码: {status_code}, 原因: {reason})")
    
    # 如果循环结束但未找到足够数量的合格IP
    if len(qualified_ips) < num_ips:
        print(f"警告: 只找到 {len(qualified_ips)} 个合格{cidr_type} IP，目标为 {num_ips} 个")
        print(f"总尝试次数: {total_attempts}, 尝试过的IP数量: {len(attempted_ips)}")
        
        # 打印一些统计信息
        status_counts = {}
        for ip_info in attempted_ips.values():
            status = ip_info['status_code']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"{cidr_type}状态码统计:")
        for status, count in status_counts.items():
            print(f"  状态码 {status}: {count} 个IP")
    
    return qualified_ips

def generate_random_ips_with_retry(num_ips=10, is_ipv6=False):
    """生成指定数量的随机IP地址，如果不符合要求则重试"""
    return generate_and_test_ips(num_ips, is_ipv6)

def get_dns_records(name, record_type=None):
    """获取 DNS 记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        print("缺少必要的环境变量")
        return []
        
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    records_info = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            all_records = response.json()['result']
            for record in all_records:
                if record['name'] == name:
                    if record_type is None or record['type'] == record_type:
                        records_info.append({
                            'id': record['id'],
                            'type': record['type'],
                            'content': record.get('content', ''),
                            'name': record['name']
                        })
            return records_info
        else:
            print('获取DNS记录失败:', response.text)
    except Exception as e:
        print(f"获取DNS记录失败: {e}")
    return []

def delete_dns_record(record_id):
    """删除 DNS 记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        print("缺少必要的环境变量")
        return False, "删除失败: 缺少API配置"
    
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'

    try:
        response = requests.delete(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"DNS删除成功: ---- 时间: " + str(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + f" ---- 记录ID: {record_id}")
                return True, f"记录ID: {record_id} 删除成功"
            else:
                errors = result.get('errors', [])
                error_msg = ', '.join([str(err) for err in errors])
                print(f"DNS删除失败: ---- 时间: " + str(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + f" ---- 错误信息: {error_msg}")
                return False, f"记录ID: {record_id} 删除失败: {error_msg}"
        else:
            print(f"DNS删除失败: ---- 时间: " + str(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- 错误信息: " + str(response.text))
            return False, f"记录ID: {record_id} 删除失败"
    except Exception as e:
        traceback.print_exc()
        print(f"DNS删除异常: {e}")
        return False, f"记录ID: {record_id} 删除异常"

def create_dns_record(name, ip_address, record_type='A', ttl=86400):
    """创建 DNS 记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        print("缺少必要的环境变量")
        return "创建失败: 缺少API配置"
    
    # 检查IP地址类型是否匹配记录类型
    try:
        ip_obj = ipaddress.ip_address(ip_address)
        if record_type == 'A' and ip_obj.version != 4:
            return f"IP地址 {ip_address} 不是IPv4地址，无法创建A记录"
        elif record_type == 'AAAA' and ip_obj.version != 6:
            return f"IP地址 {ip_address} 不是IPv6地址，无法创建AAAA记录"
    except ValueError:
        return f"IP地址 {ip_address} 格式无效"
    
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    data = {
        'type': record_type,
        'name': name,
        'content': ip_address,
        'ttl': ttl,
        'proxied': False  # 默认开启代理
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"DNS创建成功: ---- 时间: " + str(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + f" ---- {record_type}记录：{ip_address}")
                return f"{record_type}记录: {ip_address} 解析 {name} 成功"
            else:
                errors = result.get('errors', [])
                error_msg = ', '.join([str(err) for err in errors])
                print(f"DNS创建失败: ---- 时间: " + str(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + f" ---- 错误信息: {error_msg}")
                return f"{record_type}记录: {ip_address} 解析 {name} 失败: {error_msg}"
        else:
            print(f"DNS创建失败: ---- 时间: " + str(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + " ---- 错误信息: " + str(response.text))
            return f"{record_type}记录: {ip_address} 解析 {name} 失败"
    except Exception as e:
        traceback.print_exc()
        print(f"DNS创建异常: {e}")
        return f"{record_type}记录: {ip_address} 解析 {name} 异常"

def delete_all_dns_records(name, record_type=None):
    """删除指定域名的所有DNS记录或特定类型的记录"""
    if not CF_API_TOKEN or not CF_ZONE_ID or not name:
        print("缺少必要的环境变量")
        return [], "删除失败: 缺少API配置"
    
    print(f"开始删除 {name} 的DNS记录" + (f"（类型: {record_type}）" if record_type else ""))
    
    # 获取要删除的记录
    records_to_delete = get_dns_records(name, record_type)
    
    if not records_to_delete:
        print(f"没有找到 {name} 的DNS记录" + (f"（类型: {record_type}）" if record_type else ""))
        return [], f"没有找到 {name} 的DNS记录"
    
    delete_results = []
    deleted_count = 0
    
    for record in records_to_delete:
        record_id = record['id']
        record_type = record['type']
        record_content = record['content']
        
        success, message = delete_dns_record(record_id)
        delete_results.append(message)
        
        if success:
            deleted_count += 1
            print(f"已删除 {record_type} 记录: {record_content}")
    
    summary = f"删除完成: 成功删除 {deleted_count}/{len(records_to_delete)} 条记录"
    print(summary)
    
    return delete_results, summary

def push_notification(content):
    """Telegram消息推送"""
    if not BOT_TOKEN or not CHAT_ID:
        print("未配置BOT_TOKEN或CHAT_ID，跳过消息推送")
        return
    
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {
        "chat_id": CHAT_ID,
        "title": "Cloudflare IP优选及DNS更新",
        "text": content,
        "parse_mode": "Markdown"
    }
    
    try:
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=body, headers=headers)
        if response.status_code == 200:
            print("消息推送成功")
        else:
            print(f"消息推送失败: {response.text}")
    except Exception as e:
        print(f"消息推送异常: {e}")

def save_ips_to_file(ip_list, filename='cfip.txt'):
    """将IP地址保存到文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            for ip in ip_list:
                file.write(ip + '\n')
        print(f"IP地址已保存到 {filename} 文件中")
        return True
    except Exception as e:
        print(f"保存IP地址到文件失败: {e}")
        return False

def save_ipv6_to_file(ip_list, filename='cfipv6.txt'):
    """将IPv6地址保存到文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            for ip in ip_list:
                file.write(ip + '\n')
        print(f"IPv6地址已保存到 {filename} 文件中")
        return True
    except Exception as e:
        print(f"保存IPv6地址到文件失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("Cloudflare IP优选工具 - 支持IPv4和IPv6")
    print("=" * 60)
    print(f"测试配置:")
    print(f"  - 测试URL模板: {TEST_URL_TEMPLATE}")
    print(f"  - 期望状态码: {EXPECTED_STATUS_CODE}")
    print(f"  - 最大重试次数: {MAX_RETRY_ATTEMPTS}")
    print(f"  - 请求超时: {REQUEST_TIMEOUT}秒")
    print(f"  - 生成IPv6: {GENERATE_IPV6}")
    if GENERATE_IPV6:
        print(f"  - IPv6数量: {IPV6_COUNT}")
    
    # 生成并测试IPv4地址
    num_ipv4 = 10
    print(f"\n正在生成并测试 {num_ipv4} 个IPv4地址...")
    print(f"要求IP地址返回状态码: {EXPECTED_STATUS_CODE}")
    
    generated_ipv4 = generate_random_ips_with_retry(num_ips=num_ipv4, is_ipv6=False)
    
    if not generated_ipv4:
        print("警告: 无法生成任何符合条件的IPv4地址")
        generated_ipv4 = []
    
    print(f"\n成功生成 {len(generated_ipv4)} 个符合条件的IPv4地址:")
    for i, ip in enumerate(generated_ipv4, 1):
        print(f"{i}. {ip}")
    
    # 生成并测试IPv6地址（如果启用）
    generated_ipv6 = []
    if GENERATE_IPV6:
        num_ipv6 = IPV6_COUNT
        print(f"\n正在生成并测试 {num_ipv6} 个IPv6地址...")
        
        generated_ipv6 = generate_random_ips_with_retry(num_ips=num_ipv6, is_ipv6=True)
        
        if not generated_ipv6:
            print("警告: 无法生成任何符合条件的IPv6地址")
            generated_ipv6 = []
        else:
            print(f"\n成功生成 {len(generated_ipv6)} 个符合条件的IPv6地址:")
            for i, ip in enumerate(generated_ipv6, 1):
                print(f"{i}. {ip}")
    
    # 保存IP到文件
    if generated_ipv4:
        save_ips_to_file(generated_ipv4, 'cfip.txt')
    if generated_ipv6:
        save_ipv6_to_file(generated_ipv6, 'cfipv6.txt')
    
    # 更新DNS记录（如果配置了环境变量）
    if CF_API_TOKEN and CF_ZONE_ID and CF_DNS_NAME:
        print("\n开始更新DNS记录...")
        push_content = []
        
        # 1. 删除所有现有的A记录和AAAA记录
        print("步骤1: 删除现有DNS记录...")
        
        # 删除所有A记录
        a_delete_results, a_delete_summary = delete_all_dns_records(CF_DNS_NAME, 'A')
        push_content.append(f"**A记录删除结果:**")
        push_content.append(a_delete_summary)
        
        # 删除所有AAAA记录
        aaaa_delete_results, aaaa_delete_summary = delete_all_dns_records(CF_DNS_NAME, 'AAAA')
        push_content.append(f"**AAAA记录删除结果:**")
        push_content.append(aaaa_delete_summary)
        
        # 2. 创建新的DNS记录
        print("\n步骤2: 创建新的DNS记录...")
        create_results = []
        
        # 创建A记录（IPv4）
        if generated_ipv4:
            print(f"创建A记录...")
            # 限制创建的A记录数量，避免过多
            max_a_records = min(10, len(generated_ipv4))
            for i in range(max_a_records):
                ip_address = generated_ipv4[i]
                result = create_dns_record(CF_DNS_NAME, ip_address, 'A')
                create_results.append(result)
                print(f"创建A记录 {i+1}/{max_a_records}: {ip_address}")
        else:
            create_results.append("没有可用的IPv4地址，跳过A记录创建")
        
        # 创建AAAA记录（IPv6）
        if generated_ipv6 and GENERATE_IPV6:
            print(f"创建AAAA记录...")
            # 限制创建的AAAA记录数量，避免过多
            max_aaaa_records = min(10, len(generated_ipv6))
            for i in range(max_aaaa_records):
                ip_address = generated_ipv6[i]
                result = create_dns_record(CF_DNS_NAME, ip_address, 'AAAA')
                create_results.append(result)
                print(f"创建AAAA记录 {i+1}/{max_aaaa_records}: {ip_address}")
        elif GENERATE_IPV6:
            create_results.append("没有可用的IPv6地址，跳过AAAA记录创建")
        
        # 3. 汇总结果
        push_content.append(f"\n**新记录创建结果:**")
        push_content.extend(create_results)
        
        # 添加摘要信息到推送内容
        summary_content = []
        summary_content.append(f"**Cloudflare IP优选及DNS更新**")
        summary_content.append(f"更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        summary_content.append(f"测试配置: 期望状态码={EXPECTED_STATUS_CODE}")
        summary_content.append(f"域名: {CF_DNS_NAME}")
        
        if generated_ipv4:
            summary_content.append(f"\n**IPv4地址 ({len(generated_ipv4)}个):**")
            summary_content.append(", ".join(generated_ipv4[:5]))
            if len(generated_ipv4) > 5:
                summary_content.append(f"... 等共 {len(generated_ipv4)} 个地址")
        
        if generated_ipv6:
            summary_content.append(f"\n**IPv6地址 ({len(generated_ipv6)}个):**")
            summary_content.append(", ".join(generated_ipv6[:3]))
            if len(generated_ipv6) > 3:
                summary_content.append(f"... 等共 {len(generated_ipv6)} 个地址")
        
        # 合并所有内容
        final_push_content = summary_content + [""] + push_content
        
        # 发送推送通知
        push_notification('\n'.join(final_push_content))
        print("\nDNS记录更新完成")
    else:
        print("\n未更新DNS记录，原因:")
        if not CF_API_TOKEN:
            print("- 缺少 CF_API_TOKEN")
        if not CF_ZONE_ID:
            print("- 缺少 CF_ZONE_ID")
        if not CF_DNS_NAME:
            print("- 缺少 CF_DNS_NAME")
        
        if generated_ipv4:
            print(f"\nIPv4地址已保存到 cfip.txt 文件")
        if generated_ipv6:
            print(f"IPv6地址已保存到 cfipv6.txt 文件")
    
    print("=" * 60)
    print("程序执行完毕")

if __name__ == "__main__":
    main()