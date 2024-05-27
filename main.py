import asyncio
import datetime
import sqlite3
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from telethon import TelegramClient
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors import PhoneNumberBannedError
import logging
import random
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
import os
from telethon.errors import RPCError
import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import PeerUser

API_ID = ''
API_HASH = ''
PHONE_NUMBER = ''
BOT_TOKEN = ''

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
telethon_client = TelegramClient('session', API_ID, API_HASH)
dp.middleware.setup(LoggingMiddleware())

class AccountMenu(StatesGroup):
    main_menu = State()

class FilterBannedState(StatesGroup):
    waiting_for_code = State()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('mydatabase.db')
    cur = conn.cursor()
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL
        )
        ''')

        cur.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            api_id TEXT,
            api_hash TEXT,
            phone_number TEXT,
            UNIQUE(api_id, api_hash, phone_number)
        )
        ''')

        conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing the database: {str(e)}")
    finally:
        conn.close()


class SendMessageState(StatesGroup):
    waiting_for_channel_link = State()
    waiting_for_message_text = State()
    waiting_for_delay = State()
    waiting_for_confirmation = State()
    waiting_for_verification_code = State()


@dp.message_handler(state=FilterBannedState.waiting_for_code, content_types=types.ContentType.TEXT)
async def input_verification_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    async with state.proxy() as data:
        phone_number = data['phone_number']
        api_id = data['api_id']
        api_hash = data['api_hash']
        phone_code_hash = data['phone_code_hash']

    client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
    await client.connect()
    try:
        await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        await message.answer("You have been successfully logged in.")
        await client.disconnect()
        await state.finish()
    except Exception as e:
        logger.error(f"Failed to verify code for {phone_number}: {e}")
        await message.answer("The code entered was invalid. Please ensure the code is correct and try again, or request a new code.")
        await client.disconnect()
        await state.set_state(FilterBannedState.waiting_for_code)


async def show_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("Add Account", callback_data="add_account"),
        InlineKeyboardButton("List of Accounts", callback_data="list_accounts"),
        InlineKeyboardButton("Delete Account", callback_data="delete_account"),
        InlineKeyboardButton("Filter Banned Accounts", callback_data="filter_banned_accounts")
    ]
    keyboard.add(*buttons)
    await message.answer("Choose an option:", reply_markup=keyboard)

@dp.message_handler(commands=['menu'], state="*")
async def menu(message: types.Message, state: FSMContext):
    await state.finish()
    await AccountMenu.main_menu.set()
    await show_menu(message)


async def add_account(message: types.Message, state: FSMContext):
    await message.answer("Enter API ID, API Hash, and Phone Number separated by commas (e.g., 1234567,abcdef1234567890,+1234567890):")

@dp.callback_query_handler(lambda c: c.data == "add_account", state=AccountMenu.main_menu)
async def add_account_callback(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Enter API ID, API Hash, and Phone Number separated by commas (e.g., 1234567,abcdef1234567890,+1234567890):")

sent_message_count = 0
parsed_channel_count = 0
last_successful_delivery = None


async def reset_counters():
    global sent_message_count, parsed_channel_count
    sent_message_count = 0
    parsed_channel_count = 0


async def reset_counters_daily():
    while True:
        now = datetime.datetime.now()
        reset_time = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1)
        delta = reset_time - now
        await asyncio.sleep(delta.total_seconds())
        await reset_counters()

async def process_account_info(message: types.Message):
    account_info = message.text.split(',')
    if len(account_info) != 3:
        await message.answer("Invalid input format. Please enter API ID, API Hash, and Phone Number separated by commas.")
        return

    api_id, api_hash, phone_number = account_info

    conn = sqlite3.connect('accounts.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO accounts (api_id, api_hash, phone_number) VALUES (?, ?, ?)', (api_id.strip(), api_hash.strip(), phone_number.strip()))
    conn.commit()
    conn.close()

    await message.answer("Account added successfully.")

@dp.message_handler(state=AccountMenu.main_menu)
async def handle_account_info(message: types.Message, state: FSMContext):
    await process_account_info(message)
    await show_menu(message)


def init_db():
    conn = sqlite3.connect('mydatabase.db')
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL
    )
    ''')
    conn.commit()
    conn.close()


async def add_user(user_id):
    conn = sqlite3.connect('mydatabase.db')
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f'User with ID {user_id} already exists.')
    finally:
        conn.close()


async def remove_user(user_id):
    conn = sqlite3.connect('mydatabase.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


async def add_user_command(message: types.Message):
    admin_id = 0000000  # Replace with your Telegram ID
    if message.from_user.id == admin_id:
        args = message.get_args().split()
        if args and args[0].isdigit():
            user_id = int(args[0])
            await add_user(user_id)
            await message.reply(f"User {user_id} added.")
        else:
            await message.reply("Please, enter user ID by command: /add_user <user_id>.")
    else:
        await message.reply("You are not authorized to do this.")


async def remove_user_command(message: types.Message):
    admin_id = 0000000  # Replace with your Telegram ID
    if message.from_user.id == admin_id:
        args = message.get_args().split()
        if args and args[0].isdigit():
            user_id = int(args[0])
            await remove_user(user_id)
            await message.reply(f"User {user_id} deleted.")
        else:
            await message.reply("Please, enter user ID by command: /remove_user <user_id>.")
    else:
        await message.reply("You are not authorized to do this.")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("remove_user_"), state="*")
async def remove_user_button(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[2])
    await remove_user(user_id)
    await callback_query.answer(f"Access for user {user_id} removed.")

    users = await get_all_users()
    if not users:
        await callback_query.message.edit_text("User list is empty.")
        return

    markup = InlineKeyboardMarkup()
    for user_id, in users:
        markup.row(InlineKeyboardButton(f"User ID: {user_id}", callback_data=f"remove_user_{user_id}"))

    await callback_query.message.edit_text("Users with access:", reply_markup=markup)


async def get_all_users():
    conn = sqlite3.connect('mydatabase.db')
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM users')
    users = cur.fetchall()
    conn.close()
    return users


@dp.message_handler(commands=['user_status'], state="*")
async def user_status_command(message: types.Message):
    users = await get_all_users()
    if not users:
        await message.reply("User list is empty.")
        return

    markup = InlineKeyboardMarkup()
    for user_id, in users:
        markup.row(InlineKeyboardButton(f"User ID: {user_id}", callback_data=f"remove_user_{user_id}"))

    await message.answer("Users with access:", reply_markup=markup)


async def send_welcome(message: types.Message):
    await SendMessageState.waiting_for_channel_link.set()
    await message.answer("Send me a link or identifier of another channel to view its administrators.")


async def finish_action(message: types.Message, action_text: str, state: FSMContext):
    await message.answer(action_text)
    await state.finish()
    await send_welcome(message)


@dp.message_handler(state=SendMessageState.waiting_for_channel_link, content_types=types.ContentType.TEXT)
async def parse_channel_admins(message: types.Message, state: FSMContext):
    global parsed_channel_count

    channel_links = message.text.strip().split()
    if not channel_links:
        await message.reply("No links found. Please send a channel link or identifier.")
        return

    admin_data_combined = []

    for channel_link in channel_links:
        parsed_channel_count += 1

        try:
            entity = await telethon_client.get_entity(channel_link)
            admins = await telethon_client.get_participants(entity, filter=ChannelParticipantsAdmins)
            admin_data = [{"id": admin.id, "first_name": admin.first_name, "username": admin.username} for admin in admins]
            admin_data_combined.extend(admin_data)
        except Exception as e:
            await message.reply(f"Error processing channel {channel_link}: {str(e)}")
            continue

    if last_successful_delivery is not None and parsed_channel_count > 0:
        delta = datetime.datetime.now() - last_successful_delivery
        if delta.total_seconds() < 86400:
            await message.answer(f"{sent_message_count} messages have been sent in the last 24 hours.")
            return

    if admin_data_combined:
        await state.update_data(admin_data=admin_data_combined)

        markup = InlineKeyboardMarkup()
        for admin in admin_data_combined:
            markup.row(
                InlineKeyboardButton(f"{admin['first_name']} (@{admin['username'] if admin['username'] else 'N/A'})",
                                     callback_data=f"admin_{admin['id']}"))
        markup.row(InlineKeyboardButton("Finish selection", callback_data="finish_selection"))
        markup.row(InlineKeyboardButton("Cancel", callback_data="cancel_selection"))

        await message.reply("Channel administrators:\n" + "\n".join(
            [f"{admin['first_name']} (@{admin['username'] if admin['username'] else 'N/A'})" for admin in
             admin_data_combined]), reply_markup=markup)
    else:
        await message.reply("Could not find administrators in the specified channels. Please check the links and try again.")


@dp.callback_query_handler(lambda c: c.data == "cancel_selection", state=SendMessageState.waiting_for_channel_link)
async def cancel_admin_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await finish_action(callback_query.message, "Messaging cancelled. Enter a new channel or chat link to parse.", state)


async def delete_account(message: types.Message):
    with sqlite3.connect('accounts.db') as conn:
        cur = conn.cursor()
        cur.execute('SELECT api_id, api_hash, phone_number FROM accounts')
        accounts = cur.fetchall()

    if not accounts:
        await message.answer("No accounts found.")
        return

    keyboard = InlineKeyboardMarkup()
    for api_id, api_hash, phone_number in accounts:
        button_label = f"Delete {api_id}, {api_hash}, {phone_number}"
        callback_data = f"delete_{api_id}_{api_hash}_{phone_number}"
        keyboard.add(InlineKeyboardButton(button_label, callback_data=callback_data))

    await message.answer("Choose an account to delete:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def delete_account_callback(callback_query: types.CallbackQuery):
    _, api_id, api_hash, phone_number = callback_query.data.split('_', 3)

    with sqlite3.connect('accounts.db') as conn:
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM accounts WHERE api_id=? AND api_hash=? AND phone_number=?',
                        (api_id, api_hash, phone_number))
            deleted = cur.rowcount
            conn.commit()
            if deleted == 0:
                await callback_query.answer("No such account found.", show_alert=True)
                return

            session_file = f'session_{phone_number}.session'
            if os.path.exists(session_file):
                os.remove(session_file)

            await callback_query.answer("Account deleted successfully.", show_alert=True)
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            await callback_query.answer(f"Failed to delete account from database: {str(e)}", show_alert=True)
        except Exception as e:
            logging.error(f"General error: {e}")
            await callback_query.answer(f"Failed to delete session file: {str(e)}", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "filter_banned_accounts", state=AccountMenu.main_menu)
async def filter_banned_accounts_menu_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await filter_banned_accounts(callback_query, state)


async def list_accounts(message: types.Message):
    conn = sqlite3.connect('accounts.db')
    cur = conn.cursor()
    cur.execute('SELECT * FROM accounts')
    accounts = cur.fetchall()
    conn.close()

    if not accounts:
        await message.answer("No accounts found.")
        return

    accounts_text = "List of accounts:\n"
    for account in accounts:
        accounts_text += f"API ID: {account[0]}, API Hash: {account[1]}, Phone Number: {account[2]}\n"

    await message.answer(accounts_text)

@dp.callback_query_handler(lambda c: c.data == "list_accounts", state=AccountMenu.main_menu)
async def list_accounts_menu_callback(callback_query: types.CallbackQuery):
    await list_accounts(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == "delete_account", state=AccountMenu.main_menu)
async def delete_account_menu_callback(callback_query: types.CallbackQuery):
    await delete_account(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == "list_accounts", state=AccountMenu.main_menu)
async def list_accounts_menu_callback(callback_query: types.CallbackQuery):
    await list_accounts(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == "filter_banned_accounts", state=AccountMenu.main_menu)
async def filter_banned_accounts(callback_query: types.CallbackQuery, state: FSMContext):
    message = callback_query.message
    logger.info("Filtering banned accounts.")

    conn = sqlite3.connect('accounts.db')
    cur = conn.cursor()
    cur.execute('SELECT * FROM accounts')
    accounts = cur.fetchall()
    conn.close()

    if not accounts:
        await message.answer("No accounts found.")
        return

    for account in accounts:
        api_id, api_hash, phone_number = account
        client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                result = await client.send_code_request(phone_number)
                async with state.proxy() as data:
                    data['phone_number'] = phone_number
                    data['api_id'] = api_id
                    data['api_hash'] = api_hash
                    data['phone_code_hash'] = result.phone_code_hash
                await state.set_state(FilterBannedState.waiting_for_code)
                await message.answer("Please enter the verification code you received:", reply_markup=types.ForceReply(selective=True))
                return
            await message.answer(f"Logged in successfully with phone number {phone_number}.")
            await client.disconnect()
        except PhoneNumberBannedError:
            await message.answer(f"Account with phone number {phone_number} is banned.")
            cur = conn.cursor()
            cur.execute('DELETE FROM accounts WHERE phone_number=?', (phone_number,))
            conn.commit()
            await client.disconnect()
        except Exception as e:
            await message.answer(f"Failed to login with phone number {phone_number}: {e}")
            await client.disconnect()


async def login_account(client: TelegramClient, message: types.Message):
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(PHONE_NUMBER)
            await message.answer("Please enter the code you received:", reply_markup=types.ForceReply(selective=True))
            await SendMessageState.waiting_for_verification_code.set()
            await state.update_data(client=client)
    except Exception as e:
        await client.disconnect()
        await message.answer(f"Error during login attempt: {str(e)}")


@dp.callback_query_handler(lambda c: c.data == "finish_selection", state=SendMessageState.waiting_for_channel_link)
async def finish_admin_selection(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    admin_data = data.get('admin_data', [])

    if not admin_data:
        await finish_action(callback_query.message, "No administrators left for messaging. Enter a new channel or chat link to parse.", state)
        return

    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.answer("Enter the message text.")
    await SendMessageState.waiting_for_message_text.set()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_"),
                           state=SendMessageState.waiting_for_channel_link)
async def admin_selection(callback_query: types.CallbackQuery, state: FSMContext):
    admin_id = int(callback_query.data.split('_')[1])
    data = await state.get_data()
    admin_data = data['admin_data']
    admin_data = [admin for admin in admin_data if admin['id'] != admin_id]

    await state.update_data(admin_data=admin_data)

    markup = InlineKeyboardMarkup()
    for admin in admin_data:
        markup.row(InlineKeyboardButton(f"{admin['first_name']} (@{admin['username'] if admin['username'] else 'N/A'})",
                                        callback_data=f"admin_{admin['id']}"))
    markup.row(InlineKeyboardButton("Finish selection", callback_data="finish_selection"))

    await callback_query.message.edit_text("Select administrators to exclude from messaging:", reply_markup=markup)
    await callback_query.answer()


@dp.message_handler(state=SendMessageState.waiting_for_delay, content_types=types.ContentType.TEXT)
async def request_delay(message: types.Message, state: FSMContext):
    delay = message.text
    try:
        delay = int(delay)
        if delay <= 0:
            raise ValueError
        await state.update_data(delay=delay)
        confirmation_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        confirmation_keyboard.add(types.KeyboardButton(text="Yes"), types.KeyboardButton(text="No"))
        await message.answer("Are you ready to start messaging?", reply_markup=confirmation_keyboard)
        await SendMessageState.waiting_for_confirmation.set()
    except ValueError:
        await message.reply("Please enter a positive integer for the delay.")


async def handle_confirmation(message: types.Message, state: FSMContext):
    remove_keyboard = types.ReplyKeyboardRemove()
    if message.text.lower() == 'yes':
        await send_messages(message, state)
    elif message.text.lower() == 'no':
        await finish_action(message, "Messaging cancelled.", state)
    else:
        await message.answer("Please select 'Yes' or 'No'.", reply_markup=remove_keyboard)


async def get_user_entity(client, user_id):
    try:
        return await client.get_input_entity(PeerUser(user_id))
    except ValueError as e:
        logger.error(f"Cannot resolve entity for user ID {user_id}: {str(e)}")
        return None


async def send_messages(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_data = data.get('admin_data', [])
    message_text = data.get('message_text', '')
    delay = data.get('delay', 1)

    if not admin_data:
        await message.reply("No administrators available for message sending.")
        return

    conn = sqlite3.connect('accounts.db')
    cur = conn.cursor()
    cur.execute('SELECT api_id, api_hash, phone_number FROM accounts')
    accounts = cur.fetchall()
    conn.close()

    for api_id, api_hash, phone_number in accounts:
        async with TelegramClient(f'session_{phone_number}', api_id, api_hash) as client:
            await client.connect()
            if await client.is_user_authorized():
                for admin in admin_data:
                    try:
                        entity = await client.get_input_entity(PeerUser(admin['id']))
                        await client.send_message(entity, message_text)
                        global sent_message_count
                        sent_message_count += 1
                        global last_successful_delivery
                        last_successful_delivery = datetime.datetime.now()
                        await asyncio.sleep(delay)
                    except Exception as e:
                        logger.error(f"Error sending message with {phone_number}: {str(e)}")
            else:
                logger.error(f"Login required for phone number {phone_number}")

    await finish_action(message, f"Messages successfully sent. Total messages sent in the last 24 hours: {sent_message_count}", state)


@dp.message_handler(state=SendMessageState.waiting_for_message_text, content_types=types.ContentType.TEXT)
async def message_text_input(message: types.Message, state: FSMContext):
    await state.update_data(message_text=message.text)
    await SendMessageState.waiting_for_delay.set()
    await message.answer("Enter the time delay in seconds between sending messages.")


async def main():
    init_db()
    global sent_message_count, parsed_channel_count, last_successful_delivery

    asyncio.create_task(reset_counters_daily())

    await telethon_client.start(phone=lambda: PHONE_NUMBER)

    dp.register_message_handler(add_user_command, commands=['add_user'], state="*")
    dp.register_message_handler(remove_user_command, commands=['remove_user'], state="*")

    dp.register_message_handler(send_welcome, commands=['start'], state="*")
    dp.register_message_handler(parse_channel_admins, state=SendMessageState.waiting_for_channel_link, content_types=['text'])
    dp.register_message_handler(message_text_input, state=SendMessageState.waiting_for_message_text, content_types=types.ContentType.TEXT)
    dp.register_message_handler(request_delay, state=SendMessageState.waiting_for_delay, content_types=types.ContentType.TEXT)
    dp.register_message_handler(handle_confirmation, state=SendMessageState.waiting_for_confirmation, content_types=types.ContentType.TEXT)
    dp.register_message_handler(menu, commands=['menu'], state="*")
    dp.register_callback_query_handler(add_account_callback, text="add_account", state=AccountMenu.main_menu)
    dp.register_message_handler(add_account, state=AccountMenu.main_menu)

    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
