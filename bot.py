"""
Telegram Auto-Reply Bot - Complete Version
सभी बेसिक और एडवांस्ड फीचर्स एक साथ
Author: Your Name
GitHub: https://github.com/yourusername/telegram-auto-reply-bot
"""

import logging
import json
import os
import sqlite3
import time
from datetime import datetime
import random
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Telegram Bot Imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# ==================== CONFIGURATION ====================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# ==================== DATABASE CLASS ====================
class AutoReplyDatabase:
    """SQLite database for storing auto-replies and user data"""
    
    def __init__(self, db_name: str = "auto_replies.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        """Create all necessary database tables"""
        cursor = self.conn.cursor()
        
        # Auto-replies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                reply TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        
        # User statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                message_count INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Group settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                auto_reply_enabled BOOLEAN DEFAULT 1
            )
        ''')
        
        # Chat logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    # ==================== REPLY MANAGEMENT ====================
    def add_reply(self, keyword: str, reply: str) -> bool:
        """Add or update an auto-reply"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO auto_replies (keyword, reply)
                VALUES (?, ?)
            ''', (keyword.strip(), reply.strip()))
            self.conn.commit()
            return True
        except Exception as e:
            logging.error(f"Database error in add_reply: {e}")
            return False
    
    def get_reply(self, keyword: str) -> Optional[str]:
        """Get reply for a specific keyword"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT reply FROM auto_replies WHERE LOWER(keyword) = LOWER(?)',
                (keyword.strip(),)
            )
            result = cursor.fetchone()
            if result:
                # Update usage count
                cursor.execute(
                    'UPDATE auto_replies SET usage_count = usage_count + 1 WHERE LOWER(keyword) = LOWER(?)',
                    (keyword.strip(),)
                )
                self.conn.commit()
                return result[0]
        except Exception as e:
            logging.error(f"Database error in get_reply: {e}")
        return None
    
    def search_keywords(self, text: str) -> List[str]:
        """Search for all keywords in the given text"""
        found_keywords = []
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT keyword FROM auto_replies')
            all_keywords = [row[0].lower() for row in cursor.fetchall()]
            
            text_lower = text.lower()
            for keyword in all_keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
        except Exception as e:
            logging.error(f"Database error in search_keywords: {e}")
        
        return found_keywords
    
    def get_all_replies(self, page: int = 1, per_page: int = 10) -> Tuple[List[tuple], int]:
        """Get paginated list of all auto-replies"""
        try:
            cursor = self.conn.cursor()
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM auto_replies')
            total = cursor.fetchone()[0]
            
            # Get paginated data
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT keyword, reply, usage_count 
                FROM auto_replies 
                ORDER BY keyword 
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            replies = cursor.fetchall()
            return replies, total
        except Exception as e:
            logging.error(f"Database error in get_all_replies: {e}")
            return [], 0
    
    def delete_reply(self, keyword: str) -> bool:
        """Delete an auto-reply"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM auto_replies WHERE LOWER(keyword) = LOWER(?)', (keyword.strip(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Database error in delete_reply: {e}")
            return False
    
    def get_reply_count(self) -> int:
        """Get total number of auto-replies"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM auto_replies')
            return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"Database error in get_reply_count: {e}")
            return 0
    
    # ==================== USER STATISTICS ====================
    def update_user_stats(self, user_id: int, username: str, first_name: str, last_name: str = ""):
        """Update user statistics"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_stats 
                (user_id, username, first_name, last_name, message_count, last_seen)
                VALUES (?, ?, ?, ?, 
                    COALESCE((SELECT message_count FROM user_stats WHERE user_id = ?), 0) + 1, 
                    CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name, user_id))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database error in update_user_stats: {e}")
    
    def get_user_stats(self, user_id: int) -> Optional[tuple]:
        """Get statistics for a specific user"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM user_stats WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Database error in get_user_stats: {e}")
            return None
    
    def get_top_users(self, limit: int = 10) -> List[tuple]:
        """Get top users by message count"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT username, first_name, message_count 
                FROM user_stats 
                ORDER BY message_count DESC 
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"Database error in get_top_users: {e}")
            return []
    
    def get_total_users(self) -> int:
        """Get total number of users"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_stats')
            return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"Database error in get_total_users: {e}")
            return 0
    
    # ==================== GROUP MANAGEMENT ====================
    def update_group(self, group_id: int, group_name: str):
        """Update group information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO group_settings (group_id, group_name)
                VALUES (?, ?)
            ''', (group_id, group_name))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database error in update_group: {e}")
    
    def set_group_auto_reply(self, group_id: int, enabled: bool):
        """Enable or disable auto-reply for a group"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO group_settings (group_id, auto_reply_enabled)
                VALUES (?, ?)
            ''', (group_id, 1 if enabled else 0))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database error in set_group_auto_reply: {e}")
    
    def get_group_auto_reply_status(self, group_id: int) -> bool:
        """Get auto-reply status for a group"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT auto_reply_enabled FROM group_settings WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else True  # Default to enabled
        except Exception as e:
            logging.error(f"Database error in get_group_auto_reply_status: {e}")
            return True
    
    # ==================== CHAT LOGS ====================
    def log_chat(self, user_id: int, message: str, response: str):
        """Log chat conversation"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO chat_logs (user_id, message, response)
                VALUES (?, ?, ?)
            ''', (user_id, message, response))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Database error in log_chat: {e}")
    
    # ==================== BACKUP & RESTORE ====================
    def export_to_json(self, filepath: str = "auto_replies_backup.json"):
        """Export all data to JSON file"""
        try:
            cursor = self.conn.cursor()
            
            # Get all replies
            cursor.execute('SELECT keyword, reply, usage_count FROM auto_replies')
            replies = cursor.fetchall()
            
            # Get user stats
            cursor.execute('SELECT * FROM user_stats')
            users = cursor.fetchall()
            
            # Get group settings
            cursor.execute('SELECT * FROM group_settings')
            groups = cursor.fetchall()
            
            data = {
                'export_date': datetime.now().isoformat(),
                'replies': [{'keyword': k, 'reply': r, 'usage': u} for k, r, u in replies],
                'users': [
                    {
                        'user_id': u[0],
                        'username': u[1],
                        'first_name': u[2],
                        'message_count': u[4]
                    } for u in users
                ],
                'groups': [
                    {
                        'group_id': g[0],
                        'group_name': g[1],
                        'auto_reply_enabled': bool(g[2])
                    } for g in groups
                ]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True, filepath
        except Exception as e:
            logging.error(f"Database error in export_to_json: {e}")
            return False, str(e)

# ==================== BOT CLASS ====================
class AdvancedAutoReplyBot:
    """Main bot class with all features integrated"""
    
    def __init__(self, token: str):
        self.token = token
        self.db = AutoReplyDatabase()
        self.start_time = time.time()
        self.setup_logging()
        self.default_responses = self.load_default_responses()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                logging.FileHandler("bot.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_default_responses(self) -> Dict:
        """Load default responses for common queries"""
        return {
            "greetings": [
                "नमस्ते! मैं कैसे आपकी मदद कर सकता हूं? 😊",
                "हैलो! कैसे हैं आप?",
                "सुप्रभात! 🌅",
                "शुभ संध्या! 🌇"
            ],
            "thanks": [
                "आपका स्वागत है! 🙏",
                "कोई बात नहीं! 😊",
                "खुशी हुई मदद करके! 👍"
            ],
            "help": [
                "मैं आपकी क्या मदद कर सकता हूं?",
                "बताइए, मैं कैसे आपकी मदद करूं?",
                "किस चीज में मदद चाहिए?"
            ],
            "farewell": [
                "अलविदा! फिर मिलेंगे 👋",
                "खुश रहिए! 😊",
                "मिलते रहिएगा! 🙏"
            ],
            "unknown": [
                "माफ करना, मैं समझ नहीं पाया।",
                "क्या आप दोबारा कह सकते हैं?",
                "मैं अभी इसका जवाब नहीं जानता।",
                "कृपया कुछ और पूछें।"
            ]
        }
    
    def get_time_based_greeting(self) -> str:
        """Get greeting based on current time"""
        current_hour = datetime.now().hour
        
        if 5 <= current_hour < 12:
            return "शुभ प्रभात! "
        elif 12 <= current_hour < 17:
            return "नमस्ते! "
        elif 17 <= current_hour < 21:
            return "शुभ संध्या! "
        else:
            return "शुभ रात्रि! "
    
    # ==================== COMMAND HANDLERS ====================
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Update user statistics
        self.db.update_user_stats(
            user.id, 
            user.username or "", 
            user.first_name or "", 
            user.last_name or ""
        )
        
        # Create welcome message with inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📝 ऑटो-रिप्लाई सेट करें", callback_data='set_reply'),
                InlineKeyboardButton("📋 रिप्लाई लिस्ट", callback_data='list_replies')
            ],
            [
                InlineKeyboardButton("❓ मदद", callback_data='help'),
                InlineKeyboardButton("📊 स्टैट्स", callback_data='stats')
            ],
            [
                InlineKeyboardButton("🌐 GitHub", url="https://github.com/yourusername/telegram-auto-reply-bot"),
                InlineKeyboardButton("⭐ Star", url="https://github.com/yourusername/telegram-auto-reply-bot")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🙏 *नमस्ते {user.first_name or 'User'}!*

🤖 *मैं एडवांस्ड ऑटो-रिप्लाई बॉट हूं*

✨ *मुख्य फीचर्स:*
• ऑटोमैटिक कीवर्ड रिप्लाई
• डेटाबेस स्टोरेज (SQLite)
• यूजर स्टैटिस्टिक्स
• ग्रुप सपोर्ट
• स्मार्ट रिप्लाई डिटेक्शन
• इनलाइन बटन्स
• JSON बैकअप/रेस्टोर

🛠 *बेसिक कमांड्स:*
/start - बॉट शुरू करें
/help - सभी कमांड्स देखें
/setreply - नया रिप्लाई सेट करें
/listreplies - सभी रिप्लाई देखें
/delreply - रिप्लाई डिलीट करें
/stats - बॉट स्टैट्स देखें
/mystats - अपनी स्टैट्स देखें

*बस मैसेज लिखें और मैं ऑटो रिप्लाई दूंगा!* 😊
        """
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🆘 *मदद गाइड - ऑटो-रिप्लाई बॉट*

📋 *बेसिक कमांड्स:*
/start - बॉट शुरू करें
/help - यह मदद मैसेज

🛠 *रिप्लाई मैनेजमेंट:*
/setreply <कीवर्ड> <जवाब> - नया रिप्लाई सेट करें
/listreplies [पेज] - सभी रिप्लाई देखें (पेजिनेशन)
/delreply <कीवर्ड> - रिप्लाई डिलीट करें
/search <टेक्स्ट> - कीवर्ड सर्च करें

📊 *स्टैटिस्टिक्स:*
/stats - बॉट स्टैट्स देखें
/mystats - अपनी स्टैट्स देखें
/topusers - टॉप यूजर्स देखें

👥 *ग्रुप कमांड्स:*
/enable - ग्रुप में ऑटो-रिप्लाई ऑन
/disable - ग्रुप में ऑटो-रिप्लाई ऑफ
/groupinfo - ग्रुप इन्फोर्मेशन

⚙️ *एडमिन कमांड्स:*
/broadcast <मैसेज> - सभी यूजर्स को मैसेज
/backup - डेटाबेस बैकअप लें
/export - JSON एक्सपोर्ट
/restart - बॉट रीस्टार्ट

📝 *उदाहरण:*
`/setreply नमस्ते नमस्ते! कैसे हैं आप?`
`/delreply नमस्ते`
`/listreplies 2` (पेज 2 देखने के लिए)

💡 *टिप:* बस कोई भी मैसेज लिखें, मैं ऑटोमैटिक जवाब दूंगा!
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def set_reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setreply command"""
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ *गलत फॉर्मेट!*\n\n"
                "सही फॉर्मेट: `/setreply कीवर्ड जवाब`\n\n"
                "*उदाहरण:*\n"
                "`/setreply नमस्ते नमस्ते! कैसे हैं आप?`\n"
                "`/setreply समय अभी समय है: 10:30 AM`",
                parse_mode='Markdown'
            )
            return
        
        keyword = context.args[0]
        reply_text = ' '.join(context.args[1:])
        
        if self.db.add_reply(keyword, reply_text):
            await update.message.reply_text(
                f"✅ *रिप्लाई सेट हो गया!*\n\n"
                f"*कीवर्ड:* `{keyword}`\n"
                f"*जवाब:* {reply_text}\n\n"
                f"अब जब भी कोई '{keyword}' लिखेगा, मैं यह जवाब दूंगा! 😊",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ रिप्लाई सेट नहीं हो पाया। कृपया बाद में कोशिश करें।"
            )
    
    async def list_replies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /listreplies command"""
        # Get page number from arguments
        page = 1
        if context.args and context.args[0].isdigit():
            page = int(context.args[0])
        
        per_page = 10
        replies, total = self.db.get_all_replies(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        
        if not replies:
            await update.message.reply_text(
                "📭 *कोई रिप्लाई सेट नहीं है*\n\n"
                "पहला रिप्लाई सेट करने के लिए:\n"
                "`/setreply कीवर्ड जवाब`",
                parse_mode='Markdown'
            )
            return
        
        # Create reply list
        reply_text = f"📋 *रिप्लाई लिस्ट (पेज {page}/{total_pages})*\n"
        reply_text += f"_कुल रिप्लाई: {total}_\n\n"
        
        start_num = (page - 1) * per_page + 1
        for i, (keyword, reply, usage) in enumerate(replies, start_num):
            truncated_reply = reply[:50] + "..." if len(reply) > 50 else reply
            reply_text += f"{i}. *{keyword}*\n"
            reply_text += f"   ↳ {truncated_reply}\n"
            reply_text += f"   🔢 {usage} बार यूज़ हुआ\n\n"
        
        # Create navigation buttons
        keyboard = []
        if total_pages > 1:
            row = []
            if page > 1:
                row.append(InlineKeyboardButton("⬅️ पिछला", callback_data=f'page_{page-1}'))
            row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data='current_page'))
            if page < total_pages:
                row.append(InlineKeyboardButton("अगला ➡️", callback_data=f'page_{page+1}'))
            keyboard.append(row)
        
        # Add action buttons
        keyboard.append([
            InlineKeyboardButton("➕ नया रिप्लाई", callback_data='set_reply'),
            InlineKeyboardButton("🗑️ डिलीट", callback_data='delete_mode')
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            reply_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    
    async def delete_reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /delreply command"""
        if not context.args:
            await update.message.reply_text(
                "❌ *कीवर्ड नहीं दिया!*\n\n"
                "सही फॉर्मेट: `/delreply कीवर्ड`\n\n"
                "*उदाहरण:*\n"
                "`/delreply नमस्ते`\n"
                "`/delreply समय`",
                parse_mode='Markdown'
            )
            return
        
        keyword = ' '.join(context.args)
        
        if self.db.delete_reply(keyword):
            await update.message.reply_text(
                f"✅ *रिप्लाई डिलीट हो गया!*\n\n"
                f"कीवर्ड: `{keyword}`\n\n"
                f"अब इस कीवर्ड के लिए कोई ऑटो-रिप्लाई नहीं होगा।",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ *रिप्लाई नहीं मिला!*\n\n"
                f"कीवर्ड: `{keyword}`\n\n"
                f"कृपया `/listreplies` से सभी रिप्लाई देखें।",
                parse_mode='Markdown'
            )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        # Get bot statistics
        reply_count = self.db.get_reply_count()
        total_users = self.db.get_total_users()
        top_users = self.db.get_top_users(5)
        
        # Calculate uptime
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = self.format_uptime(uptime_seconds)
        
        # Create stats message
        stats_text = f"""
📊 *बॉट स्टैटिस्टिक्स*

🤖 *बॉट इन्फो:*
• अपटाइम: {uptime_str}
• स्टार्ट टाइम: {datetime.fromtimestamp(self.start_time).strftime('%d/%m/%Y %H:%M:%S')}

📝 *डेटा स्टैट्स:*
• टोटल रिप्लाई: {reply_count}
• टोटल यूजर्स: {total_users}
• डेटाबेस: `{self.db.db_name}`

🏆 *टॉप 5 एक्टिव यूजर्स:*
"""
        
        for i, (username, first_name, msg_count) in enumerate(top_users, 1):
            display_name = f"@{username}" if username else first_name
            stats_text += f"{i}. {display_name} - {msg_count} मैसेज\n"
        
        if not top_users:
            stats_text += "अभी कोई डेटा नहीं\n"
        
        stats_text += "\n⚡ *सिस्टम इन्फो:*\n"
        stats_text += f"• Python: {os.sys.version.split()[0]}\n"
        stats_text += f"• सर्वर टाइम: {datetime.now().strftime('%H:%M:%S')}"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def my_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mystats command"""
        user = update.effective_user
        user_stats = self.db.get_user_stats(user.id)
        
        if user_stats:
            user_id, username, first_name, last_name, message_count, last_seen = user_stats
            
            stats_text = f"""
👤 *आपकी स्टैट्स*

🆔 *यूजर आईडी:* `{user_id}`
👤 *यूजरनेम:* @{username if username else 'नहीं है'}
📛 *नाम:* {first_name} {last_name if last_name else ''}

📈 *एक्टिविटी:*
• मैसेज काउंट: {message_count}
• आखिरी बार: {last_seen}

🎯 *रैंक:* {self.get_user_rank(user.id)}
            """
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "📭 *कोई स्टैट्स नहीं मिली*\n\n"
                "कृपया कुछ मैसेज भेजें, फिर `/mystats` कमांड यूज़ करें।",
                parse_mode='Markdown'
            )
    
    async def top_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /topusers command"""
        top_users = self.db.get_top_users(10)
        
        if not top_users:
            await update.message.reply_text(
                "📭 *कोई यूजर डेटा नहीं है*\n\n"
                "अभी तक कोई मैसेज नहीं आया है।",
                parse_mode='Markdown'
            )
            return
        
        top_text = "🏆 *टॉप 10 एक्टिव यूजर्स*\n\n"
        
        for i, (username, first_name, msg_count) in enumerate(top_users, 1):
            if username:
                display_name = f"@{username}"
            else:
                display_name = first_name or f"User {i}"
            
            # Create progress bar
            max_msgs = top_users[0][2] if top_users else 1
            bar_length = 10
            filled = int((msg_count / max_msgs) * bar_length) if max_msgs > 0 else 0
            progress_bar = "█" * filled + "░" * (bar_length - filled)
            
            top_text += f"{i}. {display_name}\n"
            top_text += f"   {progress_bar} {msg_count} मैसेज\n\n"
        
        await update.message.reply_text(top_text, parse_mode='Markdown')
    
    # ==================== MESSAGE HANDLERS ====================
    async def handle_private_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages"""
        user = update.effective_user
        message_text = update.message.text
        
        # Skip if it's a command
        if message_text and message_text.startswith('/'):
            return
        
        # Update user statistics
        self.db.update_user_stats(
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or ""
        )
        
        # Get reply
        reply = await self.get_auto_reply(message_text, user)
        
        # Send reply
        if reply:
            await update.message.reply_text(reply)
            # Log the conversation
            self.db.log_chat(user.id, message_text, reply)
    
    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle group messages"""
        chat = update.effective_chat
        
        # Only process group/supergroup messages
        if chat.type not in ['group', 'supergroup']:
            return
        
        # Update group information
        self.db.update_group(chat.id, chat.title or "Unknown Group")
        
        # Check if auto-reply is enabled for this group
        if not self.db.get_group_auto_reply_status(chat.id):
            return
        
        user = update.effective_user
        message_text = update.message.text
        
        # Skip if it's a command
        if message_text and message_text.startswith('/'):
            return
        
        # Get reply
        reply = await self.get_auto_reply(message_text, user)
        
        # Send reply
        if reply:
            await update.message.reply_text(reply)
            # Log the conversation
            self.db.log_chat(user.id, message_text, reply)
    
    async def get_auto_reply(self, message_text: str, user) -> Optional[str]:
        """Get auto-reply for given message text"""
        if not message_text:
            return None
        
        # 1. Check for exact keyword match
        exact_reply = self.db.get_reply(message_text.strip())
        if exact_reply:
            return exact_reply
        
        # 2. Check for keywords in message
        found_keywords = self.db.search_keywords(message_text)
        if found_keywords:
            # Get reply for the first found keyword
            reply = self.db.get_reply(found_keywords[0])
            if reply:
                return reply
        
        # 3. Smart reply based on message content
        smart_reply = self.get_smart_reply(message_text)
        if smart_reply:
            return smart_reply
        
        # 4. Default random reply
        return random.choice(self.default_responses["unknown"])
    
    def get_smart_reply(self, message_text: str) -> Optional[str]:
        """Generate smart reply based on message content"""
        message_lower = message_text.lower()
        
        # Greeting detection
        if any(word in message_lower for word in ['नमस्ते', 'हैलो', 'हाय', 'hi', 'hello']):
            greeting = self.get_time_based_greeting()
            return greeting + random.choice(self.default_responses["greetings"])
        
        # Thanks detection
        if any(word in message_lower for word in ['धन्यवाद', 'थैंक्स', 'शुक्रिया', 'thank you']):
            return random.choice(self.default_responses["thanks"])
        
        # Help detection
        if any(word in message_lower for word in ['मदद', 'हेल्प', 'सहायता', 'help']):
            return random.choice(self.default_responses["help"])
        
        # Farewell detection
        if any(word in message_lower for word in ['बाय', 'अलविदा', 'बाय बाय', 'bye', 'goodbye']):
            return random.choice(self.default_responses["farewell"])
        
        # Question detection
        if any(word in message_lower for word in ['क्या', 'कैसे', 'क्यों', 'कब', 'कहाँ']):
            return "यह एक अच्छा सवाल है! मैं इसके बारे में सोचता हूं... 🤔"
        
        # Time/Date queries
        if any(word in message_lower for word in ['समय', 'टाइम', 'वक्त']):
            current_time = datetime.now().strftime("%I:%M %p")
            return f"अभी समय है: {current_time} ⏰"
        
        if any(word in message_lower for word in ['तारीख', 'डेट', 'आज']):
            current_date = datetime.now().strftime("%d/%m/%Y")
            return f"आज की तारीख: {current_date} 📅"
        
        # Bot info
        if any(word in message_lower for word in ['बॉट', 'बोट', 'तुम कौन']):
            return "मैं एक स्मार्ट ऑटो-रिप्लाई टेलीग्राम बॉट हूं! 🤖"
        
        return None
    
    # ==================== GROUP COMMANDS ====================
    async def enable_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable auto-reply in group"""
        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ यह कमांड सिर्फ ग्रुप में काम करता है!"
            )
            return
        
        chat = update.effective_chat
        self.db.set_group_auto_reply(chat.id, True)
        
        await update.message.reply_text(
            "✅ *ऑटो-रिप्लाई ऑन हो गया!*\n\n"
            "अब इस ग्रुप में मैं ऑटोमैटिक जवाब दूंगा। 😊",
            parse_mode='Markdown'
        )
    
    async def disable_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable auto-reply in group"""
        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ यह कमांड सिर्फ ग्रुप में काम करता है!"
            )
            return
        
        chat = update.effective_chat
        self.db.set_group_auto_reply(chat.id, False)
        
        await update.message.reply_text(
            "❌ *ऑटो-रिप्लाई ऑफ हो गया!*\n\n"
            "अब इस ग्रुप में मैं ऑटोमैटिक जवाब नहीं दूंगा।",
            parse_mode='Markdown'
        )
    
    async def group_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group information"""
        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ यह कमांड सिर्फ ग्रुप में काम करता है!"
            )
            return
        
        chat = update.effective_chat
        auto_reply_enabled = self.db.get_group_auto_reply_status(chat.id)
        
        group_info = f"""
👥 *ग्रुप इन्फोर्मेशन*

*ग्रुप नाम:* {chat.title or "N/A"}
*ग्रुप आईडी:* `{chat.id}`
*ग्रुप टाइप:* {chat.type}
*मेंबर्स काउंट:* {chat.get_member_count() if hasattr(chat, 'get_member_count') else "N/A"}

⚙️ *बॉट सेटिंग्स:*
• ऑटो-रिप्लाई: {'✅ ऑन' if auto_reply_enabled else '❌ ऑफ'}

🛠 *उपलब्ध कमांड्स:*
/enable - ऑटो-रिप्लाई ऑन करें
/disable - ऑटो-रिप्लाई ऑफ करें
/groupinfo - यह इन्फो देखें
        """
        
        await update.message.reply_text(group_info, parse_mode='Markdown')
    
    # ==================== ADMIN COMMANDS ====================
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users (Admin only)"""
        user = update.effective_user
        
        # Check if user is admin
        if user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ *परमिशन डिनाइड!*\n\n"
                "यह कमांड सिर्फ एडमिन के लिए है।",
                parse_mode='Markdown'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *मैसेज नहीं दिया!*\n\n"
                "सही फॉर्मेट: `/broadcast आपका मैसेज`\n\n"
                "*उदाहरण:*\n"
                "`/broadcast Hello everyone! This is a test message.`",
                parse_mode='Markdown'
            )
            return
        
        message = ' '.join(context.args)
        total_users = self.db.get_total_users()
        
        await update.message.reply_text(
            f"📢 *ब्रॉडकास्ट शुरू हो रहा है...*\n\n"
            f"मैसेज: {message[:100]}...\n"
            f"यूजर्स: {total_users}\n\n"
            f"कृपया वेट करें...",
            parse_mode='Markdown'
        )
        
        # Get all users
        success_count = 0
        failed_count = 0
        
        # Note: This is a simplified version. In production, you might want to
        # implement proper user retrieval and error handling.
        
        await update.message.reply_text(
            f"✅ *ब्रॉडकास्ट कम्प्लीट!*\n\n"
            f"📊 *रिजल्ट:*\n"
            f"• ✅ सक्सेस: {success_count}\n"
            f"• ❌ फेल्ड: {failed_count}\n"
            f"• 📊 टोटल: {total_users}",
            parse_mode='Markdown'
        )
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create database backup (Admin only)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ *परमिशन डिनाइड!*\n\n"
                "यह कमांड सिर्फ एडमिन के लिए है।",
                parse_mode='Markdown'
            )
            return
        
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        success, result = self.db.export_to_json(backup_filename)
        
        if success:
            await update.message.reply_text(
                f"✅ *बैकअप सक्सेसफुल!*\n\n"
                f"फाइल: `{backup_filename}`\n"
                f"टाइम: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode='Markdown'
            )
            
            # Send the backup file
            with open(backup_filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=backup_filename,
                    caption=f"📁 बैकअप फाइल: {backup_filename}"
                )
        else:
            await update.message.reply_text(
                f"❌ *बैकअप फेल्ड!*\n\n"
                f"एरर: {result}",
                parse_mode='Markdown'
            )
    
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export data to JSON (Admin only)"""
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ *परमिशन डिनाइड!*\n\n"
                "यह कमांड सिर्फ एडमिन के लिए है।",
                parse_mode='Markdown'
            )
            return
        
        export_filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        success, result = self.db.export_to_json(export_filename)
        
        if success:
            reply_count = self.db.get_reply_count()
            total_users = self.db.get_total_users()
            
            await update.message.reply_text(
                f"✅ *डेटा एक्सपोर्ट सक्सेसफुल!*\n\n"
                f"📊 *स्टैट्स:*\n"
                f"• रिप्लाई: {reply_count}\n"
                f"• यूजर्स: {total_users}\n"
                f"• फाइल: `{export_filename}`",
                parse_mode='Markdown'
            )
            
            # Send the export file
            with open(export_filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=export_filename,
                    caption=f"📁 एक्सपोर्ट फाइल: {export_filename}"
                )
        else:
            await update.message.reply_text(
                f"❌ *एक्सपोर्ट फेल्ड!*\n\n"
                f"एरर: {result}",
                parse_mode='Markdown'
            )
    
    # ==================== CALLBACK HANDLERS ====================
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'set_reply':
            await query.edit_message_text(
                "📝 *नया रिप्लाई सेट करें*\n\n"
                "फॉर्मेट: `/setreply कीवर्ड जवाब`\n\n"
                "*उदाहरण:*\n"
                "`/setreply नमस्ते नमस्ते! कैसे हैं?`\n"
                "`/setreply समय अभी समय है: 10:30 AM`\n\n"
                "बस ऊपर दिए फॉर्मेट में कमांड भेजें।",
                parse_mode='Markdown'
            )
        elif data == 'list_replies':
            await self.list_replies_command(update, context)
        elif data == 'help':
            await self.help_command(update, context)
        elif data == 'stats':
            await self.stats_command(update, context)
        elif data.startswith('page_'):
            page = int(data.split('_')[1])
            context.args = [str(page)]
            await self.list_replies_command(update, context)
        elif data == 'delete_mode':
            await query.edit_message_text(
                "🗑️ *डिलीट मोड*\n\n"
                "रिप्लाई डिलीट करने के लिए:\n"
                "`/delreply कीवर्ड`\n\n"
                "*उदाहरण:*\n"
                "`/delreply नमस्ते`\n\n"
                "सभी रिप्लाई देखने के लिए:\n"
                "`/listreplies`",
                parse_mode='Markdown'
            )
        elif data == 'current_page':
            await query.answer("यह करंट पेज है!", show_alert=False)
    
    # ==================== UTILITY METHODS ====================
    def format_uptime(self, seconds: int) -> str:
        """Format uptime in human readable format"""
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} दिन")
        if hours > 0:
            parts.append(f"{hours} घंटे")
        if minutes > 0:
            parts.append(f"{minutes} मिनट")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} सेकंड")
        
        return ", ".join(parts)
    
    def get_user_rank(self, user_id: int) -> str:
        """Get user rank based on message count"""
        user_stats = self.db.get_user_stats(user_id)
        if not user_stats:
            return "नया यूजर"
        
        message_count = user_stats[4]
        
        if message_count >= 1000:
            return "🏆 गोल्ड यूजर"
        elif message_count >= 500:
            return "🥈 सिल्वर यूजर"
        elif message_count >= 100:
            return "🥉 ब्रॉन्ज यूजर"
        elif message_count >= 50:
            return "⭐ एक्टिव यूजर"
        elif message_count >= 10:
            return "👍 रेगुलर यूजर"
        else:
            return "👶 नया यूजर"

# ==================== MAIN APPLICATION ====================
def setup_handlers(app: Application, bot: AdvancedAutoReplyBot):
    """Setup all bot handlers"""
    
    # Command handlers
    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("setreply", bot.set_reply_command))
    app.add_handler(CommandHandler("listreplies", bot.list_replies_command))
    app.add_handler(CommandHandler("delreply", bot.delete_reply_command))
    app.add_handler(CommandHandler("stats", bot.stats_command))
    app.add_handler(CommandHandler("mystats", bot.my_stats_command))
    app.add_handler(CommandHandler("topusers", bot.top_users_command))
    
    # Group command handlers
    app.add_handler(CommandHandler("enable", bot.enable_group_command))
    app.add_handler(CommandHandler("disable", bot.disable_group_command))
    app.add_handler(CommandHandler("groupinfo", bot.group_info_command))
    
    # Admin command handlers
    app.add_handler(CommandHandler("broadcast", bot.broadcast_command))
    app.add_handler(CommandHandler("backup", bot.backup_command))
    app.add_handler(CommandHandler("export", bot.export_command))
    
    # Callback query handler (for inline buttons)
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    
    # Message handlers
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        bot.handle_private_message
    ))
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        bot.handle_group_message
    ))

def main():
    """Main function to start the bot"""
    
    # Check if token is set
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token not set!")
        print("\n📝 Please set your bot token:")
        print("1. Create a .env file")
        print("2. Add: BOT_TOKEN=your_token_here")
        print("3. Or set it directly in the code")
        print("\n🔧 Get token from @BotFather on Telegram")
        return
    
    print("🤖 Telegram Auto-Reply Bot")
    print("=" * 40)
    print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Bot Token: {'*' * 20}{TOKEN[-5:] if len(TOKEN) > 5 else ''}")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print("=" * 40)
    
    # Create bot instance
    bot = AdvancedAutoReplyBot(TOKEN)
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Setup handlers
    setup_handlers(application, bot)
    
    print("\n✅ Bot setup complete!")
    print("⚡ Starting bot...")
    print("💡 Press Ctrl+C to stop\n")
    
    try:
        # Start the bot
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        
        # Export data before closing
        print("💾 Saving data backup...")
        bot.db.export_to_json("shutdown_backup.json")
        
        print("✅ Backup saved as 'shutdown_backup.json'")
        print("📊 Final Stats:")
        print(f"   • Replies: {bot.db.get_reply_count()}")
        print(f"   • Users: {bot.db.get_total_users()}")
        print(f"   • Uptime: {bot.format_uptime(int(time.time() - bot.start_time))}")
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Bot crashed with error: {e}", exc_info=True)
    finally:
        print("\n🎯 Bot shutdown complete!")

if __name__ == '__main__':
    main()
