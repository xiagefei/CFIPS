import dns.resolver

def get_a_records(domain):
    a_records = []
    try:
        answers = dns.resolver.resolve(domain, 'A')
        for rdata in answers:
            a_records.append(rdata.address)
    except dns.resolver.NoAnswer:
        print(f"No A records found for {domain}")
    except dns.resolver.NXDOMAIN:
        print(f"The domain {domain} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

    return a_records

if __name__ == "__main__":
    txt_file_path = "domains.txt"  
    with open(txt_file_path, "r") as f:
        domains = f.readlines()

    with open("domain.txt", "w") as output_file:  # 打开用于保存结果的单个文件
        for domain in domains:
            domain = domain.strip()
            a_records = get_a_records(domain)

            if a_records:
                output_file.write(f"Domain: {domain}\n")  # 先写入域名
                for record in a_records:
                    output_file.write(record + "\n")
                output_file.write("\n")  # 每个域名的记录写完后空一行