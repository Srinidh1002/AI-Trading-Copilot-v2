# services/utils/logging_utils.py

import logging
import sys

class EmojiFilter(logging.Filter):
    """Filter to replace emojis with ASCII equivalents for Windows console"""
    
    def filter(self, record):
        # Replace emojis with text
        replacements = {
            '🚀': '[START]',
            '📊': '[STATS]',
            '📈': '[UP]',
            '📉': '[DOWN]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '⚠️': '[WARN]',
            '🔄': '[REFRESH]',
            '🎯': '[TARGET]',
            '💰': '[MONEY]',
            '📅': '[DATE]',
            '💤': '[SLEEP]',
            '🔌': '[CONNECT]',
            '🛑': '[STOP]',
            '🎉': '[SUCCESS]',
            '📁': '[FOLDER]',
            '📄': '[FILE]',
            '📋': '[NOTE]',
            '🔍': '[SEARCH]',
            '⏳': '[WAIT]',
            '⏰': '[TIME]',
            '🧪': '[TEST]',
            '📜': '[HISTORY]',
            '🌟': '[STAR]',
            '💡': '[TIP]',
            '🏆': '[WIN]',
            '⚡': '[POWER]',
            '🔮': '[PREDICT]',
            '📣': '[ANNOUNCE]',
            '🎊': '[CELEBRATE]',
            '🤖': '[AI]',
            '💎': '[DIAMOND]',
            '🔥': '[FIRE]',
            '⭐': '[RATING]',
            '👋': '[WAVE]',
            '🙏': '[THANKS]',
            '💪': '[STRONG]',
            '🧠': '[BRAIN]',
            '🎩': '[MAGIC]',
            '🌈': '[RAINBOW]',
            '✨': '[SPARKLE]',
            '🔔': '[BELL]',
            '📢': '[ANNOUNCE]',
        }
        
        for emoji, text in replacements.items():
            if emoji in record.msg:
                record.msg = record.msg.replace(emoji, text)
        return True

def setup_logging():
    """Setup logging with emoji filter"""
    # Remove existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Add emoji filter
    console_handler.addFilter(EmojiFilter())
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add handler
    logging.root.addHandler(console_handler)
    logging.root.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)
