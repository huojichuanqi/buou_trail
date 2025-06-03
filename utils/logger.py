import logging
from logging.handlers import TimedRotatingFileHandler
import os

def setup_logger(name, log_file):
    """
    设置并返回一个配置好的logger实例
    
    Args:
        name: logger的名称
        log_file: 日志文件路径
        
    Returns:
        logging.Logger: 配置好的logger实例
    """
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 使用 TimedRotatingFileHandler 以天为单位进行日志分割
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"  # 设置日志文件名的后缀格式

    # 设置更详细的日志格式
    formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] %(levelname)s [%(name)s:%(filename)s:%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 避免日志重复
    logger.propagate = False
    
    return logger 