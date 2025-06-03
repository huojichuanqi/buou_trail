from utils.feishu_message import FeishuMessage

def test_feishu_message():
    # 替换为你的 webhook URL
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxx"
    feishu = FeishuMessage(webhook_url)
    
    # 测试普通消息
    feishu.send_card_message(
        title="测试通知",
        content="这是一条测试消息\n包含**加粗**和*斜体*效果",
        button_text="点击查看详情",
        button_url="https://example.com"
    )
    
    # 测试交易通知
    feishu.send_trade_notification(
        symbol="BTC/USDT",
        side="long",
        amount=0.01,
        entry_price=50000,
        current_price=51000,
        profit_pct=2.0,
        profit_amount=10.0
    )

if __name__ == "__main__":
    test_feishu_message() 