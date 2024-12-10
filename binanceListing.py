import requests
import time
import aiohttp
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
import json
import re

from config import WEBHOOK_URL, PROXY_URL, USE_PROXY, ALWAYS_NOTIFY, API_URL, MONITOR_INTERVAL

# HTML URL
api_url = API_URL

# 监控周期，单位：秒
monitor_interval = MONITOR_INTERVAL  # 每隔 60 秒查询一次

# 记录已经处理过的文章ID，避免重复提醒
processed_article_ids = set()

# 添加一个新的变量来存储上次的文章ID集合
last_article_ids = set()

async def send_message_async(message_content):
    """发送消息到企业微信机器人"""
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": message_content
        }
    }
    
    proxy = PROXY_URL if USE_PROXY else None
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=payload, headers=headers, proxy=proxy) as response:
            # print response
            # print(response)

            if response.status == 200:
                log_with_time("Message sent successfully!")
            else:
                log_with_time(f"Failed to send message: {response.status}")

# 打印时加上时间戳
def log_with_time(message):
    """打印带时间戳的消息"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] {message}")

# 初始化时获取现有的文章ID
def initialize_processed_articles():
    """初始化时获取当前所有文章ID，避免启动时提醒已有文章"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(api_url, headers=headers)
        # print(response.text)
        print(response.text)

        soup = BeautifulSoup(response.text, 'html.parser')
        titles = soup.find_all('h1 + div a')

        for title in titles:
            title_text = title.get_text().strip()
            content = title.find_next('div')
            content_text = content.get_text().strip() if content else ""
            announcement_id = hash(title_text + content_text)
            processed_article_ids.add(announcement_id)

        log_with_time("Initialization complete. Monitoring new articles...")
    
    except Exception as e:
        log_with_time(f"Error during initialization: {e}")

def get_emoji_for_type(title):
    """根据公告标题返回相应的 emoji"""
    if "Introducing" in title or "上线" in title:
        return "🚀"  # 新币种上线
    elif "Launchpool" in title:
        return "🌱"  # LaunchPool
    elif "Futures" in title:
        return "📈"  # 合约
    elif "Options" in title:
        return "📊"  # 期货
    elif "Margin" in title:
        return "💹"  # Margin
    else:
        return "ℹ️"  # 其他

def build_listing_message(title, release_date, link):
    """构建新币种上线公告的推送消息"""
    emoji = get_emoji_for_type(title)  # 获取对应的 emoji
    return (
        f"{emoji} 新币种上线公告 📢\n"
        f"标题: {title}\n"
        f"时间: {release_date}\n"
        f"链接: {link if link else '无链接'}"
    )

# 检查是否有包含新得币种上线公告
async def check_for_new_listing_announcements():
    """检查网页中是否有新的币种上线公告并发送通知"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(api_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 找到所有的 h1 标题
        titles = soup.find_all('h1 + div a')

        for title in titles:
            title_text = title.get_text().strip()
            # 获取标题后面的 div 内容
            content = title.find_next('div')
            content_text = content.get_text().strip() if content else ""
            
            # 生成唯一ID（使用标题和内容的组合）
            announcement_id = hash(title_text + content_text)
            
            if announcement_id not in processed_article_ids:
                message = build_listing_message(title_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), title['href'])
                log_with_time(message)
                await send_message_async(message)
                processed_article_ids.add(announcement_id)

    except Exception as e:
        log_with_time(f"Error fetching or processing data: {e}")

# 修改 monitor 函数为异步函数
async def monitor():
    """启动监控程序"""
    global last_article_ids
    
    log_with_time("Starting monitor...")
    
    # 首次运行，获取当前文章列表
    initial_articles = save_and_parse_html_content()

    if initial_articles:
        last_article_ids = {article['id'] for article in initial_articles}
        log_with_time(f"Initialized with {len(last_article_ids)} articles")
        
        # 如果设置了ALWAYS_NOTIFY，则发送初始文章通知
        if ALWAYS_NOTIFY:
            for article in initial_articles[:5]:  # 只发送最新的5条
                filtered_title = article['title'].replace('Binance', '')
                message = (
                    f"📢 Initial Listing Alert 📢\n"
                    f"Title: {filtered_title}\n"
                    f"Time: {article['release_date']}\n"
                    f"Link: {article['link']}"
                )
                await send_message_async(message)

    while True:
        try:
            log_with_time("Checking for new articles...")
            articles = save_and_parse_html_content()
            
            if not articles:
                log_with_time("No articles found in this check")
                await asyncio.sleep(monitor_interval)
                continue
                
            # 获取当前文章ID集合
            current_article_ids = {article['id'] for article in articles}
            
            # 找出新增的文章ID
            new_article_ids = current_article_ids - last_article_ids
            
            if new_article_ids:
                log_with_time(f"Found {len(new_article_ids)} new articles")
                # 获取新文章的详细信息并发送通知
                for article in articles:
                    if article['id'] in new_article_ids:
                        link = article.get('link', '无链接')
                        message = build_listing_message(article['title'], article['release_date'], link)
                        log_with_time(f"Sending notification for article {article['id']}")
                        await send_message_async(message)
            else:
                log_with_time("No new articles found")
            
            # 更新上次的文章ID集合
            last_article_ids = current_article_ids
            
        except Exception as e:
            log_with_time(f"Error in monitor loop: {e}")
            # 发送错误通知
            await send_message_async(f"❌ Monitor Error: {str(e)}")
        
        log_with_time(f"Waiting for {monitor_interval} seconds before next check...")
        await asyncio.sleep(monitor_interval)

async def save_html_content():
    """保存HTML内容到本地文件"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        timeout = aiohttp.ClientTimeout(total=10)  # 10秒超时
        
        log_with_time("Starting request...")
        async with aiohttp.ClientSession(timeout=timeout) as session:
            log_with_time("Sending request to Binance...")
            async with session.get(api_url, headers=headers, proxy=PROXY_URL if USE_PROXY else None) as response:
                log_with_time(f"Response status: {response.status}")
                html = await response.text()
                log_with_time(f"Received content length: {len(html)}")
                
                # 保存原始HTML
                with open('binance_listing.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                log_with_time("Raw HTML saved to binance_listing.html")
                
                # 保存格式化后的HTML（便于查看）
                soup = BeautifulSoup(html, 'html.parser')
                pretty_html = soup.prettify()
                with open('binance_listing_formatted.html', 'w', encoding='utf-8') as f:
                    f.write(pretty_html)
                log_with_time("Formatted HTML saved to binance_listing_formatted.html")
                
                return html

    except aiohttp.ClientError as e:
        log_with_time(f"Network error: {e}")
    except asyncio.TimeoutError:
        log_with_time("Request timed out")
    except Exception as e:
        log_with_time(f"Error saving HTML content: {e}")
    return None

# 或者使用同步方式尝试
def save_html_content_sync():
    """使用同步方式保存HTML内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        log_with_time("Starting request...")
        response = requests.get(api_url, headers=headers, timeout=10, proxies={'http': PROXY_URL, 'https': PROXY_URL} if USE_PROXY else None)
        log_with_time(f"Response status: {response.status_code}")
        
        html = response.text
        log_with_time(f"Received content length: {len(html)}")
        
        # 保存原始HTML
        with open('binance_listing.html', 'w', encoding='utf-8') as f:
            f.write(html)
        log_with_time("Raw HTML saved to binance_listing.html")
        
        # 保存格式化后的HTML
        soup = BeautifulSoup(html, 'html.parser')
        pretty_html = soup.prettify()
        with open('binance_listing_formatted.html', 'w', encoding='utf-8') as f:
            f.write(pretty_html)
        log_with_time("Formatted HTML saved to binance_listing_formatted.html")
        
        return html
        
    except requests.RequestException as e:
        log_with_time(f"Request error: {e}")
    except Exception as e:
        log_with_time(f"Error saving HTML content: {e}")
    return None

def parse_listing_data(html_content):
    """从HTML内容中解析出新币上线信息"""
    try:
        # 查找包含目标数据的script标签
        pattern = r'<script id="__APP_DATA" type="application/json".*?>(.*?)</script>'
        script_content = re.search(pattern, html_content, re.DOTALL)
        
        if not script_content:
            log_with_time("No APP_DATA script found")
            return None
            
        # 解析JSON数据
        json_data = json.loads(script_content.group(1))
        
        # 遍历 dataByRouteId 查找目标 catalog
        route_data = json_data['appState']['loader']['dataByRouteId']
        target_catalog = None
        
        for key in route_data:
            data = route_data[key]
            if 'catalogDetail' in data and data['catalogDetail'].get('catalogName') == "New Cryptocurrency Listing":
                target_catalog = data['catalogDetail']
                break
                
        if not target_catalog:
            log_with_time("No New Cryptocurrency Listing catalog found")
            return None
            
        # 解析文章列表
        articles = target_catalog['articles']
        log_with_time(f"Found {len(articles)} articles")
        
        # 格式化文章信息
        formatted_articles = []
        for article in articles:
            formatted_article = {
                'id': article['id'],
                'code': article['code'],
                'title': article['title'],
                'release_date': datetime.fromtimestamp(article['releaseDate']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                'link': build_article_link(article['title'], article['code'])
            }
            formatted_articles.append(formatted_article)
            
        return formatted_articles

    except json.JSONDecodeError as e:
        log_with_time(f"JSON parsing error: {e}")
    except Exception as e:
        log_with_time(f"Error parsing listing data: {e}")
    return None

def save_and_parse_html_content():
    """保存HTML内容并解析数据"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        log_with_time("Starting request...")
        response = requests.get(api_url, headers=headers, timeout=10, 
                              proxies={'http': PROXY_URL, 'https': PROXY_URL} if USE_PROXY else None)
        log_with_time(f"Response status: {response.status_code}")
        
        html = response.text
        log_with_time(f"Received content length: {len(html)}")
        
        # 保存原始HTML
        with open('binance_listing.html', 'w', encoding='utf-8') as f:
            f.write(html)
        log_with_time("Raw HTML saved to binance_listing.html")
        
        # 解析数据
        articles = parse_listing_data(html)
        if articles:
            # 保存解析后的数据
            with open('binance_listing_data.json', 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            log_with_time("Parsed data saved to binance_listing_data.json")
            
            # 打印最新的5条公告
            log_with_time("\nLatest 5 announcements:")
            for article in articles[:5]:
                log_with_time(f"Title: {article['title']}")
                log_with_time(f"Release Date: {article['release_date']}")
                log_with_time("-" * 50)
        
        return articles
        
    except requests.RequestException as e:
        log_with_time(f"Request error: {e}")
    except Exception as e:
        log_with_time(f"Error in save_and_parse_html_content: {e}")
    return None

def build_article_link(title, code):
    """构建文章链接"""
    base_url = "https://www.binance.com/en/support/announcement/"
    # 将标题中的空格替换为 "-"，并将其转换为小写
    formatted_title = title.replace(" ", "-").lower()
    return f"{base_url}{formatted_title}-{code}"

# 修改 main 部分
if __name__ == "__main__":
    # 正常监控模式
    asyncio.run(monitor())
