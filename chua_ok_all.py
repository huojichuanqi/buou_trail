# -*- coding: utf-8 -*-
import ccxt
import time
import logging
import requests
import json
import okx.Trade_api as TradeAPI
from utils.logger import setup_logger


class MultiAssetTradingBot:
    def __init__(self, config, feishu_webhook=None, monitor_interval=4):
        self.stop_loss_pct = config["all_stop_loss_pct"]  # 全局止损百分比
        self.low_trail_stop_loss_pct = config["all_low_trail_stop_loss_pct"]
        self.trail_stop_loss_pct = config["all_trail_stop_loss_pct"]
        self.higher_trail_stop_loss_pct = config["all_higher_trail_stop_loss_pct"]
        self.low_trail_profit_threshold = config["all_low_trail_profit_threshold"]
        self.first_trail_profit_threshold = config["all_first_trail_profit_threshold"]
        self.second_trail_profit_threshold = config["all_second_trail_profit_threshold"]
        self.feishu_webhook = feishu_webhook
        self.monitor_interval = monitor_interval  # 监控循环时间是分仓监控的3倍
        self.highest_total_profit = 0  # 记录最高总盈利

        # 配置交易所
        self.exchange = ccxt.okx({
            'apiKey': config["apiKey"],
            'secret': config["secret"],
            'password': config["password"],
            'timeout': 3000,
            'rateLimit': 50,
            'options': {'defaultType': 'future'}
        })

        # 配置 OKX 第三方库
        self.trading_bot = TradeAPI.TradeAPI(config["apiKey"], config["secret"], config["password"], False, '0')

        # 配置日志
        self.logger = setup_logger(__name__, "log/okx_all.log")

        self.position_mode = self.get_position_mode()  # 获取持仓模式

    def get_position_mode(self):
        try:
            # 假设获取账户持仓模式的 API
            response = self.exchange.private_get_account_config()
            data = response.get('data', [])
            if data and isinstance(data, list):
                # 取列表的第一个元素（假设它是一个字典），然后获取 'posMode'
                position_mode = data[0].get('posMode', 'single')  # 默认值为单向
                self.logger.info(f"当前持仓模式: {position_mode}")
                return position_mode
            else:
                self.logger.error("无法检测持仓模式: 'data' 字段为空或格式不正确")
                return 'single'  # 返回默认值
        except Exception as e:
            self.logger.error(f"无法检测持仓模式: {e}")
            return None

    def send_feishu_notification(self, message):
        if self.feishu_webhook:
            try:
                headers = {'Content-Type': 'application/json'}
                payload = {"msg_type": "text", "content": {"text": message}}
                response = requests.post(self.feishu_webhook, json=payload, headers=headers)
                if response.status_code == 200:
                    self.logger.info("飞书通知发送成功")
                else:
                    self.logger.error("飞书通知发送失败，状态码: %s", response.status_code)
            except Exception as e:
                self.logger.error("发送飞书通知时出现异常: %s", str(e))

    def fetch_positions(self):
        try:
            positions = self.exchange.fetch_positions()
            return positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []

    def fetch_open_orders(self):
        try:
            orders = self.exchange.fetch_open_orders()
            return orders
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {e}")
            return []

    def cancel_all_orders(self):
        orders = self.fetch_open_orders()
        for order in orders:
            try:
                self.exchange.cancel_order(order['id'])
                self.logger.info(f"Order {order['id']} cancelled.")
            except Exception as e:
                self.logger.error(f"Error cancelling order {order['id']}: {e}")

    def close_all_positions(self):
        positions = self.fetch_positions()
        for position in positions:
            symbol = position['symbol']
            amount = abs(float(position['contracts']))
            side = position['side']
            td_mode = position['marginMode']
            if amount > 0:
                try:
                    self.logger.info(f"Preparing to close position for {symbol}, side: {side}, amount: {amount}")

                    if self.position_mode == 'long_short_mode':
                        # 在双向持仓模式下，指定平仓方向
                        pos_side = 'long' if side == 'long' else 'short'
                    else:
                        # 在单向模式下，不指定方向
                        pos_side = 'net'

                    # 将 symbol 转换为 API 需要的格式
                    inst_id = symbol.replace('/', '-').replace(':USDT', '')
                    if 'SWAP' not in inst_id:  # 确保是永续合约标识
                        inst_id += '-SWAP'
                    # print(f'{inst_id}处理平仓')

                    # 发送平仓请求并获取返回值
                    response = self.trading_bot.close_positions(
                        instId=inst_id,
                        mgnMode=td_mode,
                        posSide=pos_side,
                        autoCxl='true'
                    )
                    self.logger.info(f"Close position response for {symbol}: {response}")
                    time.sleep(0.1)  # 短暂延迟后再试
                    # 检查平仓结果
                    if response.get('code') == '0':  # 确认成功状态
                        self.logger.info(f"Successfully closed position for {symbol}, side: {side}, amount: {amount}")
                        self.send_feishu_notification(
                            f"Successfully closed position for {symbol}, side: {side}, amount: {amount}")
                    else:
                        self.logger.error(f"Failed to close position for {symbol}: {response}")
                        self.send_feishu_notification(f"Failed to close position for {symbol}: {response}")

                except Exception as e:
                    self.logger.error(f"Error closing position for {symbol}: {e}")

    def calculate_average_profit(self):
        positions = self.fetch_positions()
        total_profit_pct = 0.0
        num_positions = 0

        for position in positions:
            symbol = position['symbol']
            entry_price = float(position['entryPrice'])
            current_price = float(position['markPrice'])
            side = position['side']

            # 计算单个仓位的浮动盈利百分比
            if side == 'long':
                profit_pct = (current_price - entry_price) / entry_price * 100
            elif side == 'short':
                profit_pct = (entry_price - current_price) / entry_price * 100
            else:
                continue

            # 累加总盈利百分比
            total_profit_pct += profit_pct
            num_positions += 1

            # 记录单个仓位的盈利情况
            self.logger.info(f"仓位 {symbol}，方向: {side}，开仓价格: {entry_price}，当前价格: {current_price}，"
                             f"浮动盈亏: {profit_pct:.2f}%")

        # 计算平均浮动盈利百分比
        average_profit_pct = total_profit_pct / num_positions if num_positions > 0 else 0
        return average_profit_pct

    def reset_highest_profit_and_tier(self):
        """重置最高总盈利和当前档位状态"""
        self.highest_total_profit = 0
        self.current_tier = "无"
        self.logger.info("已重置最高总盈利和档位状态")

    def monitor_total_profit(self):
        self.logger.info("启动主循环，开始监控总盈利...")
        previous_position_size = sum(
            abs(float(position['contracts'])) for position in self.fetch_positions())  # 初始总仓位大小
        try:
            while True:
                # 检查仓位总规模变化
                current_position_size = sum(abs(float(position['contracts'])) for position in self.fetch_positions())
                if current_position_size > previous_position_size:
                    self.send_feishu_notification(f"检测到仓位变化操作，重置最高盈利和档位状态")
                    self.logger.info("检测到新增仓位操作，重置最高盈利和档位状态")
                    self.reset_highest_profit_and_tier()
                    previous_position_size = current_position_size
                    continue  # 跳过本次循环

                total_profit = self.calculate_average_profit()
                self.logger.info(f"当前总盈利: {total_profit:.2f}%")
                if total_profit > self.highest_total_profit:
                    self.highest_total_profit = total_profit
                # 确定当前盈利档位
                if self.highest_total_profit >= self.second_trail_profit_threshold:
                    self.current_tier = "第二档移动止盈"
                elif self.highest_total_profit >= self.first_trail_profit_threshold:
                    self.current_tier = "第一档移动止盈"
                elif self.highest_total_profit >= self.low_trail_profit_threshold:
                    self.current_tier = "低档保护止盈"
                else:
                    self.current_tier = "无"

                self.logger.info(
                    f"当前总盈利: {total_profit:.2f}%，最高总盈利: {self.highest_total_profit:.2f}%，当前档位: {self.current_tier}")

                # 各档止盈逻辑
                if self.current_tier == "低档保护止盈":
                    self.logger.info(f"低档回撤止盈阈值: {self.low_trail_stop_loss_pct:.2f}%")
                    if total_profit <= self.low_trail_stop_loss_pct:
                        self.send_feishu_notification(f"总盈利触发低档保护止盈，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.logger.info(f"总盈利触发低档保护止盈，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.close_all_positions()
                        self.reset_highest_profit_and_tier()
                        continue
                elif self.current_tier == "第一档移动止盈":
                    trail_stop_loss = self.highest_total_profit * (1 - self.trail_stop_loss_pct)
                    self.logger.info(f"第一档回撤止盈阈值: {trail_stop_loss:.2f}%")
                    if total_profit <= trail_stop_loss:
                        self.send_feishu_notification(
                            f"总盈利达到第一档回撤阈值，最高总盈利: {self.highest_total_profit:.2f}%，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.logger.info(
                            f"总盈利达到第一档回撤阈值，最高总盈利: {self.highest_total_profit:.2f}%，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.close_all_positions()
                        self.reset_highest_profit_and_tier()
                        continue

                elif self.current_tier == "第二档移动止盈":
                    trail_stop_loss = self.highest_total_profit * (1 - self.higher_trail_stop_loss_pct)
                    self.logger.info(f"第二档回撤止盈阈值: {trail_stop_loss:.2f}%")
                    if total_profit <= trail_stop_loss:
                        self.logger.info(f"总盈利达到第二档回撤阈值，最高总盈利: {self.highest_total_profit:.2f}%，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.send_feishu_notification(f"总盈利达到第二档回撤阈值，最高总盈利: {self.highest_total_profit:.2f}%，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                        self.close_all_positions()
                        self.reset_highest_profit_and_tier()
                        continue
                # 全局止损
                if total_profit <= -self.stop_loss_pct:
                    self.logger.info(f"总盈利触发全局止损，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                    self.send_feishu_notification(f"总盈利触发全局止损，当前回撤到: {total_profit:.2f}%，执行全部平仓")
                    self.close_all_positions()
                    self.reset_highest_profit_and_tier()
                    continue


                time.sleep(self.monitor_interval)

        except KeyboardInterrupt:
            self.logger.info("程序收到中断信号，开始退出...")
        except Exception as e:
            error_message = f"程序异常退出: {str(e)}"
            self.logger.error(error_message)
            self.send_feishu_notification(error_message)


if __name__ == '__main__':
    with open('config.json', 'r') as f:
        config_data = json.load(f)

    # 指定具体平台配置，例如 OKX
    platform_config = config_data['okx']
    feishu_webhook_url = config_data['feishu_webhook']
    monitor_interval = config_data.get("monitor_interval", 4)  # 默认值为4秒

    bot = MultiAssetTradingBot(platform_config, feishu_webhook=feishu_webhook_url, monitor_interval=monitor_interval)
    bot.monitor_total_profit()
