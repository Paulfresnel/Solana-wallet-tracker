import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp
import json
from datetime import datetime, timedelta
import base58
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
import traceback
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
import locale

# Load environment variables
load_dotenv()

# Get the bot token from the environment variable
TOKEN = os.getenv('BOT_TOKEN')
ALCHEMY_API_KEY = os.getenv('ALCHEMY_API_KEY')
ALCHEMY_URL = f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
BITQUERY_API_KEY = os.getenv('BITQUERY_API_KEY')

# Dictionary to store user-wallet mappings
user_wallets = {}

# List of main tokens to filter out
MAIN_TOKENS = {'SOL', 'USDC', 'USDT', 'JUP', 'PYUSD'}  # Add more main tokens as needed

# Set locale for number formatting
locale.setlocale(locale.LC_ALL, '')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to the Solana Wallet Tracker Bot! Use /track <wallet_address> to start tracking a wallet.")

async def track_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Please provide a wallet address. Usage: /track <wallet_address>")
        return

    wallet_address = context.args[0]
    user_id = update.effective_user.id
    user_wallets[user_id] = wallet_address

    keyboard = [
        [InlineKeyboardButton("Wallet Worth", callback_data=f"worth_{wallet_address}")],
        [InlineKeyboardButton("Latest Memecoin Transaction", callback_data=f"memecoins_1_{wallet_address}")],
        [InlineKeyboardButton("Latest 3 Memecoin Transactions", callback_data=f"memecoins_3_{wallet_address}")],
        [InlineKeyboardButton("Transaction Frequency", callback_data=f"frequency_{wallet_address}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Now tracking wallet: {wallet_address}\nWhat would you like to know?", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, *params = query.data.split('_')
    wallet_address = params[-1]

    # Show loading message
    loading_message = await query.edit_message_text("Loading... Please wait.")

    try:
        if action == "worth":
            sol_worth, total_worth = await get_wallet_worth(wallet_address)
            message = f"SOL Holdings: {sol_worth:.2f} SOL\n"
            message += f"Total Wallet Worth: {total_worth:.2f} (in SOL equivalent)"
        elif action == "memecoins":
            limit = int(params[0])
            transactions = await get_memecoin_transactions(wallet_address, limit)
            if transactions:
                message = f"Latest {limit} Memecoin Transaction{'s' if limit > 1 else ''}:\n\n" + "\n\n".join(transactions)
            else:
                message = "No recent memecoin transactions found."
        elif action == "frequency":
            frequency = await get_transaction_frequency(wallet_address)
            message = f"Transaction Frequency: {frequency} transactions per day"
        
        # Create inline keyboard
        keyboard = [
            [InlineKeyboardButton("Wallet Worth", callback_data=f"worth_{wallet_address}")],
            [InlineKeyboardButton("Latest Memecoin Transaction", callback_data=f"memecoins_1_{wallet_address}")],
            [InlineKeyboardButton("Latest 3 Memecoin Transactions", callback_data=f"memecoins_3_{wallet_address}")],
            [InlineKeyboardButton("Transaction Frequency", callback_data=f"frequency_{wallet_address}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message with inline keyboard
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        error_message = f"An error occurred while processing your request: {str(e)}"
        await query.edit_message_text(error_message)

async def get_wallet_worth(wallet_address):
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ALCHEMY_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                sol_worth = 0
                total_worth = 0
                for account in data.get('result', {}).get('value', []):
                    balance = int(account['account']['data']['parsed']['info']['tokenAmount']['amount'])
                    decimals = account['account']['data']['parsed']['info']['tokenAmount']['decimals']
                    mint = account['account']['data']['parsed']['info']['mint']
                    token_balance = balance / (10 ** decimals)
                    
                    if mint == "So11111111111111111111111111111111111111112":  # SOL mint address
                        sol_worth += token_balance
                    
                    # Here you would need to get the token price from an API
                    # For simplicity, we're just summing up the balances
                    total_worth += token_balance

                # Get SOL balance
                sol_balance_payload = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "getBalance",
                    "params": [wallet_address]
                }
                async with session.post(ALCHEMY_URL, json=sol_balance_payload) as sol_response:
                    if sol_response.status == 200:
                        sol_data = await sol_response.json()
                        sol_balance = sol_data.get('result', {}).get('value', 0) / 1e9  # Convert lamports to SOL
                        sol_worth += sol_balance
                        total_worth += sol_balance

                return sol_worth, total_worth
            return 0, 0

async def get_memecoin_transactions(wallet_address, limit=1):
    transport = AIOHTTPTransport(
        url="https://graphql.bitquery.io",
        headers={"X-API-KEY": BITQUERY_API_KEY}
    )

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        query = gql(
            """
            query ($address: String!, $limit: Int!) {
              solana {
                transfers(
                  options: {limit: $limit, desc: "block.timestamp.time"}
                  receiverAddress: {is: $address}
                ) {
                  amount
                  currency {
                    symbol
                    name
                    address
                  }
                  block {
                    timestamp {
                      time(format: "%Y-%m-%d %H:%M:%S")
                    }
                  }
                  transaction {
                    signature
                  }
                }
              }
            }
            """
        )

        try:
            result = await session.execute(query, variable_values={
                "address": wallet_address,
                "limit": 20  # Fetch more to increase chances of finding memecoins
            })
            
            transfers = result["solana"]["transfers"]
            memecoin_txs = []
            
            for transfer in transfers:
                if transfer["currency"]["symbol"] not in MAIN_TOKENS:
                    memecoin_txs.append(await format_bitquery_transfer(transfer))
                    if len(memecoin_txs) == limit:
                        break
            
            if not memecoin_txs:
                print("No memecoin transactions found")
            return memecoin_txs
        
        except TransportQueryError as e:
            print(f"GraphQL query failed: {str(e)}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
    
    return []

async def format_bitquery_transfer(transfer):
    amount = float(transfer["amount"])
    symbol = transfer["currency"]["symbol"]
    timestamp = datetime.strptime(transfer["block"]["timestamp"]["time"], "%Y-%m-%d %H:%M:%S")
    signature = transfer["transaction"]["signature"]
    token_address = transfer['currency']['address']
    
    if not symbol or symbol == "Unknown":
        symbol = await get_token_symbol(token_address)
    
    token_name = transfer['currency'].get('name') or await get_token_name(token_address)
    
    message = f"🚀 [Transaction](https://solscan.io/tx/{signature})\n"
    message += f"🕰️ {timestamp.strftime('%d %B %Y at %I:%M %p')}\n"
    message += f"💱 Received: {locale.format_string('%.0f', amount, grouping=True)} {symbol}\n"
    message += f"🏷️ Ticker: {symbol}\n"
    message += f"💎 Token Name: {token_name}\n"
    message += f"📍 Token Address: `{token_address}`\n"
    message += f"🔄 [Swap on Jupiter](https://jup.ag/swap/SOL-{token_address})\n"
    
    return message

async def is_memecoin_transaction(signature_str):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        try:
            tx = await client.get_transaction(
                Signature.from_string(signature_str), 
                commitment=Confirmed, 
                max_supported_transaction_version=0
            )
            if tx and tx.value and tx.value.transaction and tx.value.transaction.meta:
                logs = tx.value.transaction.meta.log_messages
                if logs:
                    for log in logs:
                        if "Program log: Instruction: Swap" in log:
                            print(f"Found swap in transaction {signature_str}")
                            return await format_transaction_message(tx.value, signature_str, logs)
            else:
                print(f"Transaction {signature_str} does not contain expected data structure")
        except Exception as e:
            print(f"Error processing transaction {signature_str}: {str(e)}")
            print(traceback.format_exc())
    return None

async def format_transaction_message(tx, signature, logs):
    try:
        block_time = tx.block_time
        
        # Extract token information from logs
        input_token = None
        output_token = None
        for log in logs:
            if "Swap Input" in log:
                input_token = log.split(":")[1].strip()
            if "Swap Output" in log:
                output_token = log.split(":")[1].strip()
            if input_token and output_token:
                break
        
        if input_token and output_token:
            time_ago = datetime.now() - datetime.fromtimestamp(block_time)
            time_ago_str = f"{time_ago.days}d " if time_ago.days > 0 else ""
            time_ago_str += f"{time_ago.seconds // 3600}h " if time_ago.seconds // 3600 > 0 else ""
            time_ago_str += f"{(time_ago.seconds % 3600) // 60}m ago"
            
            message = f"🚀 Transaction: {signature[:10]}... 🚀\n"
            message += f"🕰️ {time_ago_str}\n"
            message += f"💱 Swapped {input_token} for {output_token}\n"
            
            # Fetch token prices
            input_price = await get_token_price(input_token.split()[1])
            output_price = await get_token_price(output_token.split()[1])
            
            if input_price:
                message += f"💲 Input Token Price: ${float(input_price['price']):.6f}\n"
            if output_price:
                message += f"💲 Output Token Price: ${float(output_price['price']):.6f}\n"
            
            return message
        else:
            print(f"Could not find input and output tokens in logs for transaction {signature}")
    except Exception as e:
        print(f"Error formatting transaction message for {signature}: {str(e)}")
        print(traceback.format_exc())
    return None

async def get_transaction_frequency(wallet_address):
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "getSignaturesForAddress",
        "params": [
            wallet_address,
            {"limit": 1000}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ALCHEMY_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                transactions = data.get('result', [])
                if not transactions:
                    return 0
                
                now = datetime.now()
                day_ago = now - timedelta(days=1)
                
                daily_transactions = sum(1 for tx in transactions if datetime.fromtimestamp(tx['blockTime']) > day_ago)
                return daily_transactions
            return 0

async def get_token_price(token_address):
    url = f"https://api.jup.ag/price/v2?ids={token_address}&showExtraInfo=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data['data'][token_address]
            else:
                print(f"Failed to fetch price for {token_address}: {response.status}")
                return None

async def get_token_symbol(token_address):
    url = f"https://public-api.solscan.io/token/meta?tokenAddress={token_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('symbol', 'Unknown')
    return 'Unknown'

async def get_token_name(token_address):
    url = f"https://public-api.solscan.io/token/meta?tokenAddress={token_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('name', 'Unknown')
    return 'Unknown'

def main() -> None:
    if not TOKEN:
        print("Error: BOT_TOKEN not found in environment variables.")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("track", track_wallet))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
