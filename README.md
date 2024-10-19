# Solana Wallet Tracker Bot

This Telegram bot allows users to track Solana wallet activity, focusing on memecoin transactions. It provides information about wallet worth, recent memecoin transactions, and transaction frequency.

## Features

- Track specific Solana wallet addresses
- View total wallet worth (in SOL)
- Fetch latest memecoin transaction
- Fetch latest 3 memecoin transactions
- Check transaction frequency
- Direct links to Solscan for transaction details
- Quick access to Jupiter for token swaps

## Setup

1. Clone this repository
2. Install required packages:
   ```
   pip install python-telegram-bot python-dotenv aiohttp gql solders
   ```
3. Create a `.env` file in the project root with the following content:
   ```
   BOT_TOKEN=your_telegram_bot_token
   ALCHEMY_API_KEY=your_alchemy_api_key
   BITQUERY_API_KEY=your_bitquery_api_key
   ```
4. Replace `your_telegram_bot_token`, `your_alchemy_api_key`, and `your_bitquery_api_key` with your actual API keys.

## Usage

1. Start the bot by running:
   ```
   python solana_wallet_tracker_bot.py
   ```
2. In Telegram, start a conversation with your bot
3. Use the `/track <wallet_address>` command to start tracking a wallet
4. Use the inline buttons to fetch different types of information about the tracked wallet

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check [issues page](https://github.com/yourusername/solana-wallet-tracker-bot/issues) if you want to contribute.

## License

[MIT](https://choosealicense.com/licenses/mit/)

