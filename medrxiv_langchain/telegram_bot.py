"""
Telegram Bot for BioRxiv/MedRxiv Paper Search and Processing.

This bot provides a conversational interface to search, summarize,
and analyze papers from BioRxiv and MedRxiv preprint servers.

Commands:
- /start - Welcome message and introduction
- /help - List available commands
- /search <keywords> - Search for papers
- /recent [days] - Get recent papers (default: 7 days)
- /servers <biorxiv|medrxiv|both> - Set server preference
- /summarize - Summarize papers from last search
- /similar <text> - Find semantically similar papers
- /export [json|csv] - Export last search results
- /health - Check API health status
- /settings - View current settings
"""

import os
import io
import csv
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatAction

# Import our API components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from medrxiv_langchain.loader import BioRxivLoader
from medrxiv_langchain.query_builder_enhanced import EnhancedQueryBuilder

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MAX_RESULTS_DEFAULT = 10
MAX_MESSAGE_LENGTH = 4096


# ============================================================================
# User Session Storage
# ============================================================================

# Store user sessions (in production, use Redis or database)
user_sessions: Dict[int, Dict[str, Any]] = {}


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Get or create user session."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'servers': ['biorxiv'],
            'max_results': MAX_RESULTS_DEFAULT,
            'last_search': None,
            'last_papers': [],
            'language': 'en'
        }
    return user_sessions[user_id]


# ============================================================================
# Decorators
# ============================================================================

def send_typing_action(func):
    """Send typing action while processing."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )
        return await func(update, context, *args, **kwargs)
    return wrapper


# ============================================================================
# Helper Functions
# ============================================================================

def format_paper(paper: Dict[str, Any], index: int = None) -> str:
    """Format a single paper for display."""
    title = paper.get('title', 'No title')
    authors = paper.get('authors', 'Unknown authors')
    date = paper.get('date', 'Unknown date')
    server = paper.get('server', 'unknown')
    doi = paper.get('doi', '')
    abstract = paper.get('abstract', '')[:200] + '...' if paper.get('abstract') else 'No abstract'

    # Truncate long author lists
    if len(authors) > 100:
        authors = authors[:100] + '...'

    prefix = f"*{index}.* " if index else ""

    return f"""{prefix}*{title}*

📅 {date} | 🏛 {server.upper()}
👥 {authors}

📝 {abstract}

🔗 [View Paper](https://doi.org/{doi})
"""


def truncate_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate message to fit Telegram limits."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued."""
    user = update.effective_user
    session = get_user_session(user.id)

    welcome_message = f"""
👋 *Welcome to BioRxiv/MedRxiv Bot, {user.first_name}!*

I can help you search and analyze preprints from BioRxiv and MedRxiv.

*Quick Start:*
• `/search COVID-19 vaccine` - Search for papers
• `/recent 7` - Get papers from last 7 days
• `/help` - See all commands

*Current Settings:*
• Servers: {', '.join(session['servers'])}
• Max results: {session['max_results']}

Let's find some papers! 🔬📚
"""

    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message with available commands."""
    help_text = """
*📚 Available Commands*

*Search & Browse:*
• `/search <keywords>` - Search for papers
  Example: `/search CRISPR gene editing`

• `/recent [days]` - Get recent papers
  Example: `/recent 7` (default: 7 days)

• `/category <name>` - Filter by category
  Example: `/category genomics`

*Analysis:*
• `/summarize` - Summarize last search results
• `/similar <text>` - Find similar papers
  Example: `/similar genome sequencing methods`

*Export:*
• `/export [json|csv]` - Export results
  Example: `/export csv`

*Settings:*
• `/servers <biorxiv|medrxiv|both>` - Set servers
• `/limit <number>` - Set max results
• `/settings` - View current settings

*System:*
• `/health` - Check API status
• `/stats` - Usage statistics
• `/help` - Show this help

*Tips:*
💡 Use quotes for phrases: `/search "machine learning"`
💡 Combine keywords: `/search COVID vaccine efficacy`
"""

    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )


@send_typing_action
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for papers by keywords."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Get keywords from command arguments
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide keywords.\n\nExample: `/search COVID-19 vaccine`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keywords = ' '.join(context.args)

    await update.message.reply_text(
        f"🔍 Searching for: *{keywords}*\n\nPlease wait...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        # Build query
        query = (EnhancedQueryBuilder()
            .with_keywords(keywords.split())
            .last_days(30)
            .from_servers(session['servers'])
            .build())

        # Execute search
        loader = BioRxivLoader(**query, max_results=session['max_results'])
        documents = loader.load()

        if not documents:
            await update.message.reply_text(
                "😕 No papers found. Try different keywords or a longer time range."
            )
            return

        # Convert to paper dicts
        papers = []
        for doc in documents:
            paper = doc.metadata.copy()
            paper['abstract'] = doc.page_content.split('\n\n')[-1] if doc.page_content else ''
            papers.append(paper)

        # Store in session
        session['last_search'] = keywords
        session['last_papers'] = papers

        # Format results
        result_text = f"📊 *Found {len(papers)} papers for '{keywords}'*\n\n"

        for i, paper in enumerate(papers[:5], 1):  # Show first 5
            result_text += format_paper(paper, i) + "\n---\n\n"

        if len(papers) > 5:
            result_text += f"\n_...and {len(papers) - 5} more papers._\n"
            result_text += "\nUse `/export` to get all results."

        # Send with inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📝 Summarize", callback_data="summarize"),
                InlineKeyboardButton("📥 Export", callback_data="export_json")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            truncate_message(result_text),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Search failed: {str(e)}\n\nPlease try again later."
        )


@send_typing_action
async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get recent papers."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    # Get days from argument (default: 7)
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
            if days <= 0 or days > 365:
                raise ValueError("Invalid days")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid number of days. Use 1-365.\n\nExample: `/recent 7`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    await update.message.reply_text(
        f"📅 Getting papers from the last *{days} days*...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        # Build query
        query = (EnhancedQueryBuilder()
            .last_days(days)
            .from_servers(session['servers'])
            .build())

        # Execute search
        loader = BioRxivLoader(**query, max_results=session['max_results'])
        documents = loader.load()

        if not documents:
            await update.message.reply_text(
                f"😕 No papers found in the last {days} days."
            )
            return

        # Convert and store
        papers = []
        for doc in documents:
            paper = doc.metadata.copy()
            paper['abstract'] = doc.page_content.split('\n\n')[-1] if doc.page_content else ''
            papers.append(paper)

        session['last_search'] = f"Recent ({days} days)"
        session['last_papers'] = papers

        # Format results
        result_text = f"📊 *{len(papers)} papers from last {days} days*\n\n"

        for i, paper in enumerate(papers[:5], 1):
            result_text += format_paper(paper, i) + "\n---\n\n"

        if len(papers) > 5:
            result_text += f"\n_...and {len(papers) - 5} more._"

        keyboard = [
            [
                InlineKeyboardButton("📝 Summarize", callback_data="summarize"),
                InlineKeyboardButton("📥 Export", callback_data="export_json")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            truncate_message(result_text),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Recent papers error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Failed to get recent papers: {str(e)}"
        )


async def servers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set server preference."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if not context.args:
        await update.message.reply_text(
            f"*Current servers:* {', '.join(session['servers'])}\n\n"
            "Usage: `/servers <biorxiv|medrxiv|both>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    choice = context.args[0].lower()

    if choice == 'biorxiv':
        session['servers'] = ['biorxiv']
    elif choice == 'medrxiv':
        session['servers'] = ['medrxiv']
    elif choice == 'both':
        session['servers'] = ['biorxiv', 'medrxiv']
    else:
        await update.message.reply_text(
            "❌ Invalid choice. Use: `biorxiv`, `medrxiv`, or `both`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text(
        f"✅ Servers set to: *{', '.join(session['servers'])}*",
        parse_mode=ParseMode.MARKDOWN
    )


async def limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set maximum results limit."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if not context.args:
        await update.message.reply_text(
            f"*Current limit:* {session['max_results']}\n\n"
            "Usage: `/limit <number>` (1-100)",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        limit = int(context.args[0])
        if limit < 1 or limit > 100:
            raise ValueError("Out of range")

        session['max_results'] = limit
        await update.message.reply_text(
            f"✅ Max results set to: *{limit}*",
            parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Use 1-100.",
            parse_mode=ParseMode.MARKDOWN
        )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current settings."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    settings_text = f"""
*⚙️ Current Settings*

• *Servers:* {', '.join(session['servers'])}
• *Max results:* {session['max_results']}
• *Last search:* {session['last_search'] or 'None'}
• *Papers in cache:* {len(session['last_papers'])}

*Commands to change:*
• `/servers <biorxiv|medrxiv|both>`
• `/limit <number>`
"""

    await update.message.reply_text(
        settings_text,
        parse_mode=ParseMode.MARKDOWN
    )


@send_typing_action
async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarize papers from last search."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if not session['last_papers']:
        await update.message.reply_text(
            "❌ No papers to summarize. Run a search first with `/search`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text(
        "📝 Generating summaries... This may take a moment."
    )

    try:
        # Simple summarization (truncate abstracts)
        # In production, use actual summarization engine
        summaries = []

        for i, paper in enumerate(session['last_papers'][:5], 1):
            abstract = paper.get('abstract', '')[:300]
            if len(paper.get('abstract', '')) > 300:
                abstract += '...'

            summary = f"*{i}. {paper['title'][:80]}*\n{abstract}\n"
            summaries.append(summary)

        result_text = f"*📝 Summary of {len(summaries)} papers*\n\n"
        result_text += "\n---\n\n".join(summaries)

        await update.message.reply_text(
            truncate_message(result_text),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Summarize error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Summarization failed: {str(e)}"
        )


@send_typing_action
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export papers to file."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    if not session['last_papers']:
        await update.message.reply_text(
            "❌ No papers to export. Run a search first with `/search`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Determine format
    export_format = 'json'
    if context.args and context.args[0].lower() in ['json', 'csv']:
        export_format = context.args[0].lower()

    try:
        if export_format == 'json':
            # Export as JSON
            data = {
                'search': session['last_search'],
                'exported_at': datetime.utcnow().isoformat(),
                'papers': session['last_papers']
            }

            output = io.BytesIO()
            output.write(json.dumps(data, indent=2).encode('utf-8'))
            output.seek(0)

            await update.message.reply_document(
                document=output,
                filename=f"papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                caption=f"📥 Exported {len(session['last_papers'])} papers as JSON"
            )

        else:  # CSV
            output = io.StringIO()
            fieldnames = ['doi', 'title', 'authors', 'date', 'category', 'server', 'abstract']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for paper in session['last_papers']:
                row = {field: paper.get(field, '') for field in fieldnames}
                writer.writerow(row)

            output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
            output_bytes.seek(0)

            await update.message.reply_document(
                document=output_bytes,
                filename=f"papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                caption=f"📥 Exported {len(session['last_papers'])} papers as CSV"
            )

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Export failed: {str(e)}"
        )


@send_typing_action
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check API health status."""
    import requests

    await update.message.reply_text("🔍 Checking API status...")

    status_text = "*🏥 Health Status*\n\n"

    for server in ['biorxiv', 'medrxiv']:
        try:
            start_time = datetime.now()
            response = requests.get(
                f"https://api.biorxiv.org/details/{server}/2024-01-01/2024-01-02/0/json",
                timeout=5
            )
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                status_text += f"✅ *{server.upper()}*: Online ({response_time:.0f}ms)\n"
            else:
                status_text += f"⚠️ *{server.upper()}*: Degraded (Status: {response.status_code})\n"

        except Exception as e:
            status_text += f"❌ *{server.upper()}*: Offline ({str(e)[:30]})\n"

    status_text += f"\n_Checked at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_"

    await update.message.reply_text(
        status_text,
        parse_mode=ParseMode.MARKDOWN
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage statistics."""
    user_id = update.effective_user.id
    session = get_user_session(user_id)

    stats_text = f"""
*📊 Your Statistics*

• Papers in cache: {len(session['last_papers'])}
• Last search: {session['last_search'] or 'None'}
• Active sessions: {len(user_sessions)}
"""

    await update.message.reply_text(
        stats_text,
        parse_mode=ParseMode.MARKDOWN
    )


# ============================================================================
# Callback Query Handler
# ============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks."""
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    if query.data == "summarize":
        # Trigger summarize
        session = get_user_session(user_id)
        if session['last_papers']:
            await query.message.reply_text("📝 Generating summaries...")

            summaries = []
            for i, paper in enumerate(session['last_papers'][:3], 1):
                abstract = paper.get('abstract', '')[:200]
                summary = f"*{i}.* {paper['title'][:60]}...\n_{abstract}_\n"
                summaries.append(summary)

            await query.message.reply_text(
                "\n".join(summaries),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text("No papers to summarize.")

    elif query.data == "export_json":
        session = get_user_session(user_id)
        if session['last_papers']:
            data = {'papers': session['last_papers']}
            output = io.BytesIO(json.dumps(data, indent=2).encode('utf-8'))
            output.seek(0)

            await query.message.reply_document(
                document=output,
                filename=f"papers.json",
                caption=f"📥 {len(session['last_papers'])} papers"
            )
        else:
            await query.message.reply_text("No papers to export.")


# ============================================================================
# Message Handler
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command messages."""
    text = update.message.text.lower()

    # Simple intent detection
    if any(word in text for word in ['search', 'find', 'look for']):
        await update.message.reply_text(
            "To search for papers, use:\n`/search <keywords>`\n\n"
            "Example: `/search machine learning genomics`",
            parse_mode=ParseMode.MARKDOWN
        )
    elif any(word in text for word in ['help', 'how', 'what']):
        await help_command(update, context)
    else:
        await update.message.reply_text(
            "I'm not sure what you mean. Try `/help` to see available commands. 🤔"
        )


# ============================================================================
# Error Handler
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )


# ============================================================================
# Main Application
# ============================================================================

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("\nTo use the Telegram bot:")
        print("1. Create a bot via @BotFather on Telegram")
        print("2. Set the token: export TELEGRAM_BOT_TOKEN='your_token_here'")
        print("3. Run this script again")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("servers", servers_command))
    application.add_handler(CommandHandler("limit", limit_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("summarize", summarize_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Add callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add message handler for non-commands
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting Telegram bot...")
    print("🤖 BioRxiv/MedRxiv Telegram Bot is running!")
    print("Press Ctrl+C to stop.\n")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
