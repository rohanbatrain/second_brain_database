from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from bson import ObjectId
from sbd_rohanbatrain.features.project.project_create import add_project, view_projects
from sbd_rohanbatrain.features.project.project_delete import delete_project

from sbd_rohanbatrain.config_files.config import TELEGRAM_BOT_TOKEN

# Define states for the conversation
MAIN_MENU, PROJECT_MENU, NAME, DESCRIPTION, PRIORITY = range(5)

# Helper function to format project details
def format_project_details(project):
    # Ensure the key exists before accessing it
    creation_time = project.get('creation_time', 'N/A')  # Default to 'N/A' if not found
    return (
        f"📌 *Name*: {project['name']}\n"
        f"📝 *Description*: {project['description']}\n"
        f"⭐ *Priority*: {project['priority'].capitalize()}\n"
        f"📅 *Created On*: {project['creation_date']}\n"
        f"🆔 *ID*: {project['_id']}\n"
    )

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Please choose an option.",
        reply_markup=ReplyKeyboardMarkup([["Projects"]], resize_keyboard=True),
    )
    return MAIN_MENU

# Handle the main menu
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text == "projects":
        await update.message.reply_text(
            "⚙️ *Project Management Commands:*\n\n"
            "👀 View Projects\n"
            "➕ Add Project\n"
            "❌ Delete Project\n\n"
            "Please choose an option:",
            reply_markup=ReplyKeyboardMarkup(
                [["View Projects", "Add Project"], ["Delete Project", "Back"]], resize_keyboard=True
            ),
            parse_mode="Markdown",
        )
        return PROJECT_MENU
    else:
        await update.message.reply_text("Invalid option. Please choose from the buttons.")
        return MAIN_MENU

# Handle project menu options
async def project_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text == "view projects":
        await projects_view(update, context)
    elif text == "add project":
        await projects_add(update, context)
        return NAME
    elif text == "delete project":
        await update.message.reply_text(
            "Please provide the ID of the project you want to delete."
        )
        context.user_data["delete_mode"] = True
        return PROJECT_MENU
    elif text == "back":
        await start(update, context)
        return MAIN_MENU
    else:
        await update.message.reply_text("Invalid option. Please choose from the buttons.")
        return PROJECT_MENU

# Subcommand: View all projects
async def projects_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    projects_list = view_projects()
    if projects_list:
        response = "📋 *Your Projects:*\n\n"
        for project in projects_list:
            response += format_project_details(project) + "\n"
        await update.message.reply_text(
            response,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["View Projects", "Add Project"], ["Delete Project", "Back"]], resize_keyboard=True
            ),
        )
    else:
        await update.message.reply_text(
            "⚠️ *No projects found.*\nYou can create one using *Add Project*.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["View Projects", "Add Project"], ["Delete Project", "Back"]], resize_keyboard=True
            ),
        )

# Subcommand: Add a project
async def projects_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Let's create a new project!*\n\nPlease provide the *name* of the project:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return NAME

# Subcommand: Delete a project
async def projects_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_id = update.message.text
    if context.user_data.get("delete_mode"):
        result = delete_project(project_id)
        context.user_data["delete_mode"] = False
        if result > 0:
            await update.message.reply_text(
                f"✅ *Project with ID {project_id} deleted successfully!*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    [["View Projects", "Add Project"], ["Delete Project", "Back"]], resize_keyboard=True
                ),
            )
        else:
            await update.message.reply_text(
                f"❌ *Project with ID {project_id} not found.*",
                parse_mode="Markdown",
            )

# Conversation handlers for project creation
async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "💡 Great! Now, please provide a *brief description* of the project:",
        parse_mode="Markdown",
    )
    return DESCRIPTION

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text(
        "🔖 Finally, set the *priority* (low, medium, high):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["Low", "Medium", "High"]], resize_keyboard=True),
    )
    return PRIORITY

async def handle_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    priority = update.message.text.lower()

    # Validate priority
    if priority not in ["low", "medium", "high"]:
        await update.message.reply_text(
            "⚠️ *Invalid priority!*\nPlease choose from the buttons.",
            parse_mode="Markdown",
        )
        return PRIORITY

    # Store the valid priority and proceed
    context.user_data["priority"] = priority
    name = context.user_data["name"]
    description = context.user_data["description"]
    
    # Add the project to the database
    project_id = add_project(name, description, priority)

    await update.message.reply_text(
        f"🎉 *Project '{name}' created successfully!*\n\n"
        f"🆔 *Project ID*: {project_id}\n"
        "You can view all projects using *View Projects*.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["View Projects", "Add Project"], ["Delete Project", "Back"]], resize_keyboard=True
        ),
    )
    return PROJECT_MENU

# Define the conversation handler for adding projects
def add_project_conversation():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            PROJECT_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, project_menu)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_priority)],
        },
        fallbacks=[],
    )

# Main function to run the bot
def main():
    bot_token = TELEGRAM_BOT_TOKEN
    app = ApplicationBuilder().token(bot_token).build()

    # Add Handlers
    app.add_handler(add_project_conversation())

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
