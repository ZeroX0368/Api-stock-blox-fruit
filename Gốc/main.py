
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import requests
import json
import hashlib
from datetime import datetime
import asyncio
import uvicorn

app = FastAPI(title="BloxFruit Stock Monitor", version="1.0.0")

# Global variables to store previous data hash and webhook URLs
previous_data_hash = None
monitoring_active = False
webhook_urls = set()  # Use set to avoid duplicate webhooks

def get_bloxfruit_data():
    """Fetch data from the BloxFruit API"""
    try:
        response = requests.get("http://test-hub.kys.gay/api/stock/bloxfruit")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching BloxFruit data: {e}")
        return None

def get_data_hash(data):
    """Generate hash of data to detect changes"""
    if not data:
        return None
    data_string = json.dumps(data, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()

def has_data_changed(data):
    """Check if data has changed since last check"""
    global previous_data_hash
    current_hash = get_data_hash(data)
    
    if previous_data_hash is None:
        previous_data_hash = current_hash
        return True  # First run, consider as changed
    
    if current_hash != previous_data_hash:
        previous_data_hash = current_hash
        return True
    
    return False

def send_discord_webhook(data, webhook_urls):
    """Send data to multiple Discord webhooks with separate embeds for each stock type"""
    if not data or not webhook_urls:
        return False
    
    embeds = []
    
    # Create embed for Normal Stock
    if "normal_stock" in data and "items" in data["normal_stock"]:
        normal_items = data["normal_stock"]["items"]
        
        normal_embed = {
            "title": "🔹 Normal Stock Update",
            "description": f"📦 Có {len(normal_items)} mặt hàng trong kho thường",
            "color": 0x3498db,  # Blue color for normal stock
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "BloxFruit Monitor • Normal Stock",
                "icon_url": "https://cdn.discordapp.com/emojis/123456789.png"
            },
            "fields": []
        }
        
        for item in normal_items:
            name = item.get("name", "Unknown")
            usd_price = item.get("usd_price", "N/A")
            robux_price = item.get("robux_price", "N/A")
            
            normal_embed["fields"].append({
                "name": f"🍇 {name}",
                "value": f"💰 **USD:** ${usd_price}\n💎 **Robux:** {robux_price}",
                "inline": True
            })
        
        embeds.append(normal_embed)
    
    # Create embed for Mirage Stock
    if "mirage_stock" in data and "items" in data["mirage_stock"]:
        mirage_items = data["mirage_stock"]["items"]
        
        mirage_embed = {
            "title": "✨ Mirage Stock Update",
            "description": f"🌟 Có {len(mirage_items)} mặt hàng hiếm trong kho đặc biệt",
            "color": 0xe74c3c,  # Red color for mirage stock
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "BloxFruit Monitor • Mirage Stock",
                "icon_url": "https://cdn.discordapp.com/emojis/123456789.png"
            },
            "fields": []
        }
        
        for item in mirage_items:
            name = item.get("name", "Unknown")
            usd_price = item.get("usd_price", "N/A")
            robux_price = item.get("robux_price", "N/A")
            
            mirage_embed["fields"].append({
                "name": f"⭐ {name}",
                "value": f"💰 **USD:** ${usd_price}\n💎 **Robux:** {robux_price}",
                "inline": True
            })
        
        embeds.append(mirage_embed)
    
    # If no stock data found, send a general update
    if not embeds:
        embeds.append({
            "title": "🍎 BloxFruit Stock Update",
            "description": "🔄 Stock đã được cập nhật nhưng không có dữ liệu mới",
            "color": 0x95a5a6,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "BloxFruit Monitor Bot",
                "icon_url": "https://cdn.discordapp.com/emojis/123456789.png"
            }
        })
    
    # Prepare webhook payload
    payload = {
        "username": "BloxFruit Monitor",
        "avatar_url": "https://cdn.discordapp.com/emojis/123456789.png",
        "embeds": embeds
    }
    
    success_count = 0
    total_webhooks = len(webhook_urls)
    
    for webhook_url in webhook_urls:
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            success_count += 1
            print(f"✅ Đã gửi thông báo đến webhook: {webhook_url[:50]}...")
        except requests.exceptions.RequestException as e:
            print(f"❌ Lỗi khi gửi webhook {webhook_url[:50]}...: {e}")
    
    print(f"📊 Gửi thành công {success_count}/{total_webhooks} webhooks")
    return success_count > 0

async def monitor_task():
    """Background task to monitor BloxFruit stock"""
    global monitoring_active, webhook_urls
    monitoring_active = True
    check_count = 0
    
    print("🚀 Bắt đầu theo dõi BloxFruit stock...")
    print("⏱️  Bot sẽ kiểm tra thay đổi mỗi 30 giây")
    
    try:
        while monitoring_active:
            check_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            
            print(f"📡 [{current_time}] Kiểm tra lần #{check_count}...")
            
            # Fetch data from API
            data = get_bloxfruit_data()
            
            if data:
                # Check if data has changed
                if has_data_changed(data):
                    print("🔄 Phát hiện thay đổi trong stock!")
                    
                    # Send webhook notification to all registered webhooks
                    success = send_discord_webhook(data, webhook_urls)
                    
                    if success:
                        print("🎉 Đã thông báo thay đổi thành công!")
                    else:
                        print("❌ Không thể gửi thông báo")
                else:
                    print("✅ Không có thay đổi, tiếp tục theo dõi...")
            else:
                print("❌ Không thể lấy dữ liệu từ API")
            
            await asyncio.sleep(30)  # Wait 30 seconds before next check
            
    except Exception as e:
        print(f"❌ Lỗi trong quá trình monitor: {e}")
        monitoring_active = False

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🤖 BloxFruit Stock Monitor API",
        "status": "active" if monitoring_active else "inactive",
        "endpoints": {
            "/api/stock/blox-fruit?webhook=": "Add webhook and start monitoring",
            "/api/webhooks": "Get all registered webhooks",
            "/api/webhooks/remove?webhook=": "Remove a webhook",
            "/status": "Check monitoring status",
            "/api/stock/current": "Get current Bloxfruit Stock Data"
        }
    }

@app.get("/api/stock/blox-fruit")
async def add_webhook_and_start_monitoring(webhook: str, background_tasks: BackgroundTasks):
    """Add webhook URL and start monitoring BloxFruit stock"""
    global monitoring_active, webhook_urls
    
    if not webhook:
        raise HTTPException(status_code=400, detail="Webhook URL is required")
    
    # Validate webhook URL
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise HTTPException(status_code=400, detail="Invalid Discord webhook URL")
    
    # Add webhook to the set
    webhook_urls.add(webhook)
    
    # Start monitoring if not already active
    if not monitoring_active:
        background_tasks.add_task(monitor_task)
        message = "🚀 BloxFruit stock monitoring started!"
    else:
        message = "✅ Webhook added to existing monitoring"
    
    return JSONResponse(
        status_code=200,
        content={
            "message": message,
            "webhook_added": webhook,
            "total_webhooks": len(webhook_urls),
            "check_interval": "30 seconds"
        }
    )

@app.get("/status")
async def get_status():
    """Get current monitoring status"""
    return {
        "monitoring_active": monitoring_active,
        "total_webhooks": len(webhook_urls),
        "message": "Monitoring is active" if monitoring_active else "Monitoring is not active"
    }
    
@app.get("/api/stock/current")
async def get_current_stock():
    """Get current BloxFruit stock data"""
    data = get_bloxfruit_data()
    if data:
        return data
    else:
        raise HTTPException(status_code=503, detail="Unable to fetch stock data")

@app.get("/api/webhooks")
async def get_webhooks():
    """Get all registered webhook URLs"""
    return {
        "webhooks": list(webhook_urls),
        "total_count": len(webhook_urls),
        "monitoring_active": monitoring_active
    }

@app.get("/api/webhooks/remove")
async def remove_webhook(webhook: str):
    """Remove a webhook URL from monitoring"""
    global webhook_urls
    
    if not webhook:
        raise HTTPException(status_code=400, detail="Webhook URL is required")
    
    if webhook in webhook_urls:
        webhook_urls.remove(webhook)
        return JSONResponse(
            status_code=200,
            content={
                "message": "✅ Webhook removed successfully",
                "webhook_removed": webhook,
                "remaining_webhooks": len(webhook_urls)
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Webhook not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
