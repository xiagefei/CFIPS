import requests
import ipaddress
import random

def get_cloudflare_ips():
    """从Cloudflare获取IPv4地址范围"""
    url = "https://www.cloudflare.com/ips-v4/"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 按行分割，去除空白行
        cidrs = [line.strip() for line in response.text.split('\n') if line.strip()]
        return cidrs
    except requests.RequestException as e:
        print(f"获取IP地址范围失败: {e}")
        return []

def generate_random_ip_from_cidr(cidr):
    """从CIDR范围内生成随机IP地址"""
    network = ipaddress.ip_network(cidr, strict=False)
    
    # 计算网络地址和广播地址（这两个通常不用）
    network_address = int(network.network_address)
    broadcast_address = int(network.broadcast_address)
    
    # 生成网络地址和广播地址之间的随机IP
    # 注意：在实际使用中，可能希望排除网络地址和广播地址
    # 这里我们生成包括第一个可用地址到最后一个可用地址的IP
    if network.prefixlen <= 30:  # 对于大多数网络，排除网络和广播地址
        start_ip = network_address + 1
        end_ip = broadcast_address - 1
    else:  # 对于/31和/32网络，特殊处理
        start_ip = network_address
        end_ip = broadcast_address
    
    # 生成随机IP
    random_ip_int = random.randint(start_ip, end_ip)
    random_ip = ipaddress.IPv4Address(random_ip_int)
    
    return str(random_ip)

def main():
    print("正在获取Cloudflare IPv4地址范围...")
    cidrs = get_cloudflare_ips()
    
    if not cidrs:
        print("无法获取地址范围")
        return
    
    print(f"获取到 {len(cidrs)} 个CIDR范围")
    
    # 生成5个随机IP
    ip_list = []
    for i in range(5):
        # 随机选择一个CIDR范围
        random_cidr = random.choice(cidrs)
        
        # 从该范围生成随机IP
        random_ip = generate_random_ip_from_cidr(random_cidr)
        
        # 保存IP到列表
        ip_list.append(random_ip)
        
        # 打印到控制台
        print(f"{i+1}. IP: {random_ip} (来自范围: {random_cidr})")
    
    # 将IP地址写入文件，每行一个
    with open('cfip.txt', 'w', encoding='utf-8') as file:
        for ip in ip_list:
            file.write(ip + '\n')
    
    print(f"\nIP地址已保存到 cfip.txt 文件中")

if __name__ == "__main__":
    main()