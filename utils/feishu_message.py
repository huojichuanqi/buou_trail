import requests
import logging

logger = logging.getLogger(__name__)

class FeishuMessage:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_card_message(self, title, content, button_text=None, button_url=None):
        """
        发送飞书卡片消息
        
        Args:
            title: 卡片标题
            content: 卡片内容（支持markdown格式）
            button_text: 按钮文字（可选）
            button_url: 按钮链接（可选）
            
        Returns:
            bool: 发送是否成功
        """
        if not self.webhook_url:
            logger.warning("未配置飞书 webhook")
            return False

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "content": title,
                        "tag": "plain_text"
                    }
                },
                "elements": [{
                    "tag": "div",
                    "text": {
                        "content": content,
                        "tag": "lark_md"
                    }
                }]
            }
        }

        # 如果提供了按钮信息，添加按钮
        if button_text and button_url:
            card["card"]["elements"].append({
                "actions": [{
                    "tag": "button",
                    "text": {
                        "content": button_text,
                        "tag": "lark_md"
                    },
                    "url": button_url,
                    "type": "default",
                    "value": {}
                }],
                "tag": "action"
            })

        try:
            response = requests.post(
                self.webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                logger.info("飞书通知发送成功")
                return True
            else:
                logger.error(f"飞书通知发送失败，状态码: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"发送飞书通知时出现异常: {str(e)}")
            return False

    def send_trade_notification(self, symbol, side, amount, entry_price, current_price, profit_pct, profit_amount=None):
        """
        发送交易相关的通知
        
        Args:
            symbol: 交易对
            side: 交易方向
            amount: 交易数量
            entry_price: 开仓价格
            current_price: 当前价格/平仓价格
            profit_pct: 盈亏百分比
            profit_amount: 盈亏金额（可选）
        """
        content = (
            f"**交易对**: {symbol}\n"
            f"**方向**: {side}\n"
            f"**数量**: {amount}\n"
            f"**开仓价格**: {entry_price}\n"
            f"**平仓价格**: {current_price}\n"
            f"**盈亏比例**: {profit_pct:.2f}%\n"
        )
        
        if profit_amount is not None:
            content += f"**盈亏金额**: {profit_amount:.2f} USDT"

        title = "🔔 交易通知"
        if profit_pct > 0:
            title = "📈 盈利平仓"
        elif profit_pct < 0:
            title = "📉 亏损平仓"

        return self.send_card_message(title, content) 