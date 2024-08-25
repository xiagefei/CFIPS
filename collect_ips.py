import requests
from lxml import html
import re
import os

# 目标 URL 列表
urls = ['https://monitor.gacjie.cn/page/cloudflare/ipv4.html']

# 正则表达式用于匹配 IP 地址
ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

# 检查 ip.txt 文件是否存在，如果存在则删除它
if os.path.exists('ip.txt'):
    os.remove('ip.txt')

# 创建一个文件来存储 IP 地址
with open('ip.txt', 'w') as file:
    for url in urls:
        # 发送 HTTP 请求获取网页内容
        response = requests.get(url)
        
        # 使用 lxml 解析 HTML
        tree = html.fromstring(response.content)
        
        # 根据网站的不同结构找到包含 IP 地址的元素
        if url == 'https://monitor.gacjie.cn/page/cloudflare/ipv4.html':
            elements = tree.xpath('//tr')
        elif url == 'https://ip.164746.xyz':
            elements = tree.xpath('//tr')
        else:
            elements = tree.xpath('//li')
        
        # 遍历所有元素，查找 IP 地址
        for element in elements:
            element_text = element.text_content()
            ip_matches = re.findall(ip_pattern, element_text)
            
            # 如果找到 IP 地址，则写入文件
            for ip in ip_matches:
                file.write(ip + '\n')

print('IP 地址已保存到 ip.txt 文件中。')